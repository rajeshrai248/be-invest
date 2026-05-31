# be-invest — Business Flow Diagram

> **Audience:** Business stakeholders
> **Purpose:** End-to-end view of how data flows through the platform, from broker source data to user-facing outputs.

---

```mermaid
flowchart TD
    %% ACTORS
    USER(["🧑‍💻 End User"])
    ADMIN(["🔧 Administrator"])
    SUB(["📬 Email Subscribers"])

    %% LAYER 1 — Security & API Gateway
    subgraph GATEWAY["🔒 Security & API Gateway"]
        direction TB
        RL["Rate Limiter"] --> CORS["CORS Guard"]
    end

    %% LAYER 2 — API Endpoints
    subgraph ENDPOINTS["🔌 REST API Endpoints (FastAPI)"]
        direction LR
        EP1["📥 /refresh-and-analyze"] ~~~ EP2["📊 /cost-comparison-tables"] ~~~ EP3["💬 /chat"]
        EP4["📰 /news"] ~~~ EP5["📈 /financial-analysis"] ~~~ EP6["📧 /send-email-report"]
    end

    %% LAYER 3 — Data Ingestion Pipeline
    subgraph INGESTION["📥 Data Ingestion Pipeline"]
        direction TB
        BROKERS["🏦 Belgian Brokers\nDegiro · Bolero · Keytrade\nING · Rebel · Revolut · Trade Republic"]
        SCRAPER["🕷️ Web Scraper\nPlaywright + Requests"]
        LLM_EXTRACT["🤖 AI Extraction\nClaude Sonnet 4.6 / GPT-4o · temp=0.0"]
        LLM_STRUCT["🤖 AI Structuring\nClaude Sonnet 4.6 · temp=0.0"]
        FEE_DB[("💾 fee_rules.json")]
        BROKERS -->|"PDFs & pages"| SCRAPER -->|"Raw text"| LLM_EXTRACT
        LLM_EXTRACT -->|"Fee records"| LLM_STRUCT -->|"Validated rules"| FEE_DB
    end

    %% LAYER 4 — Deterministic Fee Engine
    subgraph ENGINE["⚙️ Deterministic Fee Engine"]
        direction TB
        FEE_CALC["🧮 Fee Calculator\nflat · tiered · % · base+slice"]
        PERSONA["👤 Persona Calculator\nPassive · Moderate · Active"]
        TABLES["📋 Comparison Tables\n€50 – €50k × 7 brokers"]
        NOTES["📝 Broker Notes\ncustody · FX · connectivity"]
        FEE_CALC --> TABLES & PERSONA & NOTES
    end

    %% LAYER 5 — AI Services
    subgraph AI["🤖 AI Services"]
        direction TB
        AI_CHAT["💬 Chat AI\nGroq / Llama 3.3 70B"]
        AI_ANALYSIS["📈 Analysis AI\nClaude Sonnet 4.6"]
    end

    %% LAYER 6 — News Intelligence
    subgraph NEWS_SYS["📰 News Intelligence"]
        direction TB
        NEWS_SCHED["⏰ Auto-Scheduler (24h)"]
        NEWS_SCRAPER["🕷️ News Scraper"]
        NEWS_STORE[("💾 news.jsonl")]
        NEWS_CACHE["⚡ File Cache (24h TTL)"]
        NEWS_SCHED -->|"24h trigger"| NEWS_SCRAPER -->|"Save"| NEWS_STORE -->|"Cache"| NEWS_CACHE
    end

    %% LAYER 7 — Email Service
    subgraph EMAIL_SYS["📧 Weekly Email Reports"]
        direction TB
        EMAIL_SCHED["⏰ Weekly Task Scheduler\nMon 09:00 local"]
        EMAIL_BUILD["🏗️ HTML Report Builder"]
        SMTP["📮 Gmail SMTP"]
        EMAIL_SCHED -->|"Schedule"| EMAIL_BUILD -->|"Send"| SMTP
    end

    %% LAYER 8 — Quality Assurance
    subgraph QA["✅ AI Quality Assurance"]
        direction LR
        JUDGE["⚖️ LLM-as-Judge\nGemini 2.5 Pro"] -->|"Score 0–1"| LANGFUSE["📊 Langfuse\nObservability"]
    end

    %% PRIMARY FLOWS
    USER -->|"Request"| RL
    ADMIN -->|"Trigger"| RL
    CORS --> EP1 & EP2 & EP3 & EP4 & EP5 & EP6

    %% Flow A — Fee Refresh
    EP1 -->|"Refresh"| INGESTION

    %% Flow B — Cost Tables
    EP2 -->|"Load"| FEE_CALC
    FEE_DB -->|"Rules"| FEE_CALC
    TABLES & PERSONA & NOTES -->|"Results"| EP2 -->|"Tables + notes"| USER

    %% Flow C — Chat
    EP3 --> FEE_CALC -->|"Fees"| AI_CHAT
    FEE_DB -->|"Context"| AI_CHAT -->|"Answer"| EP3 -->|"Response"| USER

    %% Flow D — Analysis
    EP5 --> TABLES -->|"Data"| AI_ANALYSIS -->|"Report"| EP5 -->|"Analysis"| USER

    %% Flow E — News
    EP4 --> NEWS_CACHE -->|"Articles"| EP4 -->|"News"| USER

    %% Flow F — Email
    EP6 --> EMAIL_BUILD
    TABLES & PERSONA -->|"Data"| EMAIL_BUILD
    SMTP -->|"Digest"| SUB

    %% Flow G — QA (background)
    EP2 & EP3 & EP5 -.->|"Review"| JUDGE

    %% STYLING
    classDef actor     fill:#1A73E8,stroke:#0D47A1,color:#FFF,rx:12
    classDef gateway   fill:#E8EAF6,stroke:#3949AB,color:#1A237E
    classDef endpoint  fill:#E3F2FD,stroke:#1565C0,color:#0D1B5E
    classDef datastore fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    classDef llm       fill:#FFF3E0,stroke:#E65100,color:#BF360C
    classDef engine    fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef scheduler fill:#FCE4EC,stroke:#AD1457,color:#880E4F
    classDef quality   fill:#F9FBE7,stroke:#827717,color:#33691E

    class USER,ADMIN,SUB,BROKERS actor
    class RL,CORS gateway
    class EP1,EP2,EP3,EP4,EP5,EP6 endpoint
    class FEE_DB,NEWS_STORE datastore
    class LLM_EXTRACT,LLM_STRUCT,AI_CHAT,AI_ANALYSIS llm
    class SCRAPER,NEWS_SCRAPER,FEE_CALC,PERSONA,TABLES,NOTES engine
    class NEWS_SCHED,EMAIL_SCHED,EMAIL_BUILD,SMTP,NEWS_CACHE scheduler
    class JUDGE,LANGFUSE quality
```

