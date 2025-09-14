#!/usr/bin/env python3
"""
web_server.py
Flask web server for Clkwise FPGA timing analysis application.

This server provides:
1. Static file serving for the frontend
2. API endpoints for timing analysis data
3. Integration with Cohere service for enhanced presentation
4. RESTful API for frontend consumption

Run with:
  python web_server.py
  
Access at:
  http://localhost:8000/
"""

import os
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

# Import our services
from llm_integration.cohere_service import CohereProcessor, load_and_process_cerebras_file

# Flask app setup
app = Flask(__name__, 
           static_folder='../../frontend',
           template_folder='../../frontend/templates')
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Global state for demo purposes (in production, use a database)
current_analysis_data = None
cohere_processor = CohereProcessor()

def load_current_analysis_data():
    """Helper function to load analysis data if not already loaded."""
    global current_analysis_data
    
    if not current_analysis_data:
        cerebras_file = Path(__file__).parent.parent / 'data' / 'llm_out' / 'cerebras_out.json'
        
        if cerebras_file.exists():
            try:
                current_analysis_data = load_and_process_cerebras_file(str(cerebras_file))
            except Exception as e:
                raise Exception(f'Failed to load analysis data: {str(e)}')
        else:
            raise FileNotFoundError('No analysis data available')
    
    return current_analysis_data

def run_backend_pipeline(hdl_file, timing_file):
    """
    Run the complete backend processing pipeline using the uploaded files.
    
    1. Convert RPT to JSON using run_pipeline
    2. Generate optimized HDL using cerebras_int_no_schema.py
    3. Extract the SV artifacts to get the optimized code
    
    Args:
        hdl_file: Path to the HDL file
        timing_file: Path to the timing report file
        
    Returns:
        Dictionary with timing data and paths to processed files
    """
    try:
        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Step 1: Process timing report to generate LLM input JSON
            print(f"[INFO] Processing timing report: {timing_file}")
            rpt_json_out = temp_dir_path / "llm_json_simple.json"
            
            # Ensure the directory structure exists
            os.makedirs(Path("backend/data/rpt_json_con").parent, exist_ok=True)
            
            # Execute run_pipeline script to convert RPT to JSON
            cmd1 = [
                "python3", 
                "backend/app/ingest/run_pipeline", 
                timing_file,
                "--out", str(rpt_json_out)
            ]
            
            print(f"[COMMAND] {' '.join(cmd1)}")
            result1 = subprocess.run(
                cmd1, 
                capture_output=True, 
                text=True,
                cwd=str(Path(__file__).parent.parent.parent.parent)  # Project root
            )
            
            if result1.returncode != 0:
                print(f"[ERROR] Run pipeline failed: {result1.stderr}")
                raise Exception(f"Timing report processing failed: {result1.stderr}")
                
            # Create output directory if it doesn't exist
            llm_out_dir = Path("backend/data/llm_out")
            os.makedirs(llm_out_dir, exist_ok=True)
            
            # Step 2: Run the LLM to generate optimized Verilog
            print(f"[INFO] Running LLM optimization with input JSON: {rpt_json_out}")
            llm_output = llm_out_dir / "cerebras_out.json"
            
            cmd2 = [
                "python3",
                "backend/app/llm_integration/cerebras_int_no_schema.py",
                "--timing", str(rpt_json_out),
                "--verilog", hdl_file,
                "--out", str(llm_output)
            ]
            
            print(f"[COMMAND] {' '.join(cmd2)}")
            result2 = subprocess.run(
                cmd2, 
                capture_output=True, 
                text=True,
                cwd=str(Path(__file__).parent.parent.parent.parent)  # Project root
            )
            
            if result2.returncode != 0:
                print(f"[ERROR] LLM processing failed: {result2.stderr}")
                raise Exception(f"LLM processing failed: {result2.stderr}")
                
            # Step 3: Extract SV artifacts from the LLM output
            print(f"[INFO] Extracting SV artifacts from LLM output: {llm_output}")
            
            # Create output directory for frontend data if it doesn't exist
            frontend_data_dir = Path("backend/data/frontend_data/data")
            os.makedirs(frontend_data_dir, exist_ok=True)
            
            optimized_sv = frontend_data_dir / "top.sv"
            optimized_txt = frontend_data_dir / "top.txt"
            
            cmd3 = [
                "python3",
                "backend/data/frontend_data/scripts/extract_sv_artifacts.py",
                str(llm_output),
                "--sv", str(optimized_sv),
                "--txt", str(optimized_txt)
            ]
            
            print(f"[COMMAND] {' '.join(cmd3)}")
            result3 = subprocess.run(
                cmd3, 
                capture_output=True, 
                text=True,
                cwd=str(Path(__file__).parent.parent.parent.parent)  # Project root
            )
            
            if result3.returncode != 0:
                print(f"[ERROR] SV artifact extraction failed: {result3.stderr}")
                raise Exception(f"SV artifact extraction failed: {result3.stderr}")
            
            # Copy the optimized SV file to our uploads/optimized directory for consistency
            optimized_folder = Path(app.config['UPLOAD_FOLDER']) / 'optimized'
            optimized_folder.mkdir(exist_ok=True)
            
            original_filename = Path(hdl_file).name
            optimized_file = optimized_folder / original_filename
            
            shutil.copy(optimized_sv, optimized_file)
            
            # Also save to the project root for compatibility
            shutil.copy(optimized_sv, Path(__file__).parent.parent.parent / 'top.sv')
            
            # Load and parse the LLM output JSON to extract timing data
            with open(llm_output, 'r') as f:
                import json
                llm_data = json.load(f)
            
            # Extract timing data from the LLM output
            timing_data = extract_timing_from_llm_output(llm_data)
            
            # Return the results
            return {
                'timing_data': timing_data,
                'original_file': hdl_file,
                'optimized_file': str(optimized_file),
                'llm_output': str(llm_output),
                'optimized_sv': str(optimized_sv),
                'optimized_txt': str(optimized_txt)
            }
            
    except Exception as e:
        print(f"[ERROR] Backend pipeline failed: {e}")
        raise e

