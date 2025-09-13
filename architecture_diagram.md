# System Architecture Diagram for Chronos — AI Timing Debugger

```mermaid
graph TD
    A[User Uploads RTL + Timing Report] --> B[DynamoDB Storage]
    B --> C[DynamoDB Streams Trigger]
    C --> D[AI Analysis Job on Databricks]
    D --> E[LLM Inference on Groq]
    E --> F[Gemini Summarization]
    F --> G[Generate Fixes via Cohere Retrieval]
    G --> H[AI Agent (Rox) Orchestrates]
    H --> I[Graphite PR Creation]
    I --> J[Warp CLI Interface]
    J --> K[Real-time Feedback Loop]
    K --> A

    subgraph "Data & ML Layer"
        D
        E
    end

    subgraph "Frontend Layer"
        J
    end

    subgraph "Backend Layer"
        B
        C
    end

    subgraph "Collaboration Layer"
        I
    end

    subgraph "AI Layer"
        H
        F
        G
    end
