# CLKWISE Backend

## Overview
This directory contains all backend components for the CLKWISE AI-powered FPGA timing analysis platform.

## Structure
```
backend/
├── app/                    # Main application module
│   ├── web.py             # Primary Flask application
│   ├── llm_clients.py     # AI client management (Cerebras, Cohere)
│   ├── schemas.py         # Data schemas and validation
│   ├── timing_guardrails.py # Safety checks and validation
│   ├── ingest/            # Data ingestion modules
│   └── rules/             # Business logic and heuristics
├── working_app.py         # Complete functional demo app
├── minimal_test.py        # Minimal Flask server for testing
├── simple_server.py       # Basic server implementation
├── test_server.py         # Development test server
└── requirements.txt       # Python dependencies
```

## Key Features

### 🚀 **Dual AI Model Pipeline**
- **Cerebras Integration**: Fast initial analysis and optimization strategies
- **Cohere Integration**: Advanced reasoning and synthesis
- **Sequential Processing**: Cerebras → Cohere → Combined insights
- **Fallback Logic**: Graceful degradation if models unavailable

### ⚙️ **Core Components**

#### `app/web.py` - Primary Flask Application
- File upload handling (HDL code, timing reports)
- Dual model analysis orchestration
- Results processing and display
- Chat API with model selection
- Session management

#### `app/llm_clients.py` - AI Client Management
- Cerebras API integration
- Cohere API integration
- Client availability checking
- Response formatting and validation

#### `working_app.py` - Complete Demo
- Self-contained Flask application
- Mock analysis for testing
- All UI features functional
- No external API dependencies required

#### `minimal_test.py` - Testing Server
- Minimal Flask setup for UI testing
- Template rendering verification
- Quick development iteration

### 📋 **API Endpoints**

#### Core Routes
- `GET /` - Upload interface
- `POST /analyze` - File analysis with dual AI processing
- `GET /results` - Analysis results display
- `POST /chat` - Interactive chat with model selection

#### Additional Routes
- `GET /about` - About page
- `POST /analyze_document` - Document-specific analysis
- `POST /create_workflow` - Workflow generation
- `POST /rox_analyze` - ROX agent analysis

### 🔧 **Configuration**

#### Environment Variables
- `CEREBRAS_API_KEY` - Cerebras API authentication
- `COHERE_API_KEY` - Cohere API authentication
- `PORT` - Server port (default: 8089)

#### Dependencies
Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Main Application
```bash
cd backend
python -m app.web
```

### Running Demo Application
```bash
cd backend
python working_app.py
```

### Running Test Server
```bash
cd backend
python minimal_test.py
```

## Development
- All servers are configured to serve templates from `../frontend/templates/`
- Hot reload enabled in debug mode
- Comprehensive error handling and logging
- Mock data available for testing without API keys

## API Integration
The backend supports multiple AI providers:
- **Cerebras**: Fast inference for initial analysis
- **Cohere**: Advanced reasoning for synthesis
- **ROX Agent**: Messy data handling
- **Groq**: Optional ultra-fast inference
- **Gemini**: Optional natural language processing