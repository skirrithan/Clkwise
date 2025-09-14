# Clkwise Enhanced Pipeline Architecture

## 🏗️ Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               CLKWISE ENHANCED PIPELINE                          │
│                          Production-Ready AI Analysis                           │
└─────────────────────────────────────────────────────────────────────────────────┘

📄 INPUT LAYER
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   .rpt/.log  │    │    .v/.sv    │    │  User Chat   │
│ Timing Files │    │  HDL Source  │    │   Messages   │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       ▼                   ▼                   ▼

🔧 PARSING & VALIDATION LAYER
┌────────────────────────────────────────────────────────────┐
│                   app/ingest/parse_vivado.py                │
│  • Extract violations, paths, delays                       │
│  • Parse metadata (WNS, TNS, device)                      │
│  • Normalize data structures                               │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼

📊 DATA TRANSFORMATION LAYER  
┌────────────────────────────────────────────────────────────┐
│                      app/schemas.py                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ TimingViolation │  │ ViolationPrompt │  │  LlmResult   │ │
│  │ (Raw Parser)    │  │ (LLM Input)     │  │ (Validated   │ │
│  │                 │  │                 │  │  Output)     │ │
│  │ • path_id       │→ │ • clock         │→ │ • issue_class│ │
│  │ • slack_ns      │  │ • slack_ns      │  │ • root_cause │ │
│  │ • startpoint    │  │ • startpoint    │  │ • fixes[]    │ │
│  │ • endpoint      │  │ • endpoint      │  │ • confidence │ │
│  │ • logic_levels  │  │ • logic_levels  │  │ • metadata   │ │
│  │ • cell_arcs[]   │  │ • worst_cells[] │  └──────────────┘ │
│  │ • net_arcs[]    │  │ • worst_nets[]  │                   │
│  └─────────────────┘  │ • hints[]       │                   │
│                       └─────────────────┘                   │
│            Pydantic Validation & Serialization             │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼

🧠 AI ANALYSIS LAYER
┌────────────────────────────────────────────────────────────┐
│                   app/llm_clients.py                       │
│                                                            │
│  ┌─────────────────┐              ┌─────────────────┐      │
│  │ CerebrasClient  │              │  CohereClient   │      │
│  │ (Primary)       │              │  (Fallback)     │      │
│  │                 │              │                 │      │
│  │ • llama3.1-70b  │              │ • command-r-plus│      │
│  │ • <100ms        │              │ • JSON reliable │      │
│  │ • OpenAI API    │              │ • Schema strict │      │
│  └─────────────────┘              └─────────────────┘      │
│           ▲                                  ▲             │
│           │         LlmOrchestrator         │             │
│           └─────────────┬────────────────────┘             │
│                         │                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ • Unified json_chat() interface                     │    │
│  │ • Schema validation with one-shot repair           │    │
│  │ • Automatic failover: Cerebras → Cohere → Heuristic│    │
│  │ • Processing time tracking                          │    │
│  │ • Confidence scoring                                │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼

🛡️ GUARDRAILS & VALIDATION LAYER
┌────────────────────────────────────────────────────────────┐
│                app/timing_guardrails.py                    │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Expert Heuristics                      │    │
│  │                                                     │    │
│  │  Logic Levels ≥ 8    → Pipeline Fix Required       │    │
│  │  Routing % ≥ 60      → Floorplan Fix Required      │    │
│  │  High Fanout Hints   → Replication Fix Required    │    │
│  │  Clock Domain Issues → Constraint Review Required  │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │             Validation & Enhancement                │    │
│  │                                                     │    │
│  │  • validate_llm_suggestions()                      │    │
│  │  • enhance_llm_result()                            │    │
│  │  • create_fallback_result()                        │    │
│  │  • confidence_scoring()                            │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼

🌐 WEB INTERFACE LAYER
┌────────────────────────────────────────────────────────────┐
│                      app/web.py                            │
│                                                            │
│  Route: /analyze                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  1. File Upload & Parsing                           │    │
│  │  2. Violation Extraction                            │    │
│  │  3. Structured Analysis (per violation)            │    │
│  │  4. Guardrails Validation                           │    │
│  │  5. Results Presentation                            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                            │
│  Route: /chat                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  • Context-aware Q&A                               │    │
│  │  • Violation-specific analysis                     │    │
│  │  • Real-time confidence display                    │    │
│  │  • Enhanced markdown formatting                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          ▼

