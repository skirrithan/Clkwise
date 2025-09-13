#!/usr/bin/env python3

from flask import Flask, render_template
import os

# Create Flask app with correct template path
app = Flask(__name__, template_folder='../frontend/templates')
app.secret_key = 'clkwise-ui-demo'

@app.route('/')
def home():
    """Main upload page"""
    return render_template('upload.html')

@app.route('/results')
def results():
    """Results page with mock data"""
    mock_summary = {
        'wns': -0.5,
        'tns': -5.2,
        'ai_analysis': {
            'models_used': ['cerebras', 'cohere'],
            'combined_insights': '''**COMPREHENSIVE FPGA TIMING ANALYSIS**

**Root Cause Analysis:**
1. Critical path contains excessive logic levels (8 levels detected)
2. High routing congestion in center region causing 45% routing delay
3. Clock skew issues between related flops (0.3ns difference)

**Optimization Strategy:**
1. **Pipeline Insertion**: Add registers to break critical path into 2-3 stages
2. **Placement Optimization**: Use AREA_GROUP constraints to cluster logic
3. **Clock Domain Optimization**: Implement proper synchronizers

**Implementation Priority:**
1. HIGH: Pipeline critical arithmetic operations
2. MEDIUM: Optimize placement with LOC constraints
3. LOW: Fine-tune I/O timing with OFFSET constraints

**Expected Results:**
- WNS improvement: +0.8ns to +1.2ns
- TNS improvement: Complete elimination of violations
- Timing closure confidence: 95%

*Analysis completed using Cerebras + Cohere dual AI pipeline*'''
        }
    }
    
    mock_violations = [{
        'slack': -0.5,
        'startpoint': 'cpu_core/alu_reg[31]',
        'endpoint': 'cpu_core/result_reg[31]',
        'levels_of_logic': 8,
        'routing_pct': 45,
        'tips': [
            'Add pipeline registers between ALU stages',
            'Use DSP48 blocks for multiplication operations', 
            'Implement proper timing constraints'
        ]
    }]
    
    return render_template('results.html',
                         summary=mock_summary,
                         violations=mock_violations,
                         code_files=['cpu_core.v'],
                         log_files=['timing_report.rpt'])

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8095))
    print(f"🚀 CLKWISE Dual AI Analysis Platform")
    print(f"🌐 Starting server at: http://127.0.0.1:{port}/")
    print(f"📁 Frontend templates: ../frontend/templates/")
    print("=" * 50)
    
    try:
        app.run(debug=True, host='127.0.0.1', port=port, threaded=True)
    except Exception as e:
        print(f"❌ Server failed: {e}")