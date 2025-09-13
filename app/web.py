from flask import Flask, request, render_template, redirect, url_for, jsonify, session
import tempfile
import os
import json
from werkzeug.utils import secure_filename
from app.ingest.parse_vivado import parse_summary
from app.rules.heuristics import suggest_fix
from app.llm_clients import orchestrator
from app.timing_guardrails import guardrails
from app.schemas import ViolationPrompt, WorstCell, WorstNet
from app.rox_agent import rox_agent
from datetime import datetime
import requests
import time

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'clkwise_timing_debugger_2024'  # Change this in production

# Configuration for AI APIs
COHERE_API_KEY = os.environ.get('COHERE_API_KEY', '')
CEREBRAS_API_KEY = os.environ.get('CEREBRAS_API_KEY', '')

# File upload configuration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_CODE_EXTENSIONS = {'.v', '.sv', '.vhd', '.vhdl', '.vh', '.svh'}
ALLOWED_LOG_EXTENSIONS = {'.rpt', '.log', '.txt', '.out'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_extensions):
    return any(filename.lower().endswith(ext) for ext in allowed_extensions)

def save_uploaded_files(files, file_type):
    """Save uploaded files and return their info"""
    saved_files = []
    allowed_exts = ALLOWED_CODE_EXTENSIONS if file_type == 'code' else ALLOWED_LOG_EXTENSIONS
    
    for file in files:
        if file and file.filename and allowed_file(file.filename, allowed_exts):
            filename = secure_filename(file.filename)
            # Add timestamp to prevent conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Read file content
            try:
                with open(filepath, 'r', errors='ignore') as f:
                    content = f.read()
                saved_files.append({
                    'name': file.filename,
                    'path': filepath,
                    'content': content
                })
            except Exception as e:
                print(f"Error reading file {filename}: {e}")
                
    return saved_files

def get_ai_response(message, context=None, analysis_data=None):
    """Enhanced AI response using robust LLM pipeline with structured analysis"""
    
    # Check if we have specific violation data for structured analysis
    if analysis_data and analysis_data.get('violations'):
        # Use structured violation analysis for specific questions about violations
        violation = analysis_data['violations'][0]  # Analyze the worst violation
        
        try:
            # Convert violation to structured prompt format
            prompt = ViolationPrompt(
                clock=violation.get('clock', 'unknown'),
                slack_ns=float(violation.get('slack', -1.0)),
                startpoint=violation.get('startpoint', 'unknown'),
                endpoint=violation.get('endpoint', 'unknown'),
                levels_of_logic=int(violation.get('levels_of_logic', 0)),
                worst_cells=[
                    WorstCell(inst=f"cell_{i}", type="LUT", delay_ns=0.5)
                    for i in range(min(2, violation.get('levels_of_logic', 0)))
                ],
                worst_nets=[
                    WorstNet(net=f"net_{i}", delay_ns=1.0, routing_pct=violation.get('routing_pct', 50))
                    for i in range(1)
                ],
                hints=[violation.get('tips', '')]
            )
            
            # Get structured analysis from LLM orchestrator
            result = orchestrator.analyze_violation(prompt)
            
            # Validate and enhance with guardrails
            is_valid, warnings = guardrails.validate_llm_suggestions(result, prompt)
            if warnings:
                result = guardrails.enhance_llm_result(result, prompt)
            
            # Convert to readable format for user
            response_parts = []
            response_parts.append(f"**Analysis of {violation.get('startpoint', 'path')} → {violation.get('endpoint', 'path')}**")
            response_parts.append(f"**Issue Classification:** {result.issue_class.title()}")
            
            if result.probable_root_cause:
                response_parts.append(f"**Root Causes:**")
                for cause in result.probable_root_cause:
                    response_parts.append(f"• {cause}")
            
            response_parts.append(f"**Recommended Fixes:**")
            for i, fix in enumerate(result.suggested_fixes[:3], 1):  # Show top 3
                response_parts.append(f"{i}. {fix.to_markdown()}")
            
            if result.risk_notes:
                response_parts.append(f"**⚠️ Implementation Risks:**")
                for risk in result.risk_notes:
                    response_parts.append(f"• {risk}")
            
            if result.verify_steps:
                response_parts.append(f"**Verification Steps:**")
                for step in result.verify_steps:
                    response_parts.append(f"• {step}")
            
            response_parts.append(f"\n*Analysis confidence: {result.confidence_score:.1%} | Processing: {result.processing_time_ms:.1f}ms | Model: {result.model_used}*")
            
            if warnings:
                response_parts.append(f"\n*Note: Enhanced with heuristic analysis*")
            
            return "\n\n".join(response_parts)
            
        except Exception as e:
            print(f"Structured analysis failed: {e}")
            # Fall through to general chat mode
    
    # General chat mode - use simplified approach
    return get_general_ai_response(message, analysis_data)

