# Clkwise — AI Timing Debugger for Chip Design

A CLI tool for parsing Vivado timing reports and suggesting heuristic fixes for timing violations in FPGA designs. This project aims to accelerate the timing closure process by providing automated analysis and actionable suggestions.

## Features

- Parse Vivado timing summary reports
- Extract key metrics: Worst Negative Slack (WNS), Total Negative Slack (TNS), and violation paths
- Suggest fixes for the top timing violations using heuristics
- Command-line interface for easy integration into design workflows

## Usage

Run the CLI tool with a Vivado timing report file:

```bash
python app/cli.py <path-to-timing-report.rpt>
```

Example output:
```
WNS=-0.123  TNS=-1.456  paths=10

Path 1  slack=-0.123  levels=5  routing%=20.5
  - Reduce logic levels by pipelining
  - Optimize routing for critical path

Path 2  slack=-0.145  levels=6  routing%=15.2
  - Use faster cells for high-fanout nets
  - Balance load on clock trees
...
```

## Web Front End

A web interface is now available to upload Vivado timing reports and view analysis results interactively.

### Usage

1. Install Flask if not already installed:

```
pip install flask
```

2. Run the web app:

```
python -m app.web
```

3. Open your browser and go to:

```
http://127.0.0.1:5000/
```

4. Upload your Vivado timing report file (.rpt) and view the analysis results.

## Project Structure

- `app/cli.py`: Main CLI script for parsing reports and suggesting fixes
- `app/ingest/parse_vivado.py`: Parser for Vivado timing reports
- `app/rules/heuristics.py`: Heuristic rules for suggesting timing fixes
- `app/web.py`: Flask web app for interactive report upload and analysis
- `hw/`: Hardware-related files (Verilog, constraints, TCL scripts)

## Sponsor Requirements Mapping

To align with the sponsor categories and maximize chances of winning prizes, here's how Chronos addresses each requirement:

### 📡 CSE — Core Network Dataset Focus
- Treat chip modules and connections as a “network” graph.
- Collect timing congestion data between modules and build a network traffic-style dataset.
- Analyze “network flow bottlenecks” across the chip’s timing paths.

### 💻 Warp — Developer Terminal Tool
- Create a CLI for the AI debugger inside Warp.
- Show real-time inline annotated timing violations as you type.
- Use Warp multiplayer sessions for collaborative chip debugging.

### ✨ Gemini — Fallback/Natural Language Summarization
- Use Gemini to summarize long static timing analysis (STA) reports.
- Convert cryptic error logs into plain language action items.

### ⚡ Groq — Real-Time Engine
- Deploy your custom Verilog-timing LLM on Groq hardware.
- Get millisecond-latency feedback on timing fixes as engineers iterate.

### 🚀 Databricks — Best Use of Databricks
- Store and preprocess RTL/timing datasets at scale.
- Train/fine-tune timing-debug LLMs collaboratively on Databricks notebooks.

### ☁️ AWS — Best Use of DynamoDB
- Store submitted designs and timing logs in DynamoDB.
- Trigger analysis pipelines using DynamoDB Streams on each upload.

### 🛠 Graphite — Engineering Dream Team
- Generate AI timing-fix patches as Graphite pull requests.
- Track contributions, reviews, and approvals visually.

### 🤖 Rox — Best AI Agent
- Rox agent orchestrates: Detect timing issue → Ask LLM → Generate fix → Commit → Verify.

### 💬 Cohere — LLMs for Developer Tools or Agents
- Use Cohere to create vector search on Verilog/timing snippets.
- Use Cohere as a fast lightweight fallback model to retrieve known timing fixes.

## System Architecture

See `architecture_diagram.md` for a visual representation of how the platforms connect in the system.

## Contributing

Contributions are welcome! Please open issues or pull requests for improvements.

## License

[Add license information if applicable]