📤 OUTPUT LAYER
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Web UI     │    │ JSON API     │    │ Chat Interface│
│ • Violation  │    │ • Structured │    │ • Interactive│
│   Tables     │    │   Results    │    │   Analysis   │
│ • Fix Cards  │    │ • Confidence │    │ • Context    │
│ • Confidence │    │   Scores     │    │   Aware      │
│   Indicators │    │ • Metadata   │    │ • Markdown   │
└──────────────┘    └──────────────┘    └──────────────┘
```

## 🔄 Data Flow Example

### Input → Analysis → Output

```
📄 INPUT
timing_report.rpt:
  Path: u_dsp/mult_reg[31]/Q → u_core/add_reg[31]/D
  Slack: -2.5ns
  Logic Levels: 12
  Routing: 65%

       ↓ parse_vivado.py

📊 STRUCTURED DATA  
{
  "path_id": "P0001",
  "slack_ns": -2.5,
  "startpoint": {"name": "u_dsp/mult_reg[31]/Q"},
  "endpoint": {"name": "u_core/add_reg[31]/D"},
  "levels_of_logic": 12,
  "net_arcs": [{"routing_pct": 65}]
}

       ↓ schemas.py conversion

🎯 LLM INPUT
{
  "clock": "clk_250mhz",
  "slack_ns": -2.5,
  "startpoint": "u_dsp/mult_reg[31]/Q",
  "endpoint": "u_core/add_reg[31]/D", 
  "levels_of_logic": 12,
  "worst_nets": [{"routing_pct": 65}],
  "hints": ["deep arithmetic", "high routing delay"]
}

       ↓ LLM Analysis (Cerebras/Cohere)

🧠 AI ANALYSIS
{
  "issue_class": "setup",
  "probable_root_cause": [
    "deep combinational logic (12 levels)",
    "excessive routing delay (65%)"
  ],
  "suggested_fixes": [
    {
      "type": "retime_or_pipeline",
      "scope": "u_dsp",
      "detail": "Insert 3 pipeline stages to reduce logic depth"
    },
    {
      "type": "floorplan", 
      "scope": "placement",
      "detail": "Add pblock to co-locate u_dsp and u_core"
    }
  ],
  "expected_effect_ns": 3.2,
  "confidence_score": 0.85
}

       ↓ Guardrails validation & enhancement

🛡️ VALIDATED OUTPUT
• Confidence: 85% (High data quality + complete analysis)
• Missing risks added: "Pipeline adds 3 cycle latency"
• Verification steps added: "Update protocol timing"

       ↓ Web interface formatting

📱 USER DISPLAY
**Analysis of u_dsp/mult_reg[31]/Q → u_core/add_reg[31]/D**

**Issue Classification:** Setup

**Root Causes:**
• deep combinational logic (12 levels)  
• excessive routing delay (65%)

**Recommended Fixes:**
1. ⏱️ **Retime Or Pipeline** in `u_dsp`
   Insert 3 pipeline stages to reduce logic depth

2. 📍 **Floorplan** in `placement` 
   Add pblock to co-locate u_dsp and u_core

**⚠️ Implementation Risks:**
• Pipeline adds 3 cycle latency - update protocol timing

*Analysis confidence: 85% | Processing: 145ms | Model: cerebras-llama3.1-70b*
```

## 🔧 Component Integration

### File Structure
```
Clkwise-2/
├── app/
│   ├── schemas.py              # Data contracts & validation
│   ├── llm_clients.py          # Cerebras/Cohere adapters  
│   ├── timing_guardrails.py    # Expert heuristics
│   ├── web.py                  # Enhanced Flask app
│   ├── ingest/
│   │   └── parse_vivado.py     # Original parser (enhanced)
│   └── rules/
│       └── heuristics.py       # Original rules (integrated)
├── templates/                  # Web UI templates
├── test_basic.py              # Validation tests
├── requirements.txt           # Updated dependencies
└── ENHANCED_PIPELINE.md       # This documentation
```

### Key Integration Points

1. **Parser → Schemas**: `TimingViolation.to_prompt()`
2. **Schemas → LLM**: `ViolationPrompt.to_dict()`
3. **LLM → Validation**: `validate_llm_output()`
4. **Guardrails → Enhancement**: `enhance_llm_result()`
5. **Web → Pipeline**: `orchestrator.analyze_violation()`

---

This architecture provides **production-grade robustness** while maintaining the **simplicity** of your original design. Each layer has clear responsibilities, comprehensive error handling, and graceful degradation paths. 🎯