def get_general_ai_response(message, analysis_data=None):
    """General AI response for non-violation specific questions"""
    
    # Build context for general questions
    context_text = ""
    if analysis_data:
        summary = analysis_data.get('summary', {})
        context_text += f"""
Current Analysis Context:
- Worst Negative Slack (WNS): {summary.get('wns', 'N/A')} ns
- Total Negative Slack (TNS): {summary.get('tns', 'N/A')} ns
- Number of violations: {len(analysis_data.get('violations', []))}
"""
    
    system_prompt = f"""
You are an expert FPGA timing closure engineer with deep knowledge of:
- Static Timing Analysis (STA) and timing optimization
- Xilinx Vivado and Intel Quartus timing closure
- Verilog/SystemVerilog/VHDL best practices
- Clock domain crossing (CDC) and pipeline design
- FPGA resource utilization and placement optimization

Provide practical, specific advice for FPGA timing issues. Be concise but thorough.
{context_text}
"""
    
    # Try primary client (Cerebras) first, then fallback
    if orchestrator.primary_client.is_available():
        try:
            response = orchestrator.primary_client.json_chat(
                system_prompt,
                f"User question: {message}\n\nProvide a helpful response (not JSON, just text):"
            )
            # Clean any JSON artifacts that might remain
            if response.startswith('{') or response.startswith('['):
                return get_fallback_response(message, analysis_data)
            return response
        except Exception as e:
            print(f"General AI response failed: {e}")
    
    # Ultimate fallback
    return get_fallback_response(message, analysis_data)

def get_dual_model_analysis(violations, summary_data):
    """Perform analysis using both Cerebras and Cohere sequentially"""
    # Return a simple mock analysis for now to prevent blocking
    analysis_results = {
        'cerebras_analysis': '''**CEREBRAS ANALYSIS:**

Root Cause Analysis:
1. Critical path contains excessive logic levels (8 detected)
2. High routing congestion causing 45% routing delay
3. Clock skew issues between related flops

Optimization Strategies:
1. Add pipeline registers to break critical paths
2. Use AREA_GROUP constraints for placement optimization
3. Implement proper clock domain crossing techniques

Tool-Specific Settings:
- Enable retiming in Vivado synthesis
- Use DSP48 blocks for multiplication operations
- Set appropriate timing constraints''',
        'cohere_analysis': '''**COHERE ANALYSIS:**

Advanced Optimization Opportunities:
1. Implement multi-cycle path constraints for non-critical paths
2. Use clock gating to reduce power and improve timing
3. Consider architectural changes like distributed vs block RAM

Risk Assessment:
- Pipeline insertion may increase latency
- Placement constraints could affect routability
- Clock domain changes require verification

Verification Steps:
1. Run timing simulation after changes
2. Verify functional correctness with testbench
3. Check power consumption impact''',
        'combined_insights': '''**COMPREHENSIVE FPGA TIMING ANALYSIS**

**Root Cause Analysis:**
1. Critical path contains excessive logic levels (8 levels detected)
2. High routing congestion in center region causing 45% routing delay
3. Clock skew issues between related flops (0.3ns difference)

**Optimization Strategy:**
1. **Pipeline Insertion**: Add registers to break critical path into 2-3 stages
2. **Placement Optimization**: Use AREA_GROUP constraints to cluster logic
3. **Clock Domain Optimization**: Implement proper synchronizers

**Implementation Priority:**
1. HIGH: Pipeline critical arithmetic operations
2. MEDIUM: Optimize placement with LOC constraints
3. LOW: Fine-tune I/O timing with OFFSET constraints

**Expected Results:**
- WNS improvement: +0.8ns to +1.2ns
- TNS improvement: Complete elimination of violations
- Timing closure confidence: 95%

*Analysis completed using Cerebras + Cohere dual AI pipeline*''',
        'models_used': ['cerebras', 'cohere']
    }
    
    print("✅ Mock dual analysis completed (Cerebras + Cohere)")
    return analysis_results

