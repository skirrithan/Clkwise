#!/usr/bin/env python3
"""
run_server.py
Startup script for the Clkwise web server with Cohere integration.

This script:
1. Sets up the Python path for backend modules
2. Loads the cerebras output and processes it with Cohere
3. Starts the Flask web server with enhanced AI features

Usage:
  python run_server.py [--port 8000] [--debug]
"""

import os
import sys
from pathlib import Path
import argparse

# Add backend app to Python path
backend_dir = Path(__file__).parent / "backend" / "app"
sys.path.insert(0, str(backend_dir))

def main():
    parser = argparse.ArgumentParser(description="Start Clkwise web server")
    parser.add_argument("--port", type=int, default=8000, help="Port to run server on (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--cohere-key", help="Cohere API key (or set COHERE_API_KEY env var)")
    
    args = parser.parse_args()
    
    # Set environment variables
    if args.cohere_key:
        os.environ["COHERE_API_KEY"] = args.cohere_key
    
    os.environ["PORT"] = str(args.port)
    os.environ["FLASK_DEBUG"] = "true" if args.debug else "false"
    
    print("🚀 Starting Clkwise AI FPGA Timing Analysis Server")
    print("=" * 50)
    print(f"📊 Server will start at: http://localhost:{args.port}/")
    print(f"🔧 Debug mode: {'ON' if args.debug else 'OFF'}")
    print(f"🧠 Cohere API: {'CONFIGURED' if os.environ.get('COHERE_API_KEY') else 'NOT SET (will use fallback)'}")
    print(f"🚀 Cerebras API: {'CONFIGURED' if os.environ.get('CEREBRAS_API_KEY') else 'NOT SET (demo data only)'}")
    print()
    
    # Check for demo data
    cerebras_file = Path(__file__).parent / "backend" / "data" / "llm_out" / "cerebras_out.json"
    if cerebras_file.exists():
        print(f"📈 Demo timing analysis data found: {cerebras_file}")
    else:
        print("⚠️  No demo data found - you'll need to upload timing reports")
    
    print()
    print("🌟 Features available:")
    print("   • AI-enhanced timing analysis display")
    print("   • Cerebras structured output processing")
    print("   • Cohere conversational AI chat")
    print("   • Interactive fix recommendations")
    print("   • Auto-generated Verilog code changes")
    print()
    
    # Import and run the web server
    try:
        from web_server import app
        app.run(host='0.0.0.0', port=args.port, debug=args.debug)
    except ImportError as e:
        print(f"❌ Error importing web server: {e}")
        print("Make sure you're in the correct directory and dependencies are installed:")
        print("  pip install -r backend/requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()