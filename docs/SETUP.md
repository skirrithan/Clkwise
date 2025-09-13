# Clkwise Enhanced UI Setup

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up AI API Keys (Optional)**
   
   For enhanced AI chat functionality, you can configure one or both APIs:

   **Cohere API (Primary)**
   ```bash
   export COHERE_API_KEY="your_cohere_api_key_here"
   ```

   **Cerebras API (Fallback)**
   ```bash
   export CEREBRAS_API_KEY="your_cerebras_api_key_here"
   ```

   *Note: The chat will work with basic responses even without API keys*

3. **Start the Web Interface**
   ```bash
   python -m app.web
   ```

4. **Access the Interface**
   - Open your browser to: http://127.0.0.1:8000/
   - *Note: Using port 8000 to avoid macOS AirPlay conflict on port 5000*

## Features

### 🎯 Enhanced UI
- **Modern Design**: Professional gradient interface with responsive layout
- **Drag & Drop**: Support for dragging files directly onto upload areas
- **Multi-File Upload**: Separate areas for code files (.v, .sv, .vhd) and timing reports (.rpt, .log)
- **Real-time Feedback**: Interactive file list with remove options

### 🤖 AI-Powered Chat
- **Context-Aware**: AI understands your uploaded files and timing analysis results
- **Expert Knowledge**: Specialized in FPGA timing closure and HDL optimization
- **Dual API Support**: Uses Cohere (primary) or Cerebras (fallback) APIs
- **Fallback Responses**: Works with built-in knowledge when APIs unavailable

### 📊 Enhanced Analysis
- **Visual Results**: Card-based summary with color-coded violations
- **Multi-File Support**: Combines results from multiple timing reports
- **Detailed Violations**: Expandable violation details with AI suggestions
- **Session Persistence**: Results stay available during chat sessions

## File Support

### Code Files
- `.v` - Verilog
- `.sv` - SystemVerilog  
- `.vhd`, `.vhdl` - VHDL
- `.vh`, `.svh` - Header files

### Timing Reports & Logs
- `.rpt` - Vivado timing reports
- `.log` - Synthesis/implementation logs
- `.txt` - Text-based reports
- `.out` - Tool output files

## API Key Setup

### Getting Cohere API Key
1. Visit https://dashboard.cohere.ai/
2. Sign up/log in
3. Go to API Keys section
4. Create a new key
5. Export it: `export COHERE_API_KEY="your_key"`

### Getting Cerebras API Key  
1. Visit https://cloud.cerebras.ai/
2. Sign up/log in
3. Navigate to API section
4. Generate an API key
5. Export it: `export CEREBRAS_API_KEY="your_key"`

## Usage Tips

1. **Upload Order**: Upload timing reports first (required), then optionally add code files for better context
2. **Chat Context**: The AI has access to your analysis results and can provide specific advice
3. **File Cleanup**: Uploaded files are automatically cleaned up after analysis
4. **Session Data**: Results persist in your browser session for continued chat interaction

## Troubleshooting

- **No API Keys**: Chat works with basic responses based on common timing fixes
- **File Upload Issues**: Check file extensions and ensure files are valid
- **Large Files**: Maximum file size is 16MB per file
- **API Errors**: System automatically falls back to basic responses if APIs fail