def get_ai_response_with_model(message, context, analysis_data, preferred_model='cerebras'):
    """Enhanced AI response using selected model preference"""
    
    from app.llm_clients import create_cerebras_client, create_cohere_client
    
    # Create clients based on preference
    if preferred_model == 'cohere':
        primary_client = create_cohere_client()
        fallback_client = create_cerebras_client()
        primary_name = "Cohere"
        fallback_name = "Cerebras"
    else:  # Default to cerebras
        primary_client = create_cerebras_client()
        fallback_client = create_cohere_client()
        primary_name = "Cerebras"
        fallback_name = "Cohere"
    
    # Build context for the question
    context_text = ""
    if analysis_data:
        summary = analysis_data.get('summary', {})
        context_text += f"""
Current Analysis Context:
- Worst Negative Slack (WNS): {summary.get('wns', 'N/A')} ns
- Total Negative Slack (TNS): {summary.get('tns', 'N/A')} ns
- Number of violations: {len(analysis_data.get('violations', []))}
"""
    
    system_prompt = f"""
You are an expert FPGA timing closure engineer with deep knowledge of:
- Static Timing Analysis (STA) and timing optimization
- Xilinx Vivado and Intel Quartus timing closure
- Verilog/SystemVerilog/VHDL best practices
- Clock domain crossing (CDC) and pipeline design
- FPGA resource utilization and placement optimization

Provide practical, specific advice for FPGA timing issues. Be concise but thorough.
{context_text}
"""
    
    # Try primary model first
    if primary_client.is_available():
        try:
            response = primary_client.json_chat(
                system_prompt,
                f"User question: {message}\n\nProvide a helpful response (not JSON, just text):"
            )
            # Clean any JSON artifacts that might remain
            if response.startswith('{') or response.startswith('['):
                return get_fallback_response(message, analysis_data) + f" (via {primary_name})"
            return response + f" (via {primary_name})"
        except Exception as e:
            print(f"{primary_name} failed: {e}")
    
    # Try fallback model
    if fallback_client.is_available():
        try:
            response = fallback_client.json_chat(
                system_prompt,
                f"User question: {message}\n\nProvide a helpful response (not JSON, just text):"
            )
            # Clean any JSON artifacts that might remain
            if response.startswith('{') or response.startswith('['):
                return get_fallback_response(message, analysis_data) + f" (via {fallback_name} fallback)"
            return response + f" (via {fallback_name} fallback)"
        except Exception as e:
            print(f"{fallback_name} fallback failed: {e}")
    
    # Ultimate fallback to heuristics
    return get_fallback_response(message, analysis_data) + " (via heuristic analysis)"

def get_fallback_response(message, analysis_data):
    """Provide basic responses when AI APIs are not available"""
    message_lower = message.lower()
    
    if 'timing' in message_lower and 'violation' in message_lower:
        return """Common timing violation fixes:
1. Add pipeline registers to break long combinational paths
2. Use faster speed grade devices
3. Optimize placement with LOC constraints
4. Reduce logic levels by restructuring equations
5. Use DSP blocks for multiplication operations"""
    
    elif 'pipeline' in message_lower:
        return """To add pipelining:
1. Insert registers in long arithmetic chains
2. Balance pipeline stages for equal delays
3. Consider retiming in Vivado synthesis
4. Use shift registers for delay pipelines"""
        
    elif 'dsp' in message_lower:
        return """To use DSP48 blocks:
1. Add (* use_dsp = "yes" *) attribute
2. Structure multipliers to match DSP architecture
3. Chain multiple DSPs for large operations
4. Consider pre-adders and post-adders"""
    
    elif analysis_data and analysis_data.get('violation_count', 0) > 0:
        return f"""I see you have {analysis_data.get('violation_count')} timing violations with WNS of {analysis_data.get('wns')}ns. 
The most common fixes are pipelining (for high logic levels) and placement optimization (for high routing delays). 
What specific aspect would you like help with?"""
    
    else:
        return "I'm here to help with FPGA timing closure! Ask me about timing violations, optimization techniques, or HDL best practices."

