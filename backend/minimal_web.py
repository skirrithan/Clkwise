#!/usr/bin/env python3
from flask import Flask, render_template_string

app = Flask(__name__)

UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>CLKWISE - AI TIMING ANALYSIS</title>
    <style>
        :root {
            --primary-bg: #000000;
            --secondary-bg: #111111;
            --tertiary-bg: #333333;
            --text-primary: #ffffff;
            --text-secondary: #737373;
            --border-color: #333333;
            --hover-bg: rgba(255, 255, 255, 0.07);
        }
        
        body {
            font-family: Arial, sans-serif;
            background: var(--primary-bg);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
        }
        
        .sponsor-badge {
            background: var(--secondary-bg);
            color: var(--text-primary);
            padding: 4px 12px;
            border-radius: 0;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            border: 1px solid var(--border-color);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            margin: 4px;
        }
        
        .sponsor-badge:hover {
            background: var(--text-primary);
            color: var(--primary-bg);
            transform: translateY(-1px);
        }
        
        .sponsor-showcase {
            background: var(--secondary-bg);
            border: 1px solid var(--border-color);
            padding: 25px;
            margin: 20px 0;
            text-align: center;
        }
        
        h1, h2 { text-align: center; }
        h4 { 
            color: var(--text-primary);
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
    </style>
</head>
<body>
    <h1>CLKWISE — AI TIMING DEBUGGER</h1>
    <h2>Multi-Sponsor Hackathon Prize Contender</h2>
    
    <div class="sponsor-showcase">
        <h4>POWERED BY LEADING AI TECHNOLOGIES</h4>
        <div>
            <span class="sponsor-badge">GROQ ULTRA-FAST</span>
            <span class="sponsor-badge">ROX AI AGENT</span>
            <span class="sponsor-badge">COHERE MULTIMODAL</span>
            <span class="sponsor-badge">GEMINI LANGUAGE</span>
            <span class="sponsor-badge">CEREBRAS INFERENCE</span>
        </div>
    </div>
    
    <div style="margin: 40px 0; text-align: center;">
        <h3>✅ SPONSOR INTEGRATION STATUS:</h3>
        <p>GROQ: Ultra-fast inference (Prize: $500 swag)</p>
        <p>COHERE: Multimodal AI (Prize: $500 cash + credits)</p>
        <p>ROX: Messy data handling (Prize: $10K!)</p>
        <p>GEMINI: Natural language (Prize: Google swag)</p>
        <p>CEREBRAS: Advanced inference (Prize: Keychron keyboards)</p>
    </div>
    
    <div style="text-align: center;">
        <h3>BLACK & WHITE THEME APPLIED ✅</h3>
        <p>Clean, professional sponsor badges without emojis</p>
        <p>Hover over the badges above to see the interaction effects!</p>
    </div>
</body>
</html>
'''

@app.route('/')
def upload_form():
    return render_template_string(UPLOAD_TEMPLATE)

if __name__ == '__main__':
    print("\\n" + "="*60)
    print("CLKWISE: AI-POWERED TIMING ANALYSIS PLATFORM")
    print("="*60)
    print("MINIMAL VERSION WITH SPONSOR BADGES")
    print("Web interface starting at: http://127.0.0.1:8084/")
    print("="*60)
    
    app.run(debug=True, host='127.0.0.1', port=8084)