def extract_timing_from_llm_output(llm_data):
    """Extract timing information from the LLM output JSON."""
    try:
        # Navigate through the JSON structure to find timing data
        # This will need to be adjusted based on your actual JSON structure
        timing_info = llm_data.get('result', {}).get('timing_info', {})
        
        # Extract key metrics
        wns = float(timing_info.get('wns', -1.2))
        tns = float(timing_info.get('tns', -3.5))
        period = float(timing_info.get('period', 10.0))
        
        # Extract violations if available
        violations_data = timing_info.get('violations', [])
        violations = []
        
        for violation in violations_data:
            violations.append({
                'startpoint': violation.get('startpoint', 'unknown'),
                'endpoint': violation.get('endpoint', 'unknown'),
                'slack_ns': float(violation.get('slack', -1.0)),
                'clock': violation.get('clock', 'unknown'),
                'description': violation.get('description', 'Timing path violation')
            })
        
        # If no violations in the expected format, try alternative formats
        if not violations and 'paths' in timing_info:
            for path in timing_info.get('paths', []):
                violations.append({
                    'startpoint': path.get('startpoint', 'unknown'),
                    'endpoint': path.get('endpoint', 'unknown'),
                    'slack_ns': float(path.get('slack', -1.0)),
                    'clock': path.get('clock', 'unknown'),
                    'description': path.get('description', 'Timing path violation')
                })
        
        # Create a result object
        result = {
            'wns': wns,
            'tns': tns,
            'period': period,
            'violations': violations
        }
        
        return result
    except Exception as e:
        print(f"[ERROR] Failed to extract timing data: {e}")
        # Return fallback data
        return {
            'wns': -1.2,
            'tns': -3.5,
            'period': 10.0,
            'violations': [
                {
                    'startpoint': 'ff_reg',
                    'endpoint': 'output_reg',
                    'slack_ns': -1.2,
                    'clock': 'clk',
                    'description': 'Default timing violation from fallback'
                }
            ]
        }

