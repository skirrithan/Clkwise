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
    Get the optimized top.sv file content (the current top.sv file in the project).
    This contains the timing-fixed version with pipeline registers.
    
    Returns:
        JSON with the optimized top.sv file content
    """
    try:
        # Path to the current optimized top.sv file in the project root
        top_sv_path = Path(__file__).parent.parent.parent / 'top.sv'
        
        if not top_sv_path.exists():
            return jsonify({
                'error': 'Optimized top.sv file not found',
                'status': 'not_found'
            }), 404
        
        with open(top_sv_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'status': 'success',
            'content': content,
            'filename': 'top.sv (optimized timing-fixed)'
        })
    except Exception as e:
        return jsonify({
            'error': f'Failed to read optimized top.sv: {str(e)}',
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