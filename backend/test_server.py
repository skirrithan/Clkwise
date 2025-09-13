#!/usr/bin/env python3
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>CLKWISE - Test</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: #000; 
                color: #fff; 
                padding: 20px; 
            }
            .badge { 
                background: #333; 
                color: #fff; 
                padding: 5px 10px; 
                margin: 5px; 
                display: inline-block; 
                border: 1px solid #666; 
            }
            .badge:hover {
                background: #fff;
                color: #000;
            }
        </style>
    </head>
    <body>
        <h1>CLKWISE - AI TIMING ANALYSIS</h1>
        <h2>SPONSOR INTEGRATIONS:</h2>
        
        <div>
            <span class="badge">GROQ ULTRA-FAST</span>
            <span class="badge">ROX AI AGENT</span>
            <span class="badge">COHERE MULTIMODAL</span>
            <span class="badge">GEMINI LANGUAGE</span>
            <span class="badge">CEREBRAS INFERENCE</span>
        </div>
        
        <p>✅ Simple sponsor badges working without emojis!</p>
        <p>Black and white theme applied successfully.</p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    print("Starting simple test server...")
    app.run(debug=True, host='127.0.0.1', port=8083)