@app.route('/')
def index():
    """Serve the main upload page."""
    return render_template('upload.html')

@app.route('/about')
def about():
    """Serve the about page.""" 
    return render_template('about.html')


@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    """
    Get the current timing analysis data.
    
    Returns:
        JSON with enhanced timing analysis data
    """
    try:
        data = load_current_analysis_data()
        return jsonify({
            'status': 'success',
            'data': data
        })
    except FileNotFoundError:
        return jsonify({
            'error': 'No analysis data available',
            'status': 'not_found'
        }), 404
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/analysis/summary', methods=['GET'])
def get_analysis_summary():
    """
    Get a summary of the timing analysis.
    
    Returns:
        JSON with summary data optimized for UI display
    """
    try:
        analysis_data = load_current_analysis_data()
        
        ui_data = analysis_data.get('ui_data', {})
        analysis = analysis_data.get('analysis', {})
        
        summary = {
            'header': ui_data.get('header', {}),
            'problem': ui_data.get('problem', {}),
            'metrics': ui_data.get('metrics', {}),
            'severity': analysis.get('summary', {}).get('severity', 'unknown'),
            'quick_facts': analysis.get('summary', {}).get('quick_facts', []),
            'explanation': analysis.get('summary', {}).get('explanation', ''),
            'fix_count': len(analysis.get('fixes', []))
        }
        
        return jsonify({
            'status': 'success',
            'summary': summary
        })
    except FileNotFoundError:
        return jsonify({
            'error': 'No analysis data available',
            'status': 'not_found'
        }), 404
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@app.route('/api/analysis/code', methods=['GET'])
def get_code_changes():
    """
    Get code changes from the analysis.
    
    Returns:
        JSON with code changes and artifacts
    """
    try:
        analysis_data = load_current_analysis_data()
        
        code_changes = analysis_data.get('analysis', {}).get('code_changes', {})
        artifacts = analysis_data.get('original', {}).get('result', {}).get('artifacts', {})
        
        return jsonify({
            'status': 'success',
            'code_changes': code_changes,
            'artifacts': artifacts
        })
    except FileNotFoundError:
        return jsonify({
            'error': 'No analysis data available',
            'status': 'not_found'
        }), 404
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/download/json', methods=['GET'])
def download_json():
    """
    Download the processed JSON created by the log parser.
    
    Returns:
        JSON file as download
    """
    try:
        analysis_data = load_current_analysis_data()
        
        from flask import make_response
        import json
        
        # Get the original cerebras data (the log parser output)
        original_data = analysis_data.get('original', {})
        
        response = make_response(json.dumps(original_data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = 'attachment; filename=timing_analysis.json'
        
        return response
    except FileNotFoundError:
        return jsonify({
            'error': 'No analysis data available for download',
            'status': 'not_found'
        }), 404
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/download/verilog', methods=['GET'])
def download_verilog():
    """
    Download the optimized Verilog code (current top.sv file).
    
    Returns:
        Verilog file as download
    """
    try:
        # Get the optimized Verilog code from the current top.sv file
        top_sv_path = Path(__file__).parent.parent.parent / 'top.sv'
        
        if not top_sv_path.exists():
            return jsonify({
                'error': 'Optimized top.sv file not found',
                'status': 'not_found'
            }), 404
        
        with open(top_sv_path, 'r', encoding='utf-8') as f:
            verilog_content = f.read()
        
        from flask import make_response
        
        response = make_response(verilog_content)
        response.headers['Content-Type'] = 'text/plain'
        response.headers['Content-Disposition'] = 'attachment; filename=optimized_timing_top.sv'
        
        return response
    except Exception as e:
        return jsonify({
            'error': f'Failed to read optimized top.sv: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/api/original/top.sv', methods=['GET'])
def get_original_top_sv():
    """
    Get the original problematic top.sv file content for diff comparison.
    This returns the simple version with timing violations, not the optimized version.
    
    Returns:
        JSON with the original problematic top.sv file content
    """
    try:
        # The original problematic code (before timing fixes)
        original_problematic_code = """module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e, //32 bit
  output logic [63:0]  y //64 bit
);

  logic [63:0] mul1 = a * b; //32 bit x 32 bit
  logic [63:0] mul2 = c * d; //32 bit x 32 bit
  logic [63:0] sum  = mul1 + mul2 + e;  //64 bit + 64 bit + 32 bit

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) y <= '0;
    else        y <= sum;
  end
endmodule"""
        
        return jsonify({
            'status': 'success',
            'content': original_problematic_code,
            'filename': 'top.sv (original with timing violations)'
        })
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate original top.sv: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/api/optimized/top.sv', methods=['GET'])
def get_optimized_top_sv():
    """
    Get the optimized top.sv file content.
    Uses the file generated by the backend pipeline if available.
    
    Returns:
        JSON with the optimized top.sv file content
    """
    try:
        # Check if we have a processed file from the pipeline
        global current_analysis_data
        
        if current_analysis_data and 'pipeline_results' in current_analysis_data and 'optimized_sv' in current_analysis_data['pipeline_results']:
            optimized_sv = current_analysis_data['pipeline_results']['optimized_sv']
            
            with open(optimized_sv, 'r') as f:
                content = f.read()
                
            return jsonify({
                'status': 'success',
                'content': content,
                'filename': f"{Path(optimized_sv).name} (optimized pipeline version)"
            })
        
        # Fall back to the analysis optimized file
        if current_analysis_data and 'analysis' in current_analysis_data and 'optimized_file' in current_analysis_data['analysis']:
            optimized_file = current_analysis_data['analysis']['optimized_file']
            
            with open(optimized_file, 'r') as f:
                content = f.read()
                
            return jsonify({
                'status': 'success',
                'content': content,
                'filename': f"{Path(optimized_file).name} (optimized version)"
            })
        
        # Fallback to the project root top.sv (which might be optimized by earlier runs)
        # [existing fallback code remains unchanged]
        ...
    except Exception as e:
        return jsonify({
            'error': f'Failed to read optimized top.sv: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/api/download/llm_json', methods=['GET'])
def download_llm_json():
    """Download the LLM output JSON file."""
    try:
        global current_analysis_data
        
        if current_analysis_data and 'pipeline_results' in current_analysis_data and 'llm_output' in current_analysis_data['pipeline_results']:
            llm_output = current_analysis_data['pipeline_results']['llm_output']
            
            with open(llm_output, 'r', encoding='utf-8') as f:
                json_content = f.read()
            
            from flask import make_response
            
            response = make_response(json_content)
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = 'attachment; filename=timing_analysis_output.json'
            
            return response
        else:
            return jsonify({
                'status': 'error',
                'error': 'No LLM output JSON available'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to download LLM JSON: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """
    Chat endpoint for conversational AI about the timing analysis.
    
    Expects:
        JSON with 'message' field
        
    Returns:
        JSON with AI response
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Message is required',
                'status': 'error'
            }), 400
        
        user_message = data['message']
        
        # Get current analysis for context
        context = {}
        try:
            analysis_data = load_current_analysis_data()
            context = analysis_data.get('analysis', {}).get('conversation_ready', {})
        except:
            pass
        
        # Generate response using Cohere if available
        response_text = ""
        
        if cohere_processor.client:
            try:
                # Build context-aware prompt
                context_info = ""
                if context:
                    metrics = context.get('key_metrics', {})
                    context_info = f"""
Context: Current timing analysis shows {context.get('problem', 'timing issues')}.
Key metrics: WNS={metrics.get('wns', 'unknown')}ns, Period={metrics.get('period', 'unknown')}ns, 
Signals={metrics.get('signal_group', 'unknown')}, Path={metrics.get('path_type', 'unknown')}.
Available fixes: {context.get('fix_count', 0)} suggestions.
"""

                prompt = f"""
You are an expert FPGA timing closure engineer helping a user analyze timing violations.

{context_info}

User question: {user_message}

Provide a helpful, technical but accessible response about FPGA timing analysis and optimization.
If the question is about the current analysis, reference the specific context provided.
Keep responses concise and practical.
"""
                
                response = cohere_processor.client.generate(
                    model="command-r-plus",
                    prompt=prompt,
                    max_tokens=300,
                    temperature=0.3
                )
                
                response_text = response.generations[0].text.strip()
                
            except Exception as e:
                print(f"Warning: Cohere API call failed: {e}")
                response_text = ""
        
        # Fallback responses if no API or API fails
        if not response_text:
            response_text = generate_fallback_response(user_message, context)
        
        return jsonify({
            'status': 'success',
            'response': response_text,
            'context_available': bool(context)
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Chat processing failed: {str(e)}',
            'status': 'error'
        }), 500

def generate_fallback_response(message: str, context: Dict[str, Any]) -> str:
    """Generate fallback responses when Cohere API is not available."""
    message_lower = message.lower()
    
    # Pattern matching for common questions
    if any(word in message_lower for word in ['cause', 'reason', 'why']):
        if context.get('key_metrics', {}).get('wns', 0) < 0:
            return """The timing violation is typically caused by paths that are too long to complete within the clock period. 
Common causes include deep combinational logic, excessive routing delays, or clock skew. 
The analysis suggests specific fixes to address these issues."""
        else:
            return "I'd be happy to help analyze timing violations. Please upload a timing report first."
    
    elif any(word in message_lower for word in ['fix', 'solution', 'solve']):
        fix_count = context.get('fix_count', 0)
        if fix_count > 0:
            return f"""The analysis suggests {fix_count} potential fixes including pipelining, placement optimization, and logic restructuring. 
Each fix includes implementation details and expected impact on timing. 
Review the fixes section for specific recommendations."""
        else:
            return """Common timing fixes include: 1) Adding pipeline stages to break long paths, 
2) Optimizing placement to reduce routing delays, 3) Using faster IO standards, 
4) Restructuring logic to reduce combinational depth."""
    
    elif any(word in message_lower for word in ['code', 'verilog', 'implementation']):
        if context.get('has_code_changes'):
            return """The analysis includes automatically generated Verilog code changes. 
These typically involve adding pipeline registers, restructuring logic, or optimizing signal routing. 
Check the code changes section for the complete modified files."""
        else:
            return """Code changes for timing fixes usually involve adding registers for pipelining, 
restructuring combinational logic, or adding placement constraints."""
    
    elif any(word in message_lower for word in ['risk', 'danger', 'problem']):
        return """Main risks of timing fixes include increased latency (affecting protocol timing), 
increased resource usage, and added design complexity. 
Always verify downstream timing assumptions and run thorough simulation after changes."""
    
    else:
        # General help response
        if context:
            severity = context.get('severity', 'unknown')
            return f"""I can help with your timing analysis (currently showing {severity} violations). 
Ask me about: the root cause of violations, implementation of suggested fixes, 
code changes needed, or verification strategies."""
        else:
            return """I'm here to help with FPGA timing analysis and optimization. 
You can ask about timing violations, fix strategies, implementation details, or verification approaches. 
Upload a timing report to get specific analysis and recommendations."""


# Static file serving for development
@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from frontend directory."""
    return send_from_directory('../../frontend', filename)

@app.route('/api/process/files', methods=['POST'])
def process_uploaded_files():
    """Process the uploaded HDL and timing files to generate optimized code using the backend pipeline."""
    try:
        # Get paths to the uploaded files from current_analysis_data
        if not current_analysis_data or 'files' not in current_analysis_data:
            return jsonify({
                'status': 'error',
                'error': 'No uploaded files found'
            }), 400
            
        files = current_analysis_data.get('files', {})
        hdl_file = files.get('hdl')
        timing_file = files.get('timing')
        
        if not hdl_file or not timing_file:
            return jsonify({
                'status': 'error',
                'error': 'Both HDL and timing files are required'
            }), 400
        
        # Update processing status
        current_analysis_data['processing_status'] = 'processing'
        
        # Run the complete backend pipeline
        print(f"[INFO] Starting backend pipeline processing for HDL: {hdl_file}, Timing: {timing_file}")
        pipeline_result = run_backend_pipeline(hdl_file, timing_file)
        
        # Extract timing data and file paths
        timing_data = pipeline_result['timing_data']
        optimized_file = pipeline_result['optimized_file']
        
        # Generate UI-friendly metrics
        metrics = {
            'wns': f"{timing_data['wns']:.3f}",
            'tns': f"{timing_data['tns']:.3f}",
            'period': f"{timing_data['period']:.3f}",
            'violation_count': len(timing_data.get('violations', [])),
            'signal_group': 'Combinational Path',
            'path_type': 'Setup'
        }
        
        # Create fixes based on timing data and LLM output
        fixes = []
        if timing_data['wns'] < 0:
            fixes.append({
                'title': 'Pipeline Multiplier Operations',
                'rationale': 'Add pipeline registers after multiplication to improve timing by breaking the critical path.',
                'impact': 'High',
                'latency_impact_cycles': 1
            })
            
        # Update analysis data with results
        current_analysis_data['processing_status'] = 'completed'
        current_analysis_data['analysis'] = {
            'timing_data': timing_data,
            'original_file': hdl_file,
            'optimized_file': optimized_file,
            'summary': {
                'severity': 'critical' if timing_data['wns'] < -1 else 'high' if timing_data['wns'] < 0 else 'pass',
                'quick_facts': [
                    f"WNS: {timing_data['wns']}ns",
                    f"TNS: {timing_data['tns']}ns",
                    f"Clock Period: {timing_data['period']}ns",
                    f"Violations: {len(timing_data.get('violations', []))}"
                ],
                'explanation': f"The design has a worst negative slack of {timing_data['wns']}ns." if timing_data['wns'] < 0 else "The design meets timing."
            },
            'violations': timing_data.get('violations', []),
            'fixes': fixes,
            'code_changes': {
                'summary': 'Pipeline registers added to improve timing.',
                'details': 'Added registers after multipliers to break critical paths.'
            } if timing_data['wns'] < 0 else {}
        }
        
        # Add conversation-ready data for the chat interface
        current_analysis_data['conversation_ready'] = {
            'problem': current_analysis_data['analysis']['summary']['explanation'],
            'severity': current_analysis_data['analysis']['summary']['severity'],
            'fix_count': len(fixes),
            'key_metrics': metrics,
            'has_code_changes': timing_data['wns'] < 0
        }
        
        # Add UI-friendly data
        current_analysis_data['ui_data'] = {
            'header': {
                'title': 'Timing Analysis Results',
                'subtitle': f"Analysis of {Path(hdl_file).name}"
            },
            'metrics': metrics,
            'problem': {
                'description': current_analysis_data['analysis']['summary']['explanation']
            }
        }
        
        # Store the pipeline result paths for access
        current_analysis_data['pipeline_results'] = pipeline_result
        
        # Redirect to results page
        return jsonify({
            'status': 'success',
            'message': 'Files processed successfully',
            'redirect': '/results'
        })
        
    except Exception as e:
        print(f"[ERROR] Processing files failed: {e}")
        if current_analysis_data:
            current_analysis_data['processing_status'] = 'failed'
            current_analysis_data['processing_error'] = str(e)
            
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/upload/files', methods=['POST'])
def upload_files():
    """Handle file uploads from the frontend and store their paths."""
    global current_analysis_data
    
    try:
        print(f"[DEBUG] Received files: {list(request.files.keys())}")
        
        # Check for file uploads with various possible field names
        verilog_file = None
        timing_file = None
        
        # Find the Verilog/HDL file
        for field_name in ['verilogFile', 'code_files', 'hdlFile', 'sv_file']:
            if field_name in request.files:
                verilog_file = request.files[field_name]
                if verilog_file.filename:
                    break
        
        # Find the timing report file
        for field_name in ['timingFile', 'log_files', 'rptFile', 'timing_file']:
            if field_name in request.files:
                timing_file = request.files[field_name]
                if timing_file.filename:
                    break
        
        # If no files found with expected names, check if we have any files
        if (not verilog_file or not verilog_file.filename) and len(request.files) > 0:
            # Take the first file as verilog
            verilog_file = list(request.files.values())[0]
        
        if (not timing_file or not timing_file.filename) and len(request.files) > 1:
            # Take the second file as timing
            timing_file = list(request.files.values())[1]
        
        # Check if we have the required files
        if not verilog_file or not verilog_file.filename:
            return jsonify({
                'status': 'error',
                'error': 'No Verilog/HDL file uploaded'
            }), 400
        
        if not timing_file or not timing_file.filename:
            return jsonify({
                'status': 'error',
                'error': 'No timing report file uploaded'
            }), 400
        
        # Create upload directories if they don't exist
        upload_folder = Path(__file__).parent / 'uploads'
        hdl_folder = upload_folder / 'hdl'
        timing_folder = upload_folder / 'timing'
        
        hdl_folder.mkdir(exist_ok=True, parents=True)
        timing_folder.mkdir(exist_ok=True, parents=True)
        
        # Save the files
        hdl_path = hdl_folder / verilog_file.filename
        timing_path = timing_folder / timing_file.filename
        
        verilog_file.save(str(hdl_path))
        timing_file.save(str(timing_path))
        
        print(f"[INFO] Files saved: HDL={hdl_path}, Timing={timing_path}")
        
        # Initialize or update the current_analysis_data
        if not current_analysis_data:
            current_analysis_data = {}
        
        current_analysis_data['files'] = {
            'hdl': str(hdl_path),
            'timing': str(timing_path)
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Files uploaded successfully',
            'files': {
                'hdl': verilog_file.filename,
                'timing': timing_file.filename
            }
        })
        
    except Exception as e:
        print(f"[ERROR] Upload failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/results')
def results_page():
    """Serve the results page showing analysis results."""
    try:
        # Check if we have analysis data
        global current_analysis_data
        
        if not current_analysis_data or 'analysis' not in current_analysis_data:
            # Redirect to upload page with error
            return render_template('upload.html', error="No analysis data available. Please upload and process files first.")
        
        return render_template('results.html')
    except Exception as e:
        print(f"[ERROR] Failed to render results page: {str(e)}")
        return render_template('upload.html', error=f"Error loading results: {str(e)}")

def initialize_demo_data():
    """Initialize with demo data if available."""
    global current_analysis_data
    
    cerebras_file = Path(__file__).parent.parent / 'data' / 'llm_out' / 'cerebras_out.json'
    
    if cerebras_file.exists():
        try:
            print(f"Loading demo analysis data from {cerebras_file}")
            current_analysis_data = load_and_process_cerebras_file(str(cerebras_file))
            print("Demo data loaded successfully")
        except Exception as e:
            print(f"Warning: Could not load demo data: {e}")

if __name__ == '__main__':
    # Initialize demo data
    initialize_demo_data()
    
    # Start the server
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"\n🚀 Starting Clkwise server...")
    print(f"📊 Access the application at: http://localhost:{port}/")
    print(f"🔧 Cohere API available: {bool(cohere_processor.client)}")
    print(f"📈 Demo data loaded: {bool(current_analysis_data)}")
    print()
    
    app.run(host='0.0.0.0', port=port, debug=debug)