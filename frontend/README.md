# CLKWISE Frontend

## Overview
This directory contains all frontend-related files for the CLKWISE AI-powered FPGA timing analysis platform.

## Structure
```
frontend/
├── templates/           # Flask/Jinja2 HTML templates
│   ├── upload.html     # Main upload interface with dual AI pipeline
│   ├── results.html    # Analysis results display
│   └── about.html      # About page
└── demo_ui.html        # Standalone demo UI (no backend required)
```

## Key Features

### 🎨 **Dual AI Pipeline UI**
- **Sequential Pipeline Visualization**: Cerebras → Cohere workflow
- **Professional Greyscale Theme**: Clean, modern design
- **Model Selector**: Interactive choice between AI models for chat
- **Responsive Design**: Works on desktop and mobile

### 📋 **Templates**

#### `upload.html`
- Main file upload interface
- HDL design files (.v, .sv, .vhd, .vhdl) upload
- Timing reports (.rpt, .log, .txt) upload  
- Dual AI pipeline visualization
- Interactive chat with model selection
- File drag & drop support

#### `results.html`
- Comprehensive analysis results display
- Pipeline status indicators (✓/✗ for each AI model)
- Combined AI analysis synthesis
- Individual model results fallback
- Interactive chat for follow-up questions

#### `about.html`
- Platform information and documentation
- Consistent styling with main interface

### 🎯 **Styling**
- **Color Scheme**: Professional greyscale with white text
- **Typography**: Inter font family for modern look
- **Layout**: Responsive grid system
- **Components**: Custom buttons, cards, badges
- **Animations**: Smooth transitions and hover effects

## Usage
These templates are designed to work with Flask backends. The backend should be configured to serve templates from this directory using:

```python
app = Flask(__name__, template_folder='../frontend/templates')
```

## Demo
The `demo_ui.html` file can be opened directly in a browser to preview the UI without running a backend server.