---

## Flow Summary

| Flow | Trigger | Key Steps | Output |
|------|---------|-----------|--------|
| **A · Fee Refresh** | Admin runs `/refresh-and-analyze` | Scrape PDFs → Claude/GPT-4o extract → Claude structure → Save | Updated `fee_rules.json` |
| **B · Fee Comparison** | User requests `/cost-comparison-tables` | Load rules → Compute fees → Build tables + notes | Fee matrix + TCO rankings |
| **C · AI Chat** | User posts question to `/chat` | Parse intent → Pre-compute fees → Groq/Llama answer | Natural language response |
| **D · Financial Analysis** | User calls `/financial-analysis` | Load tables → Claude narrative → Return report | Written analysis |
| **E · News Feed** | User calls `/news` | Check 24h cache → Serve recent articles | Broker news items |
| **F · Weekly Email** | Monday scheduler or `/send-email-report` | Build HTML → Gmail SMTP → Deliver | Subscriber email digest |
| **G · Quality Check** | Runs in background after every AI response | Gemini Judge reviews output → Score logged | Groundedness score in Langfuse |

---

## Key Design Principles

- **Deterministic-first:** Fees are computed by pure Python rules (no AI guessing) — AI is only used for extraction, structuring, and natural language output.
- **AI-as-a-Tool:** Separate LLMs handle different jobs: Claude/GPT-4o for extraction, Claude for structuring and analysis, Groq/Llama for chat speed.
- **Continuous Quality:** Every AI-generated response is independently scored by a fourth model (Gemini Judge) and logged to Langfuse.
- **Scheduled Automation:** News scraping is API-managed; weekly email should run through the standalone scheduler script so host sleep/restart behavior is explicit.
- **Security by default:** All requests pass through rate limiting and IP blocking before reaching any business logic.