@app.route('/')
def upload_form():
    return render_template('upload.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # Handle code files (no model preference needed - using both)
        code_files = request.files.getlist('code_files')
        log_files = request.files.getlist('log_files')
        
        if not log_files or not any(f.filename for f in log_files):
            return jsonify({'error': 'At least one timing report file is required'}), 400
        
        # Save uploaded files
        saved_code_files = save_uploaded_files(code_files, 'code')
        saved_log_files = save_uploaded_files(log_files, 'log')
        
        # Parse timing reports with Rox messy data handling
        all_violations = []
        combined_summary = {'wns': None, 'tns': None, 'violations': []}
        
        # Use Rox agent for robust data ingestion
        for log_file in saved_log_files:
            try:
                # Ingest potentially messy/corrupted data
                rox_agent.ingest_messy_data(
                    content=log_file['content'],
                    source_name=log_file['name'],
                    tool_hint=""  # Auto-detect
                )
                
                # Also use traditional parser for comparison
                summary = parse_summary(log_file['content'])
                
                # Update combined summary with worst values
                if summary.get('wns') is not None:
                    if combined_summary['wns'] is None or summary['wns'] < combined_summary['wns']:
                        combined_summary['wns'] = summary['wns']
                
                if summary.get('tns') is not None:
                    if combined_summary['tns'] is None:
                        combined_summary['tns'] = summary['tns']
                    else:
                        combined_summary['tns'] += summary['tns']
                
                # Add violations with enhanced data for LLM analysis
                for v in summary.get('violations', []):
                    v['tips'] = suggest_fix(v)
                    v['source_file'] = log_file['name']
                    
                    # Add default values for structured analysis if missing
                    if 'clock' not in v:
                        v['clock'] = 'clk_unknown'
                    if 'routing_pct' not in v:
                        v['routing_pct'] = 50  # Default assumption
                    if 'levels_of_logic' not in v:
                        v['levels_of_logic'] = 5  # Conservative estimate
                        
                    all_violations.append(v)
                    
            except Exception as e:
                print(f"Error parsing {log_file['name']}: {e}")
        
        # Sort violations by slack (worst first)
        all_violations.sort(key=lambda x: x.get('slack', 0) if x.get('slack') is not None else 0)
        combined_summary['violations'] = all_violations
        
        # Extract robust violations using Rox agent
        try:
            rox_violations = rox_agent.extract_robust_violations()
            if rox_violations:
                # Merge Rox violations with traditional parsing
                print(f"✅ Rox agent found {len(rox_violations)} robust violations")
                # Add Rox violations to the analysis
                combined_summary['rox_violations'] = rox_violations[:5]  # Top 5
        except Exception as e:
            print(f"Rox agent extraction failed: {e}")
        
        # Perform dual model AI analysis (Cerebras + Cohere) - DISABLED FOR TESTING
        # print("🚀 Starting dual model analysis pipeline...")
        # dual_analysis = None
        # try:
        #     dual_analysis = get_dual_model_analysis(all_violations[:10], combined_summary)
        #     print(f"✅ Dual analysis completed using models: {', '.join(dual_analysis['models_used'])}")
        #     combined_summary['ai_analysis'] = dual_analysis
        # except Exception as e:
        #     print(f"Dual model analysis failed: {e}")
        #     combined_summary['ai_analysis'] = {
        #         'error': 'AI analysis temporarily unavailable',
        #         'models_used': []
        #     }
        
        print("✅ Analysis completed (dual AI disabled for testing)")
        
        # Store in session for chat context
        session['analysis_data'] = {
            'summary': combined_summary,
            'violations': all_violations[:10],  # Store top 10 for chat context
            'code_files': [f['name'] for f in saved_code_files],
            'log_files': [f['name'] for f in saved_log_files],
            'timestamp': datetime.now().isoformat()
        }
        
        # Clean up temporary files
        for files in [saved_code_files, saved_log_files]:
            for f in files:
                try:
                    os.unlink(f['path'])
                except:
                    pass
        
        return redirect(url_for('show_results'))
        
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/results')
def show_results():
    analysis_data = session.get('analysis_data')
    if not analysis_data:
        return redirect(url_for('upload_form'))
    
    return render_template('results.html', 
                         summary=analysis_data['summary'],
                         violations=analysis_data['violations'],
                         code_files=analysis_data['code_files'],
                         log_files=analysis_data['log_files'])


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context', '')
        preferred_model = data.get('preferred_model', 'cerebras')
        analysis_data = data.get('analysis_data', session.get('analysis_data', {}))
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get AI response with model preference
        response = get_ai_response_with_model(message, context, analysis_data, preferred_model)
        
        return jsonify({
            'response': response,
            'model_used': preferred_model
        })
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({
            'response': 'Sorry, I encountered an error processing your message. Please try again.',
            'model_used': 'fallback'
        })

@app.route('/analyze_document', methods=['POST'])
def analyze_document():
    """Enhanced document analysis using Cohere's multimodal capabilities"""
    try:
        data = request.get_json()
        document_content = data.get('content', '')
        analysis_type = data.get('type', 'timing_report')
        
        if not document_content:
            return jsonify({'error': 'No document content provided'}), 400
        
        # Use Cohere client for multimodal document analysis
        from app.llm_clients import create_cohere_client
        cohere_client = create_cohere_client()
        
        if not cohere_client.is_available():
            return jsonify({'error': 'Cohere API not configured'}), 503
        
        # Perform advanced document analysis
        analysis_result = cohere_client.analyze_document(document_content, analysis_type)
        
        return jsonify({
            'analysis': analysis_result,
            'timestamp': datetime.now().isoformat(),
            'model': 'cohere-multimodal'
        })
        
    except Exception as e:
        return jsonify({'error': f'Document analysis failed: {str(e)}'}), 500

@app.route('/create_workflow', methods=['POST'])
def create_workflow():
    """Generate agentic workflow using Cohere's reasoning capabilities"""
    try:
        data = request.get_json()
        task_description = data.get('task', '')
        context = data.get('context', {})
        
        if not task_description:
            return jsonify({'error': 'No task description provided'}), 400
        
        # Use Cohere client for agentic workflow generation
        from app.llm_clients import create_cohere_client
        cohere_client = create_cohere_client()
        
        if not cohere_client.is_available():
            return jsonify({'error': 'Cohere API not configured'}), 503
        
        # Generate agentic workflow
        workflow_steps = cohere_client.create_agentic_workflow(task_description, context)
        
        return jsonify({
            'workflow': workflow_steps,
            'task': task_description,
            'timestamp': datetime.now().isoformat(),
            'model': 'cohere-agentic'
        })
        
    except Exception as e:
        return jsonify({'error': f'Workflow creation failed: {str(e)}'}), 500

@app.route('/rox_analyze', methods=['POST'])
def rox_robust_analysis():
    """Advanced messy data analysis using Rox AI Agent capabilities"""
    try:
        data = request.get_json()
        task_description = data.get('task', 'Analyze timing violations from messy data sources')
        
        # Clear previous data and start fresh analysis
        rox_agent.data_sources.clear()
        rox_agent.conflict_resolutions.clear()
        
        # Get uploaded files from session or request
        if 'files' in data:
            # Direct file content provided
            for file_info in data['files']:
                rox_agent.ingest_messy_data(
                    content=file_info.get('content', ''),
                    source_name=file_info.get('name', 'unnamed'),
                    tool_hint=file_info.get('tool', '')
                )
        else:
            # Use files from current session
            analysis_data = session.get('analysis_data', {})
            if not analysis_data:
                return jsonify({'error': 'No analysis data available. Upload files first.'}), 400
        
        # Perform robust analysis
        robust_result = rox_agent.generate_robust_analysis(task_description)
        
        return jsonify({
            'rox_analysis': robust_result,
            'task': task_description,
            'timestamp': datetime.now().isoformat(),
            'sources_processed': len(rox_agent.data_sources),
            'conflicts_resolved': len(rox_agent.conflict_resolutions),
            'model': 'rox-messy-data-agent'
        })
        
    except Exception as e:
        return jsonify({'error': f'Rox analysis failed: {str(e)}'}), 500

@app.route('/gemini_summarize', methods=['POST'])
def gemini_summarize_report():
    """Generate natural language summary using Google Gemini API"""
    try:
        data = request.get_json()
        report_content = data.get('content', '')
        focus_areas = data.get('focus_areas', [])
        
        if not report_content:
            return jsonify({'error': 'No report content provided'}), 400
        
        # Use Gemini client for natural language summarization
        from app.llm_clients import create_gemini_client
        gemini_client = create_gemini_client()
        
        if not gemini_client.is_available():
            return jsonify({'error': 'Gemini API not configured'}), 503
        
        # Generate comprehensive summary
        summary_result = gemini_client.summarize_timing_report(report_content, focus_areas)
        
        return jsonify({
            'summary': summary_result,
            'focus_areas': focus_areas,
            'timestamp': datetime.now().isoformat(),
            'model': 'gemini-1.5-pro'
        })
        
    except Exception as e:
        return jsonify({'error': f'Gemini summarization failed: {str(e)}'}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 CLKWISE: AI-POWERED TIMING ANALYSIS PLATFORM")
    print("="*60)
    print("🏆 HACKATHON SPONSOR INTEGRATIONS:")
    print("")
    
    # Check sponsor API availability
    from app.llm_clients import create_groq_client, create_cohere_client, create_gemini_client
    
    sponsor_status = []
    
    # Groq
    groq_client = create_groq_client()
    groq_status = "✅ READY" if groq_client.is_available() else "❌ NOT CONFIGURED"
    sponsor_status.append(("⚡ GROQ", groq_status, "Ultra-fast inference (Prize: $500 swag)"))
    
    # Cohere  
    cohere_client = create_cohere_client()
    cohere_status = "✅ READY" if cohere_client.is_available() else "❌ NOT CONFIGURED"
    sponsor_status.append(("🧠 COHERE", cohere_status, "Multimodal AI (Prize: $500 cash + credits)"))
    
    # Gemini
    gemini_client = create_gemini_client()
    gemini_status = "✅ READY" if gemini_client.is_available() else "❌ NOT CONFIGURED"
    sponsor_status.append(("📖 GEMINI", gemini_status, "Natural language (Prize: Google swag)"))
    
    # Rox Agent (always available)
    sponsor_status.append(("💎 ROX", "✅ READY", "Messy data handling (Prize: $10K!)"))
    
    # Cerebras
    cerebras_status = "✅ READY" if orchestrator.primary_client.get_model_name().startswith('cerebras') else "❌ NOT CONFIGURED"
    sponsor_status.append(("🚀 CEREBRAS", cerebras_status, "Advanced inference (Prize: Keychron keyboards)"))
    
    for name, status, description in sponsor_status:
        print(f"   {name:<15} {status:<15} {description}")
    
    print("")
    print("🎯 ACTIVE AI PIPELINE:")
    print(f"   Primary: {orchestrator.primary_client.get_model_name() if orchestrator.primary_client.is_available() else 'None configured'}")
    print(f"   Fallback: {orchestrator.fallback_client.get_model_name() if orchestrator.fallback_client and orchestrator.fallback_client.is_available() else 'None'}")
    print(f"   Guardrails: Enabled")
    print(f"   Rox Agent: Enabled")
    print("")
    port = int(os.environ.get('PORT', 8082))
    print(f"🌐 Web interface starting at: http://127.0.0.1:{port}/")
    print("   Upload timing reports to see sponsor integrations in action!")
    print("="*60)
    
    app.run(debug=True, host='127.0.0.1', port=port)
