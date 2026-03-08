# be-invest — Business Flow Diagram

> **Audience:** Business stakeholders
> **Purpose:** End-to-end view of how data flows through the platform, from broker source data to user-facing outputs.

---

```mermaid
flowchart TD

    %% ══════════════════════════════════════════════════════
    %% ACTORS
    %% ══════════════════════════════════════════════════════

    USER(["🧑‍💻  End User\nFrontend / Mobile App"])
    ADMIN(["🔧  Administrator\nManual Trigger"])
    SUB(["📬  Email Subscribers\nWeekly Recipients"])

    %% ══════════════════════════════════════════════════════
    %% LAYER 1 — SECURITY & API GATEWAY
    %% ══════════════════════════════════════════════════════

    subgraph GATEWAY["  🔒  Security & API Gateway  "]
        direction TB
        RL["Rate Limiter\nBlocks suspicious IPs,\nlimits requests/min"]
        CORS["CORS Guard\nAllows only approved\nfrontend origins"]
        RL --> CORS
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 2 — API ENDPOINTS
    %% ══════════════════════════════════════════════════════

    subgraph ENDPOINTS["  🔌  REST API Endpoints  (FastAPI)  "]
        direction LR
        EP1["📥  POST\n/refresh-and-analyze\nRebuild fee rules\nfrom broker sources"]
        EP2["📊  GET\n/cost-comparison-tables\nFee tables for all\nbrokers & amounts"]
        EP3["💬  POST\n/chat\nAI-powered Q&A\nchatbot"]
        EP4["📰  GET\n/news\nBroker news &\nmarket updates"]
        EP5["📈  GET\n/financial-analysis\nPortfolio cost\nnarrative"]
        EP6["📧  POST\n/send-email-report\nManual email\ntrigger"]
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 3 — DATA INGESTION PIPELINE
    %% ══════════════════════════════════════════════════════

    subgraph INGESTION["  📥  Data Ingestion Pipeline  "]
        direction TB
        BROKERS["🏦  Belgian Broker Sources\nDegiro · Bolero · Keytrade\nING · Rebel · Revolut · Trade Republic\n\nWebsites & Published PDFs"]

        SCRAPER["🕷️  Web Scraper\nPlaywright + Requests\nDownloads fee tariff PDFs\nand public web pages"]

        LLM_EXTRACT["🤖  AI Extraction\nGPT-4o  ·  temp=0.0\nReads raw PDF text,\nextracts fee records as JSON"]

        LLM_STRUCT["🤖  AI Structuring\nClaude Sonnet  ·  temp=0.0\nConverts raw records into\nvalidated fee rule objects"]

        FEE_DB[("💾  fee_rules.json\nCentral Fee Rules Store\nBroker × Instrument × Exchange\nFee patterns + hidden costs")]

        BROKERS -->|"Tariff PDFs & web pages"| SCRAPER
        SCRAPER -->|"Raw text content"| LLM_EXTRACT
        LLM_EXTRACT -->|"Structured fee records"| LLM_STRUCT
        LLM_STRUCT -->|"Validated fee rules & hidden costs"| FEE_DB
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 4 — DETERMINISTIC FEE ENGINE
    %% ══════════════════════════════════════════════════════

    subgraph ENGINE["  ⚙️  Deterministic Fee Engine  "]
        direction TB
        FEE_CALC["🧮  Fee Calculator\nPure Python — no AI\nComputes exact fees using rule patterns:\nflat · tiered · percentage · base+slice"]

        PERSONA["👤  Persona Calculator\nProfiles 3 investor types:\nPassive Investor · Moderate · Active Trader\nAnnual Total Cost of Ownership (TCO)"]

        TABLES["📋  Comparison Tables\nFee matrix for all\namount sizes (€50 – €50,000)\nacross all 7 brokers"]

        NOTES["📝  Broker Notes Builder\nHidden costs summary:\ncustody · FX · connectivity\ndividend · subscription fees"]

        FEE_CALC --> TABLES
        FEE_CALC --> PERSONA
        FEE_CALC --> NOTES
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 5 — AI SERVICES
    %% ══════════════════════════════════════════════════════

    subgraph AI["  🤖  AI Services  "]
        direction TB
        AI_CHAT["💬  Chat AI\nGroq / Llama 3.3 70B  ·  temp=0.3\nNatural language answers\nGrounded in pre-computed fees"]

        AI_ANALYSIS["📈  Analysis AI\nClaude Sonnet  ·  temp=0.0\nNarrative portfolio analysis\nbased on fee tables & TCO rankings"]
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 6 — NEWS INTELLIGENCE
    %% ══════════════════════════════════════════════════════

    subgraph NEWS_SYS["  📰  News Intelligence  "]
        direction TB
        NEWS_SCHED["⏰  Auto-Scheduler\nRuns every 24 hours\nin background thread"]

        NEWS_SCRAPER["🕷️  News Scraper\nFetches broker announcements,\npress releases & market news"]

        NEWS_STORE[("💾  news.jsonl\nNews Store\nPersistent log of\nall broker news items")]

        NEWS_CACHE["⚡  File Cache\n24-hour TTL\nAvoids redundant\nscraping"]

        NEWS_SCHED -->|"Triggers every 24h"| NEWS_SCRAPER
        NEWS_SCRAPER -->|"Saves new articles"| NEWS_STORE
        NEWS_STORE -->|"Cached for serving"| NEWS_CACHE
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 7 — EMAIL SERVICE
    %% ══════════════════════════════════════════════════════

    subgraph EMAIL_SYS["  📧  Weekly Email Reports  "]
        direction TB
        EMAIL_SCHED["⏰  Weekly Scheduler\nEvery Monday 09:00 UTC\nBackground daemon thread"]

        EMAIL_BUILD["🏗️  HTML Report Builder\nAssembles fee comparison tables,\nTCO persona rankings,\nand broker logo banners"]

        SMTP["📮  Gmail SMTP\nTLS-encrypted delivery\nto subscriber list"]

        EMAIL_SCHED -->|"Fires on schedule"| EMAIL_BUILD
        EMAIL_BUILD -->|"Sends HTML email"| SMTP
    end

    %% ══════════════════════════════════════════════════════
    %% LAYER 8 — QUALITY ASSURANCE
    %% ══════════════════════════════════════════════════════

    subgraph QA["  ✅  AI Quality Assurance  "]
        direction LR
        JUDGE["⚖️  LLM-as-Judge\nGemini 2.5 Pro\nEvaluates all AI responses\nfor factual groundedness"]

        LANGFUSE["📊  Langfuse Observability\nScores: 0.0 = hallucination\n0.5 = partial  ·  1.0 = grounded\nAll LLM calls traced & scored"]

        JUDGE -->|"Groundedness score (0–1)"| LANGFUSE
    end

    %% ══════════════════════════════════════════════════════
    %% PRIMARY FLOWS — User to Gateway
    %% ══════════════════════════════════════════════════════

    USER -->|"API request"| RL
    ADMIN -->|"Trigger refresh\nor email"| RL
    CORS -->|"Validated request"| EP1
    CORS -->|"Validated request"| EP2
    CORS -->|"Validated request"| EP3
    CORS -->|"Validated request"| EP4
    CORS -->|"Validated request"| EP5
    CORS -->|"Validated request"| EP6

    %% ══════════════════════════════════════════════════════
    %% FLOW A — Fee Rule Refresh
    %% ══════════════════════════════════════════════════════

    EP1 -->|"Kick off pipeline"| INGESTION

    %% ══════════════════════════════════════════════════════
    %% FLOW B — Cost Comparison Tables
    %% ══════════════════════════════════════════════════════

    EP2 -->|"Load rules"| FEE_CALC
    FEE_DB -->|"Fee rules & hidden costs"| FEE_CALC
    TABLES -->|"Fee matrix"| EP2
    PERSONA -->|"TCO rankings"| EP2
    NOTES -->|"Hidden cost notes"| EP2
    EP2 -->|"Returns tables + notes"| USER

    %% ══════════════════════════════════════════════════════
    %% FLOW C — AI Chat Q&A
    %% ══════════════════════════════════════════════════════

    EP3 -->|"Extract broker, amount, instrument"| FEE_CALC
    FEE_DB -->|"Fee context & rules"| AI_CHAT
    FEE_CALC -->|"Pre-computed fee amounts"| AI_CHAT
    AI_CHAT -->|"Natural language answer"| EP3
    EP3 -->|"Returns answer"| USER

    %% ══════════════════════════════════════════════════════
    %% FLOW D — Financial Analysis
    %% ══════════════════════════════════════════════════════

    EP5 -->|"Request analysis"| TABLES
    TABLES -->|"Fee data"| AI_ANALYSIS
    AI_ANALYSIS -->|"Narrative report"| EP5
    EP5 -->|"Returns analysis"| USER

    %% ══════════════════════════════════════════════════════
    %% FLOW E — News Feed
    %% ══════════════════════════════════════════════════════

    EP4 -->|"Fetch news"| NEWS_CACHE
    NEWS_CACHE -->|"Recent news items"| EP4
    EP4 -->|"Returns news articles"| USER

    %% ══════════════════════════════════════════════════════
    %% FLOW F — Email Reports
    %% ══════════════════════════════════════════════════════

    EP6 -->|"Manual trigger"| EMAIL_BUILD
    TABLES -->|"Fee tables"| EMAIL_BUILD
    PERSONA -->|"TCO rankings"| EMAIL_BUILD
    SMTP -->|"Weekly digest"| SUB

    %% ══════════════════════════════════════════════════════
    %% FLOW G — Quality Assurance (background, non-blocking)
    %% ══════════════════════════════════════════════════════

    EP2 -.->|"Background: submit for review"| JUDGE
    EP3 -.->|"Background: submit for review"| JUDGE
    EP5 -.->|"Background: submit for review"| JUDGE

    %% ══════════════════════════════════════════════════════
    %% STYLING
    %% ══════════════════════════════════════════════════════

    classDef actor       fill:#1A73E8,stroke:#0D47A1,color:#FFFFFF,rx:12,font-size:13px
    classDef gateway     fill:#E8EAF6,stroke:#3949AB,color:#1A237E,font-size:12px
    classDef endpoint    fill:#E3F2FD,stroke:#1565C0,color:#0D1B5E,font-size:11px
    classDef datastore   fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C,font-size:12px
    classDef llm         fill:#FFF3E0,stroke:#E65100,color:#BF360C,font-size:12px
    classDef engine      fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20,font-size:12px
    classDef scheduler   fill:#FCE4EC,stroke:#AD1457,color:#880E4F,font-size:12px
    classDef quality     fill:#F9FBE7,stroke:#827717,color:#33691E,font-size:12px

    class USER,ADMIN,SUB actor
    class RL,CORS gateway
    class EP1,EP2,EP3,EP4,EP5,EP6 endpoint
    class FEE_DB,NEWS_STORE datastore
    class LLM_EXTRACT,LLM_STRUCT,AI_CHAT,AI_ANALYSIS llm
    class SCRAPER,NEWS_SCRAPER,FEE_CALC,PERSONA,TABLES,NOTES engine
    class NEWS_SCHED,EMAIL_SCHED,EMAIL_BUILD,SMTP,NEWS_CACHE scheduler
    class JUDGE,LANGFUSE quality
    class BROKERS actor
```

