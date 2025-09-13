from flask import Flask, request, render_template, redirect, url_for, jsonify, session
import tempfile
import os
import json
from werkzeug.utils import secure_filename
from app.ingest.parse_vivado import parse_summary
from app.rules.heuristics import suggest_fix
from datetime import datetime
import requests

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
    """Get AI response using Cohere or Cerebras API"""
    
    # Build context for the AI
    system_prompt = """
You are an expert FPGA timing closure engineer and Verilog/VHDL designer. 
You help engineers fix timing violations in digital designs. 

Your expertise includes:
- Static Timing Analysis (STA)
- FPGA architecture and timing optimization
- Verilog/SystemVerilog/VHDL best practices
- Xilinx Vivado timing closure techniques
- Clock domain crossing (CDC) issues
- Pipeline optimization and resource utilization

Provide practical, specific advice for fixing timing issues. Be concise but thorough.
"""
    
    # Add analysis context if available
    context_text = ""
    if analysis_data:
        context_text += f"""
Current Analysis Results:
- Worst Negative Slack (WNS): {analysis_data.get('wns', 'N/A')}
- Total Negative Slack (TNS): {analysis_data.get('tns', 'N/A')}
- Number of violations: {analysis_data.get('violation_count', 0)}
"""
        
        if analysis_data.get('violations'):
            context_text += "\nTop violations:\n"
            for i, v in enumerate(analysis_data['violations']):
                context_text += f"Path {i+1}: Slack={v.get('slack', 'N/A')}, Logic Levels={v.get('levels_of_logic', 'N/A')}, Routing%={v.get('routing_pct', 'N/A')}%\n"
    
    # Try Cohere first, then Cerebras as fallback
    if COHERE_API_KEY:
        try:
            response = requests.post(
                'https://api.cohere.ai/v1/chat',
                headers={
                    'Authorization': f'Bearer {COHERE_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'command-r-plus',
                    'message': f"{context_text}\n\nUser question: {message}",
                    'preamble': system_prompt,
                    'max_tokens': 500,
                    'temperature': 0.7
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('text', 'Sorry, I could not generate a response.')
        except Exception as e:
            print(f"Cohere API error: {e}")
    
    # Try Cerebras as fallback
    if CEREBRAS_API_KEY:
        try:
            response = requests.post(
                'https://api.cerebras.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {CEREBRAS_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama3.1-8b',
                    'messages': [
                        {'role': 'system', 'content': system_prompt + context_text},
                        {'role': 'user', 'content': message}
                    ],
                    'max_tokens': 500,
                    'temperature': 0.7
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"Cerebras API error: {e}")
    
    # Fallback response if APIs are not available
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
                
                # Add violations with fix suggestions
                for v in summary.get('violations', []):
                    v['tips'] = suggest_fix(v)
                    v['source_file'] = log_file['name']
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
    print("Starting Clkwise web interface...")
    print(f"Cohere API configured: {'Yes' if COHERE_API_KEY else 'No'}")
    print(f"Cerebras API configured: {'Yes' if CEREBRAS_API_KEY else 'No'}")
    print("")
    print("🌐 Web interface will be available at: http://127.0.0.1:8000/")
    print("   (Using port 8000 to avoid macOS AirPlay conflict on port 5000)")
    app.run(debug=True, host='127.0.0.1', port=8000)
