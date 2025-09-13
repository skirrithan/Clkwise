from flask import Flask, request, render_template, redirect, url_for
import tempfile
import os
from ingest.parse_vivado import parse_summary
from rules.heuristics import suggest_fix

app = Flask(__name__)

@app.route('/')
def upload_form():
    return render_template('upload.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.rpt') as tmp:
            file.save(tmp.name)
            rpt = open(tmp.name, 'r', errors='ignore').read()
            os.unlink(tmp.name)
        summary = parse_summary(rpt)
        violations = summary['violations']
        for v in violations:
            v['tips'] = suggest_fix(v)
        return render_template('results.html', summary=summary, violations=violations)

if __name__ == '__main__':
    app.run(debug=True)
