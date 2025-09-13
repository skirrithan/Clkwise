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
        # Handle code files
        code_files = request.files.getlist('code_files')
        log_files = request.files.getlist('log_files')
        
        if not log_files or not any(f.filename for f in log_files):
            return jsonify({'error': 'At least one timing report file is required'}), 400
        
        # Save uploaded files
        saved_code_files = save_uploaded_files(code_files, 'code')
        saved_log_files = save_uploaded_files(log_files, 'log')
        
        # Parse timing reports
        all_violations = []
        combined_summary = {'wns': None, 'tns': None, 'violations': []}
        
        for log_file in saved_log_files:
            try:
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
        analysis_data = data.get('analysis_data', session.get('analysis_data', {}))
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get AI response
        response = get_ai_response(message, context, analysis_data)
        
        return jsonify({'response': response})
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({
            'response': 'Sorry, I encountered an error processing your message. Please try again.'
        })

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

if __name__ == '__main__':
    print("Starting Clkwise web interface with enhanced AI pipeline...")
    print(f"Primary AI Engine: {orchestrator.primary_client.get_model_name() if orchestrator.primary_client.is_available() else 'None configured'}")
    print(f"Fallback AI Engine: {orchestrator.fallback_client.get_model_name() if orchestrator.fallback_client and orchestrator.fallback_client.is_available() else 'None'}")
    print(f"Guardrails & Validation: Enabled")
    print(f"Structured Analysis: Enabled")
    print("")
    print("🧠 AI Features:")
    print("   ✓ Structured violation analysis with schema validation")
    print("   ✓ Heuristic guardrails and enhancement")
    print("   ✓ Multi-model fallback (Cerebras → Cohere → Heuristics)")
    print("   ✓ Real-time confidence scoring")
    print("")
    print("🌐 Web interface will be available at: http://127.0.0.1:5001/")
    print("   (Using port 5001 to avoid conflicts)")
    app.run(debug=True, host='127.0.0.1', port=5001)
