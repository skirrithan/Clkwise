#!/usr/bin/env python3

from flask import Flask, render_template
import os

app = Flask(__name__, template_folder='templates')
app.secret_key = 'test'

@app.route('/')
def home():
    try:
        return render_template('upload.html')
    except Exception as e:
        return f'<h1>Template Error</h1><p>{str(e)}</p><p>But Flask is working!</p>'

@app.route('/test')
def test():
    return '<h1>✅ CLKWISE Flask Server is Working!</h1><p>This confirms Flask can run properly.</p>'

if __name__ == '__main__':
    port = 8093
    print(f"🚀 Starting minimal CLKWISE test server on http://127.0.0.1:{port}/")
    print(f"📝 Test URL: http://127.0.0.1:{port}/test")
    try:
        app.run(debug=True, host='127.0.0.1', port=port, threaded=True)
    except Exception as e:
        print(f"❌ Server failed to start: {e}")