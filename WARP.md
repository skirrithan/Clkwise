# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Clkwise is an AI timing debugger for chip design that parses Vivado timing reports and suggests heuristic fixes for timing violations in FPGA designs. The project consists of a CLI tool, web interface, and hardware design examples.

## Common Commands

### Running the CLI Tool
```bash
# Parse a timing report and get fix suggestions
python app/cli.py <path-to-timing-report.rpt>

# Example with sample report
python app/cli.py sample.rpt
```

### Web Interface
```bash
# Install Flask dependency (if not installed)
pip install flask

# Run the web application
python -m app.web

# Access at http://127.0.0.1:5000/
```

### Hardware Simulation & Synthesis
```bash
# Clean previous builds
make clean

# Run Vivado synthesis and generate timing reports
make vivado

# Note: Requires Vivado installation and Windows/WSL environment per Makefile
```

### Testing Individual Modules
```bash
# Test the Vivado parser directly
python app/ingest/parse_vivado.py sample.rpt

# This will create sample.json with parsed data
```

## Architecture Overview

### Core Components

**CLI Layer (`app/cli.py`)**
- Main entry point that orchestrates parsing and analysis
- Takes timing report files as input and outputs violations with suggestions

**Parsing Layer (`app/ingest/parse_vivado.py`)**
- Extracts timing metrics from Vivado reports using regex patterns
- Parses WNS (Worst Negative Slack), TNS (Total Negative Slack), and violation paths
- Identifies startpoint, endpoint, slack values, logic levels, and routing percentages

**Heuristics Engine (`app/rules/heuristics.py`)**
- Contains timing closure heuristics based on path characteristics
- Suggests fixes like pipelining, DSP inference, routing optimization, CDC handling
- Uses thresholds (6+ logic levels, 60%+ routing delay) to trigger specific recommendations

**Web Interface (`app/web.py`)**
- Flask-based web app for interactive report upload and analysis
- Handles file uploads, processes reports, and displays results via HTML templates

### Hardware Design Files

**RTL (`hw/src/top.sv`)**
- Example SystemVerilog design with intentionally long combinational paths
- Demonstrates timing-critical scenarios: multiple multipliers and addition chains
- Used for generating sample timing violations

**Constraints (`hw/constrs/top.xdc`)**
- Timing constraints with aggressive 2ns clock period (500 MHz)
- Includes input/output delays for realistic timing analysis

**Build Script (`hw/run_vivado.tcl`)**
- Complete Vivado flow: synthesis → place → route → timing analysis
- Generates multiple report types including timing summary and design analysis
- Automatically fails if timing is not met (negative slack)

### Data Flow

1. **Input**: Vivado timing report (.rpt files)
2. **Parse**: Extract timing metrics and violation paths using regex
3. **Analyze**: Apply heuristic rules based on path characteristics
4. **Output**: Ranked violations with specific fix suggestions

## Key Patterns & Conventions

### Timing Analysis Heuristics
- **Logic Level Threshold**: 6+ levels triggers pipelining suggestions
- **Routing Threshold**: 60%+ routing delay suggests placement/fanout issues
- **DSP Detection**: Looks for "mul" in path descriptions to suggest DSP48 usage
- **CDC Detection**: Identifies clock domain crossing issues from path descriptions

### Report Parsing Strategy
- Uses regex patterns to extract structured data from free-form Vivado reports
- Handles variations in report formatting with optional matches
- Preserves raw path data (first 2000 chars) for advanced analysis

### File Organization
- `app/` contains all Python application code
- `hw/` contains hardware design and synthesis scripts  
- `templates/` contains HTML templates for web interface
- `data/` is created dynamically during Vivado runs for reports/bitstreams

## Development Notes

### Adding New Heuristics
- Extend `suggest_fix()` function in `app/rules/heuristics.py`
- Use path characteristics: slack, levels_of_logic, routing_pct, raw text
- Add pattern matching against raw path data for specific scenarios

### Testing Parsing Logic
- Use `sample.rpt` for basic parser testing
- Generate new reports via `make vivado` for comprehensive testing
- Parser outputs JSON format for integration with other tools

### Multi-Platform Considerations
- Makefile currently configured for Windows/WSL Vivado installation
- Python components are cross-platform compatible
- Web interface runs on any system with Flask

## Integration Architecture

The project is designed to integrate with multiple external platforms as outlined in the sponsor requirements, including DynamoDB for storage, Databricks for ML processing, Groq for LLM inference, and various development tools for collaborative debugging workflows.