---

## Flow Summary

| Flow | Trigger | Key Steps | Output |
|------|---------|-----------|--------|
| **A · Fee Refresh** | Admin runs `/refresh-and-analyze` | Scrape PDFs → GPT-4o extract → Claude structure → Save | Updated `fee_rules.json` |
| **B · Fee Comparison** | User requests `/cost-comparison-tables` | Load rules → Compute fees → Build tables + notes | Fee matrix + TCO rankings |
| **C · AI Chat** | User posts question to `/chat` | Parse intent → Pre-compute fees → Groq/Llama answer | Natural language response |
| **D · Financial Analysis** | User calls `/financial-analysis` | Load tables → Claude narrative → Return report | Written analysis |
| **E · News Feed** | User calls `/news` | Check 24h cache → Serve recent articles | Broker news items |
| **F · Weekly Email** | Monday scheduler or `/send-email-report` | Build HTML → Gmail SMTP → Deliver | Subscriber email digest |
| **G · Quality Check** | Runs in background after every AI response | Gemini Judge reviews output → Score logged | Groundedness score in Langfuse |

---

## Key Design Principles

- **Deterministic-first:** Fees are computed by pure Python rules (no AI guessing) — AI is only used for extraction, structuring, and natural language output.
- **AI-as-a-Tool:** Three separate LLMs handle different jobs: GPT-4o (extraction), Claude (structuring + analysis), Groq/Llama (chat speed).
- **Continuous Quality:** Every AI-generated response is independently scored by a fourth model (Gemini Judge) and logged to Langfuse.
- **Scheduled Automation:** News scraping (daily) and email reporting (weekly) run as daemon threads — no manual intervention needed.
- **Security by default:** All requests pass through rate limiting and IP blocking before reaching any business logic.
