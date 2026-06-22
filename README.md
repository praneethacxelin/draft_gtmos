# GTM Factory — Agentic Go-To-Market Operating System

An AI-powered, 3-stage Go-To-Market (GTM) operating system that automates the entire pipeline from product strategy discovery through lead generation to multi-channel outreach, with a closed-loop intelligence layer that continuously refines targeting.

---

## Table of Contents

- [Product Overview](#product-overview)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Directory Structure](#directory-structure)
- [Database Schema (ERD)](#database-schema-erd)
- [Pipeline Stages — Deep Dive](#pipeline-stages--deep-dive)
  - [Stage 1: Product Profile & Discovery (S1)](#stage-1-product-profile--discovery-s1)
  - [Stage 2: Market Research & Scoring (S2)](#stage-2-market-research--scoring-s2)
  - [Stage 3: 3-Channel Outreach (S3)](#stage-3-3-channel-outreach-s3)
  - [M3: Intelligence Loop](#m3-intelligence-loop)
- [Discovery Questionnaire — Full Question List](#discovery-questionnaire--full-question-list)
- [API Surface](#api-surface)
- [Frontend Pages & Components](#frontend-pages--components)
- [Third-Party Integrations](#third-party-integrations)
- [Setup & Run Locally](#setup--run-locally)
- [Environment Variables](#environment-variables)
- [Data Flow Diagrams](#data-flow-diagrams)
- [Known Limitations & Gotchas](#known-limitations--gotchas)
- [Recent Improvements (June 2026)](#recent-improvements-june-2026)
- [Roadmap & Future Improvements](#roadmap--future-improvements)

---

## Product Overview

GTM Factory is a **single-operator console** designed for GTM Engineers, CROs, and Sales Heads. It replaces fragmented spreadsheets, manual research, and disconnected tools with a unified AI pipeline:

1. **Product Profile & Discovery (S1)** — Enter your product name, fill a 15-question discovery wizard (MCQ chips + text inputs), and the AI generates an ICP, persona matrix, problem map, NAICS segmentation, stakeholder graph, and use-case library.

2. **Market Research & Scoring (S2)** — TAM/SAM/SOM estimation (via SerpAPI + AI), competitor profiling, lead discovery (via Apollo or AI demo), buying-signal detection (SerpAPI or AI demo), composite lead scoring, and pattern recognition.

3. **3-Channel Outreach (S3)** — Persona-aware email/LinkedIn/call sequencer, deliverability scoring, and campaign launch via Instantly or simulation mode.

4. **M3 Intelligence Loop** — Engagement tracking, intent classification, feedback capture with sentiment analysis, multi-touch attribution, MQL/SQL/Nurture qualification, and ICP loop-back with one-click apply.

**Design Philosophy**: "Minimal effort, maximum output" — the user spends 5–10 minutes on discovery, and the system generates hundreds of data points for strategy, leads, signals, and outreach.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)                   │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐   │
│  │Dashboard│ │Product   │ │Prospects │ │Outreach       │   │
│  │         │ │Profile   │ │(Accounts,│ │(Sequences,    │   │
│  │         │ │(Discovery│ │ Contacts,│ │ Email Preview,│   │
│  │         │ │ Wizard)  │ │ Signals) │ │ Launch)       │   │
│  └─────────┘ └──────────┘ └──────────┘ └───────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │Intelli-  │ │Analytics │ │Settings  │ │Audit Log     │   │
│  │gence(M3) │ │          │ │(API Keys)│ │              │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────────────┐
│                   BACKEND (FastAPI)                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Routes (/api/*)                         │    │
│  │  strategies · accounts · contacts · signals         │    │
│  │  sequences · intelligence · dashboard · analytics   │    │
│  │  settings · copilot · audit · admin · health        │    │
│  └────────────────────┬────────────────────────────────┘    │
│  ┌────────────────────▼────────────────────────────────┐    │
│  │              Agent Pipeline                          │    │
│  │  s1_strategy.py → s2_signals.py → s3_outreach.py    │    │
│  │  m3_intent.py · sdr_copilot.py · s1_graph.py        │    │
│  └────────────────────┬────────────────────────────────┘    │
│  ┌────────────────────▼────────────────────────────────┐    │
│  │              Services                                │    │
│  │  clients.py (Apollo, SerpAPI, Clay, Instantly)       │    │
│  │  settings_service.py (encrypted API keys)            │    │
│  │  audit_service.py (immutable logging)                │    │
│  │  fetch_limits.py · rate_limit.py · m3_tracking.py    │    │
│  └────────────────────┬────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────────────┘
                       │ SQL
┌──────────────────────▼──────────────────────────────────────┐
│          PostgreSQL  +  ChromaDB (local vector store)        │
│  20+ tables: strategies, accounts, contacts, signals,        │
│  sequences, lead_scores, engagement_events, intent_scores,   │
│  audit_logs, icp_embeddings, pattern_clusters, etc.          │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query, Wouter (routing), Lucide Icons |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0, psycopg3, sse-starlette (SSE streaming) |
| **AI** | OpenAI GPT-4o-mini via Replit proxy (consumed in `app/llm.py`) |
| **Embeddings** | ChromaDB (local, embedded) with a built-in MiniLM sentence-transformer; deterministic SHA-based fallback when the model can't load |
| **Database** | PostgreSQL (relational) + ChromaDB (vector similarity) |
| **External APIs** | Apollo.io (lead discovery), SerpAPI (market research + signals), Clay (enrichment), Instantly.ai (email campaigns + verification) |

---

## Directory Structure

```
Attached-Assets/
├── artifacts/
│   ├── app/                          # React frontend
│   │   ├── src/
│   │   │   ├── App.tsx               # Router (Wouter) + QueryClient
│   │   │   ├── main.tsx              # Entry point
│   │   │   ├── index.css             # Design system (CSS vars, MCQ chips, wizard styles)
│   │   │   ├── components/
│   │   │   │   ├── layout/
│   │   │   │   │   └── AppShell.tsx  # Sidebar nav, active profile dropdown, theme toggle
│   │   │   │   ├── DiscoveryWizard.tsx  # 4-section MCQ + text wizard (15 questions)
│   │   │   │   ├── EditableField.tsx    # Inline editable text
│   │   │   │   ├── EditableTextarea.tsx # Inline editable textarea
│   │   │   │   ├── EditableList.tsx     # Inline editable list
│   │   │   │   ├── Empty.tsx            # Empty state component
│   │   │   │   ├── PageHeader.tsx       # Reusable page header
│   │   │   │   ├── Pills.tsx            # StatusPill, TierBadge, ScoreBar, DemoBadge
│   │   │   │   ├── ReasoningPanel.tsx   # Provenance/reasoning display
│   │   │   │   ├── RetriggerBar.tsx     # "Data changed — re-run?" bar
│   │   │   │   ├── StakeholderFlow.tsx  # Stakeholder graph visualization
│   │   │   │   └── ui/                  # shadcn/ui primitives
│   │   │   ├── hooks/
│   │   │   │   ├── useActiveStrategy.ts # Global active profile state (synced via CustomEvent)
│   │   │   │   ├── useStrategies.ts     # CRUD + S1/S2 mutations
│   │   │   │   ├── useAccounts.ts       # Account queries
│   │   │   │   ├── useContacts.ts       # Contact queries + reveal/verify mutations
│   │   │   │   ├── useSignals.ts        # Signal queries
│   │   │   │   ├── useSequences.ts      # Outreach sequence queries
│   │   │   │   ├── useSettings.ts       # API key management
│   │   │   │   ├── useAuditLogs.ts      # Audit log queries
│   │   │   │   ├── useDashboard.ts      # Dashboard stats
│   │   │   │   ├── useM3.ts            # M3 intelligence (engagement, intent, feedback)
│   │   │   │   ├── useCopilot.ts       # SDR copilot
│   │   │   │   └── useTheme.ts         # Dark/light theme toggle
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx        # Overview stats + pipeline summary
│   │   │   │   ├── StrategyList.tsx     # Product Profile list + "name-only" creation
│   │   │   │   ├── StrategyDetail.tsx   # Full profile detail (pipeline tabs + discovery)
│   │   │   │   ├── Prospects.tsx        # Accounts, contacts, signals tables
│   │   │   │   ├── Outreach.tsx         # Sequence builder + launch
│   │   │   │   ├── Intelligence.tsx     # M3 loop (engagement, intent, feedback, attribution)
│   │   │   │   ├── Analytics.tsx        # Campaign analytics
│   │   │   │   ├── Settings.tsx         # API key management
│   │   │   │   ├── Audit.tsx            # Full audit trail viewer
│   │   │   │   ├── Help.tsx             # User guide
│   │   │   │   └── Admin.tsx            # Admin panel
│   │   │   └── lib/
│   │   │       ├── api.ts              # apiFetch() + apiUrl() helpers
│   │   │       ├── format.ts           # Date/number formatters
│   │   │       └── utils.ts            # cn() class merge utility
│   │   ├── vite.config.ts
│   │   └── package.json
│   │
│   └── fastapi-server/                 # Python backend
│       ├── main.py                     # App factory + router mounting + lifespan
│       ├── app/
│       │   ├── db.py                   # All SQLAlchemy models (20+ tables)
│       │   ├── llm.py                  # OpenAI wrapper: chat_json(), deterministic_embedding()
│       │   ├── provenance.py           # stamp() provenance helper for reasoning panels
│       │   ├── auth.py                 # user_public seeding (no auth)
│       │   ├── admin_auth.py           # Admin header check
│       │   ├── crypto.py              # Fernet encrypt/decrypt for API keys
│       │   ├── scoping.py             # Query scoping utilities
│       │   ├── agents/
│       │   │   ├── s1_strategy.py     # S1 pipeline (ICP → Personas → Problems → NAICS → Stakeholders → Use Cases)
│       │   │   ├── s1_graph.py        # S1 GraphRAG variant (knowledge graph extraction)
│       │   │   ├── s2_signals.py      # S2 pipeline (Market Sizing → Lead Search → Signals → Scoring → Patterns)
│       │   │   ├── s3_outreach.py     # S3 pipeline (Sequence generation → Deliverability → Launch)
│       │   │   ├── m3_intent.py       # M3 intent scoring + qualification + ICP loop-back
│       │   │   └── sdr_copilot.py     # Next-best-action copilot
│       │   ├── services/
│       │   │   ├── clients.py         # HTTP wrappers: Apollo, SerpAPI, Clay, Instantly
│       │   │   ├── settings_service.py # Encrypted API key CRUD
│       │   │   ├── audit_service.py   # Immutable audit logging
│       │   │   ├── fetch_limits.py    # Per-run limit clamping
│       │   │   ├── rate_limit.py      # API rate limiting
│       │   │   ├── m3_tracking.py     # Engagement event tracking
│       │   │   └── instantly_poller.py # Instantly campaign sync
│       │   ├── routes/
│       │   │   ├── strategies.py      # /api/strategies/* (CRUD + S1 run + discovery)
│       │   │   ├── accounts.py        # /api/accounts/*
│       │   │   ├── contacts.py        # /api/contacts/* (reveal, verify, bulk verify)
│       │   │   ├── signals.py         # /api/signals/*
│       │   │   ├── sequences.py       # /api/sequences/*
│       │   │   ├── intelligence.py    # /api/intelligence/* (engagement, intent, feedback, attribution, qualify)
│       │   │   ├── dashboard.py       # /api/dashboard/*
│       │   │   ├── analytics.py       # /api/analytics/*
│       │   │   ├── settings.py        # /api/settings/*
│       │   │   ├── copilot.py         # /api/copilot/*
│       │   │   ├── audit.py           # /api/audit/*
│       │   │   ├── admin.py           # /api/admin/*
│       │   │   └── health.py          # /api/health
│       │   └── schemas/               # Pydantic request/response models
│       ├── seed.py                     # Demo data seeder
│       └── alembic/                    # Database migrations
```

---

## Database Schema (ERD)

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | Single shared user (no auth) | `id`, `email`, `is_admin` |
| `app_settings` | Encrypted API keys per integration | `integration_name`, `api_key_encrypted`, `is_enabled`, `test_status` |
| `strategies` | Product profiles + all S1 outputs | `product_name`, `description`, `discovery_data` (JSONB), `icp_json`, `personas_json`, `problems_json`, `naics_json`, `stakeholder_map_json`, `use_cases_json`, `tam_sam_som_json`, `status` |
| `accounts` | Target companies | `company_name`, `domain`, `industry`, `employee_count`, `revenue_range`, `tier` (1/2/3) |
| `contacts` | People at accounts | `full_name`, `title`, `email`, `phone`, `persona_type`, `icp_fit_score`, `signal_score`, `engagement_score`, `total_score`, `tier`, `is_demo`, `email_verified` |
| `signals` | Buying signals (funding/hiring/tech/news) | `signal_type`, `source`, `summary`, `strength_score`, `raw_data_json` |
| `competitor_profiles` | Competitor analysis data | `name`, `website`, `positioning`, `features_json`, `pricing_info`, `weaknesses_json`, `g2_rating` |

### Scoring & Outreach Tables

| Table | Purpose |
|-------|---------|
| `lead_scores` | Composite lead score breakdown |
| `sequences` | Outreach sequences (email/LinkedIn/call plans) |
| `sequence_steps` | Individual steps within a sequence |
| `instantly_campaigns` | Instantly.ai campaign sync data |
| `outreach_events` | sent/opened/clicked/replied/bounced events |

### M3 Intelligence Tables

| Table | Purpose |
|-------|---------|
| `engagement_events` | Page views, ad clicks, email opens |
| `intent_scores` | Account-level intent classification (low/medium/high) |
| `feedback_entries` | NPS/survey/rating with auto-extracted sentiment + themes |
| `attribution_events` | Multi-touch attribution (demo_booked, trial_started, deal_created) |
| `qualification_records` | MQL/SQL/Nurture decisions |
| `contact_snoozes` | Snooze contacts for N days with reason |
| `gtm_loop_updates` | ICP refinement suggestions with one-click apply |

### Infrastructure Tables

| Table | Purpose |
|-------|---------|
| `icp_embeddings` | ICP embeddings (JSON copy in Postgres; queryable copy in ChromaDB) for semantic ICP-fit scoring |
| `pattern_clusters` | Learned conversion patterns from scoring |
| `audit_logs` | Immutable log of every API call + data change |

---

## Pipeline Stages — Deep Dive

### Stage 1: Product Profile & Discovery (S1)

**File**: `artifacts/fastapi-server/app/agents/s1_strategy.py`

**Trigger**: User clicks "Run S1" or creates a new profile (auto-runs if status is `draft`).

**Data Flow**:
1. User creates a Product Profile (just a product name).
2. User fills the **Discovery Wizard** (15 questions across 4 sections — see below).
3. Discovery answers are saved to `strategies.discovery_data` (JSONB) via auto-save (800ms debounce).
4. When S1 runs, it builds a **rich brief** from all 15 discovery fields + legacy fields.
5. The brief is sent through 6 sequential LLM stages, each emitting an SSE event:

| Stage | Output | Stored In |
|-------|--------|-----------|
| 1. ICP Modeling | Firmographics, org size, geographies, industries, tech stack signals | `icp_json` |
| 2. Persona Matrix | Champion, Economic Buyer, Blocker (title, priorities, objections, messaging) | `personas_json` |
| 3. Problem Map | Problem rows with severity, frequency, current workaround, cost of inaction | `problems_json` |
| 4. NAICS Segmentation | Industry codes with fit score and rationale | `naics_json` |
| 5. Stakeholder Graph | Role nodes with influence scores and relationships | `stakeholder_map_json` |
| 6. Use Case Library | Structured use cases with triggers, outcomes, and proof points | `use_cases_json` |

**Brief Construction Logic** (`_dd()` helper):
- Arrays: filters out `__other__` sentinel, joins with commas
- Strings: strips whitespace, falls back to legacy field or `"unspecified"`
- Legacy backfill: if `description`/`target_market`/`pain_points_raw` are empty, populates them from discovery data

---

### Stage 2: Market Research & Scoring (S2)

**File**: `artifacts/fastapi-server/app/agents/s2_signals.py`

**Sub-pipelines**:

#### 2a. Market Sizing (`run_market_sizing`)
1. Selects top NAICS segment as search anchor.
2. Queries SerpAPI for market size data (or skips if no key).
3. Sends snippets + discovery context to LLM with a structured prompt demanding methodology and source citations.
4. Returns `{tam, sam, som, methodology, confidence, sources[]}`.

#### 2b. Lead Discovery (`run_lead_search`)
1. Extracts search filters from discovery data:
   - **Titles**: From personas → discovery `economic_buyer`/`champion` → fallback defaults
   - **Employee ranges**: Mapped from MCQ org_size (e.g., "51–200 (Mid-Market)" → "51,200")
   - **Locations**: Merged from discovery `target_geos` + ICP geographies
   - **Technologies**: From discovery `alternatives` (competitor tools people use)
   - **Keywords**: From UVP/pain points
   - **Industries**: From ICP
2. Calls Apollo People Search with those filters.
3. Falls back to broader search if too restrictive.
4. Falls back to AI-generated demo leads if no Apollo key.
5. Deduplicates by email + (account, name).
6. Creates Account + Contact rows.
7. Auto-triggers lead scoring.

**Caching**: If real (non-demo) contacts already exist, skips Apollo to save credits.

#### 2c. Buying Signals (`run_signals`)
1. For each account (up to 10), runs SerpAPI queries:
   - Funding: `"{company}" funding OR investment OR raises`
   - Hiring: `"{company}" hiring OR "new hire" OR "joins as"`
2. Filters for relevance (company name must appear in title or snippet).
3. **Bulk LLM Translation**: All raw search results are sent to the LLM to generate actionable sales insights formatted as `[Fact] - [Why it matters / Action]`.
4. Falls back to AI-generated demo signals if no SerpAPI key.

#### 2d. Lead Scoring (`score_leads`)
Weighted composite:
- **ICP Fit (30%)**: LLM evaluates contact against ICP firmographics
- **Signals (40%)**: strength_score from detected buying signals
- **Engagement (30%)**: From M3 engagement events
- **Pattern Bonus**: Small boost when learned `pattern_clusters` exist

Tier assignment: Tier 1 (≥70), Tier 2 (40–69), Tier 3 (<40).

#### 2e. Pattern Recognition (`run_patterns`)
pgvector-free pattern recognition: signal co-occurrences are clustered with a `Counter`, named, and (when available) indexed in ChromaDB for semantic pattern memory.

---

### Stage 3: 3-Channel Outreach (S3)

**File**: `artifacts/fastapi-server/app/agents/s3_outreach.py`

1. **Sequence Generation**: LLM generates persona-aware outreach plan:
   - Email (subject + body, personalized to persona type and pain points)
   - LinkedIn (connection request + follow-up)
   - Call (talk track with objection handling)
2. **Deliverability Scoring**: Checks email format, domain reputation, catch-all detection.
3. **Launch**: 
   - With Instantly key: Creates campaign, adds leads, starts sending.
   - Without key: Marks as "simulated" — all steps saved but not sent.

---

### M3: Intelligence Loop

**File**: `artifacts/fastapi-server/app/agents/m3_intent.py`

Closed-loop system that feeds back into S1:

1. **Engagement Events**: Track page views, email opens, ad clicks, form fills.
2. **Intent Classification**: Aggregate engagement into account-level intent (low/medium/high).
3. **Feedback Capture**: NPS/survey with auto-extracted sentiment + themes.
4. **Attribution**: Multi-touch attribution across channels.
5. **Qualification**: MQL → SQL → Nurture decisions.
6. **ICP Loop-back**: Suggests ICP refinements based on what's actually converting, with one-click apply.

---

## Discovery Questionnaire — Full Question List

The Discovery Wizard is a 4-section, 15-question interactive form. Questions are either **MCQ chips** (selectable pills with "Other" free-text) or **text inputs** (textarea/single-line).

### Section 1: Product & Company (3 questions)

| # | Question | Type | Options / Placeholder |
|---|----------|------|----------------------|
| 1 | What is your product or service? | Textarea | "An AI-powered sales intelligence platform that helps B2B sales teams…" |
| 2 | What type of company are you? | MCQ (single) | SaaS · Consulting/Agency · E-commerce/D2C · Marketplace/Platform · Hardware+Software · Services/Professional · IT/Managed Services · Other |
| 3 | What pain points does your product solve? | Textarea | "Sales teams waste 60% of their time on unqualified leads…" |

### Section 2: Ideal Customer (3 questions)

| # | Question | Type | Options / Placeholder |
|---|----------|------|----------------------|
| 4 | What org size are you targeting? | MCQ (multi) | 1–10 (Startup) · 11–50 (Small) · 51–200 (Mid-Market) · 201–1,000 (Enterprise) · 1,000+ (Large Enterprise) · Other |
| 5 | What geographies are you targeting? | MCQ (multi) | North America · Europe · India · Asia-Pacific · Latin America · Middle East & Africa · Global · Other |
| 6 | Describe your perfect customer | Textarea | "Series B+ SaaS companies with 100-500 employees, using Salesforce…" |

### Section 3: Buying Committee (3 questions)

| # | Question | Type | Options / Placeholder |
|---|----------|------|----------------------|
| 7 | Who is the Economic Buyer? | Text | "VP of Sales, CRO, Head of Revenue" |
| 8 | Who is the Champion? | Text | "Sales Manager, RevOps Lead, SDR Manager" |
| 9 | What typically blocks deals? | MCQ (multi) | IT/Security · Finance/Procurement · Legal · End Users · Existing Vendor Loyalty · Long approval chains · Other |

### Section 4: Signals & Competition (5 questions)

| # | Question | Type | Options / Placeholder |
|---|----------|------|----------------------|
| 10 | What buying signals should we look for? | MCQ (multi) | Just raised funding · Hired new leadership · Expanding to new markets · Tech stack migration · Competitor contract renewal · Job postings for related roles · Negative reviews of competitor · Other |
| 11 | What triggers a purchase? | Textarea | "Missed quarterly revenue targets, board pressure to reduce CAC…" |
| 12 | What tools/methods do they currently use? | Text | "Spreadsheets, ZoomInfo, LinkedIn Sales Navigator, HubSpot" |
| 13 | What is your unique value proposition? | Textarea | "3x faster lead qualification with AI-driven intent signals…" |
| 14 | What is the typical sales cycle? | MCQ (single) | < 1 month · 1–3 months · 3–6 months · 6–12 months · 12+ months · Other |

### How Discovery Data Flows Into the Pipeline

```
Discovery Wizard (frontend)
    │
    ├──► strategies.discovery_data (JSONB) ──► S1 brief construction
    │                                          └──► ICP, Personas, Problems, NAICS, etc.
    │
    ├──► S2 Lead Search (Apollo filters)
    │    ├── org_size → employee_ranges
    │    ├── target_geos → locations
    │    ├── alternatives → technologies
    │    ├── uvp/pain_points → keywords
    │    └── economic_buyer/champion → titles
    │
    └──► S2 Market Sizing (context for TAM/SAM/SOM prompt)
```

---

## API Surface

### Strategies
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/strategies` | List all product profiles |
| POST | `/api/strategies` | Create profile (only `product_name` required) |
| GET | `/api/strategies/:id` | Get full profile with all S1 outputs |
| PATCH | `/api/strategies/:id` | Update profile fields |
| PATCH | `/api/strategies/:id/discovery` | Save discovery questionnaire data |
| PATCH | `/api/strategies/:id/section` | Update individual S1 section (ICP, personas, etc.) |
| GET | `/api/strategies/:id/run` | **SSE stream** — Run full S1 pipeline |
| POST | `/api/strategies/:id/market-sizing` | Run TAM/SAM/SOM estimation |
| POST | `/api/strategies/:id/competitors` | Run competitor profiling |
| POST | `/api/strategies/:id/lead-search` | Discover leads (Apollo or AI demo) |
| POST | `/api/strategies/:id/signals` | Detect buying signals (SerpAPI or AI demo) |
| POST | `/api/strategies/:id/score` | Score all leads |
| POST | `/api/strategies/:id/patterns` | Run pattern recognition |

### Contacts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contacts` | List contacts (filterable by strategy, tier) |
| PATCH | `/api/contacts/:id` | Update contact fields |
| POST | `/api/contacts/:id/reveal-email` | Reveal email via Apollo (1 credit) |
| POST | `/api/contacts/:id/reveal-phone` | Reveal phone via Apollo (1 credit) |
| POST | `/api/contacts/:id/verify-email` | Verify email via Instantly |
| POST | `/api/contacts/verify-bulk` | Bulk verify selected contacts |
| POST | `/api/strategies/:id/fetch-emails` | Bulk fetch emails for contacts missing them |
| POST | `/api/strategies/:id/fetch-phones` | Bulk fetch phones for contacts missing them |

### Sequences
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sequences` | List sequences |
| POST | `/api/sequences/:id/generate` | Generate outreach content |
| POST | `/api/sequences/:id/launch` | Launch campaign (Instantly or simulated) |
| POST | `/api/sequences/:id/deliver-check` | Run deliverability check |

### Intelligence (M3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/intelligence/engagement` | Log engagement event |
| GET | `/api/intelligence/intent/:strategy_id` | Get account intent scores |
| POST | `/api/intelligence/intent/compute` | Compute intent from engagements |
| POST | `/api/intelligence/feedback` | Submit feedback (NPS/survey) |
| GET | `/api/intelligence/attribution/:strategy_id` | Get attribution summary |
| POST | `/api/intelligence/qualify` | Qualify contact (MQL/SQL/Nurture) |
| GET | `/api/intelligence/loop-updates/:strategy_id` | Get ICP refinement suggestions |
| POST | `/api/intelligence/loop-updates/:id/apply` | Apply ICP refinement |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Dashboard summary metrics |
| GET/POST | `/api/settings/*` | API key management |
| GET | `/api/audit/logs` | Audit trail query |
| GET | `/api/health` | Health check |
| GET | `/api/copilot/:strategy_id` | SDR copilot next-best-actions |
| GET | `/api/analytics/*` | Campaign analytics |

---

## Frontend Pages & Components

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | `Dashboard` | Pipeline overview, stats, recent activity |
| `/strategy` | `StrategyList` | Product Profile list + name-only creation form |
| `/strategy/:id` | `StrategyDetail` | Full profile detail with tabbed view: Discovery, ICP, Personas, Problems, NAICS, Stakeholders, Use Cases, Market Sizing, Competitors |
| `/prospects` | `Prospects` | 3 tabs: Accounts (tiered), Contacts (with inline edit, email reveal/verify), Signals |
| `/outreach` | `Outreach` | Sequence builder, email preview, launch controls |
| `/intelligence` | `Intelligence` | M3 loop: engagement events, intent scores, feedback, attribution, qualification, ICP loop-back |
| `/analytics` | `Analytics` | Campaign performance metrics |
| `/settings` | `Settings` | API key management (SerpAPI, Apollo, Clay, Instantly) |
| `/audit` | `Audit` | Full audit trail with filters |
| `/help` | `Help` | User guide and documentation |

### Key Components

- **`DiscoveryWizard`**: 4-section stepper with MCQ chips + text inputs, auto-save, progress tracking
- **`AppShell`**: Sidebar nav, active profile dropdown (synced via CustomEvent across components), dark/light toggle
- **`ReasoningPanel`**: Shows provenance (Live: SerpAPI vs AI Generated, model used, processing steps)
- **`StakeholderFlow`**: Interactive stakeholder graph visualization
- **`RetriggerBar`**: "Data changed — re-run scoring?" notification bar

---

## Third-Party Integrations

All integrations are **optional**. Without API keys, the system falls back to AI-generated demo data flagged with `is_demo: true` / `source: "ai_demo"`.

| Integration | Purpose | How to Enable |
|-------------|---------|---------------|
| **SerpAPI** | Market sizing research, buying signal detection (funding/hiring queries) | Settings → Add SerpAPI key |
| **Apollo.io** | Real lead discovery (people search with firmographic filters) | Settings → Add Apollo key |
| **Clay** | Additional enrichment (company/contact data) | Settings → Add Clay key |
| **Instantly.ai** | Email campaign launch, email verification, campaign analytics sync | Settings → Add Instantly key |

API keys are encrypted with **Fernet** (AES-128-CBC) before storage in the `app_settings` table. The encryption key is set via the `ENCRYPTION_KEY` environment variable.

---

## Setup & Run Locally

### Prerequisites
- Node.js 18+ and pnpm
- Python 3.11+
- PostgreSQL (ChromaDB is embedded — no separate server or pgvector extension needed)

### Backend
```bash
cd artifacts/fastapi-server
python -m venv venv
.\venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn main:app --port 8080 --reload
```

### Frontend
```bash
cd artifacts/app
pnpm install
pnpm run dev
```

### Seed Demo Data
```bash
cd artifacts/fastapi-server
python seed.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `ENCRYPTION_KEY` | ✅ | Fernet key for API key encryption |
| `AI_INTEGRATIONS_OPENAI_API_KEY` | ✅ | OpenAI API key (or Replit proxy) |
| `AI_INTEGRATIONS_OPENAI_BASE_URL` | Optional | Custom OpenAI base URL |
| `AI_INTEGRATIONS_OPENAI_MODEL` | Optional | Model override (default: gpt-4o-mini) |

---

## Data Flow Diagrams

### End-to-End Pipeline

```
[User] → Create Product Profile (name only)
    │
    ▼
[Discovery Wizard] → 15 questions → saved to discovery_data (JSONB)
    │
    ▼
[S1 Pipeline] (SSE stream)
    ├── ICP → Personas → Problems → NAICS → Stakeholders → Use Cases
    │
    ▼
[S2 Pipeline] (triggered manually)
    ├── Market Sizing (SerpAPI + AI)
    ├── Lead Discovery (Apollo + dedup + scoring)
    ├── Signal Detection (SerpAPI + LLM actionable insights)
    └── Pattern Recognition (Counter clustering + ChromaDB memory)
    │
    ▼
[S3 Pipeline] (triggered per contact)
    ├── Sequence Generation (email/LinkedIn/call)
    ├── Deliverability Check
    └── Launch (Instantly or simulated)
    │
    ▼
[M3 Intelligence Loop]
    ├── Engagement Events → Intent Scores
    ├── Feedback → Sentiment + Themes
    ├── Attribution → Channel ROI
    ├── Qualification → MQL/SQL/Nurture
    └── ICP Loop-back → S1 refinement (one-click apply)
```

### Lead Scoring Formula

```
total_score = (icp_fit × 0.30) + (signals × 0.40) + (engagement × 0.30) + pattern_bonus

Tier Assignment:
  ├── Tier 1: total_score ≥ 70
  ├── Tier 2: 40 ≤ total_score < 70
  └── Tier 3: total_score < 40
```

---

## Known Limitations & Gotchas

1. **No Authentication**: This is a single-operator console. All `/api/*` routes are unauthenticated. Add OIDC before exposing externally.
2. **S1 Re-run Guard**: S1 SSE rejects re-runs while `status == "generating"` to prevent interleaved writes.
3. **LLM JSON Failures**: Surface as `{"_error": ...}` and are NOT persisted. The UI shows previous payload.
4. **Lead Deduplication**: Re-running lead discovery deduplicates by email + (account_id, full_name).
5. **Pseudo-Embeddings**: The Replit OpenAI proxy doesn't expose embeddings. `deterministic_embedding()` uses SHA-based 1536-dim pseudo-vectors. Pattern clustering works but isn't as accurate as real embeddings.
6. **Apollo Credit Conservation**: Lead search skips Apollo if real contacts already exist. Delete contacts to force re-fetch.
7. **Instantly Free Tier**: Campaign management, warmup, and analytics APIs are wired up but only activate with a valid Instantly API key.
8. **Git Push Errors**: If you see `curl 52 Recv failure: Connection was reset`, increase the buffer: `git config --global http.postBuffer 524288000` and retry.

---

## Recent Improvements (June 2026)

### UI/UX Redesign
- **Renamed "Strategy" → "Product Profile"** across the entire app (sidebar, headers, dropdown, list page, detail page)
- **Simplified creation flow**: Only product name required to create → redirects to Discovery Wizard
- **Discovery Wizard**: Complete rewrite from 9 text-only questions to a 4-section interactive wizard with MCQ chip selectors, "Other" free-text, auto-save (800ms debounce), section stepper with progress, and completion percentage
- **Fixed Active Profile dropdown sync**: Now uses CustomEvent broadcasting so the sidebar dropdown instantly reflects which profile you're viewing
- **Fixed Discovery stepper**: Steps only show green checkmark if questions are actually answered, not just by clicking Next

### Backend Pipeline Enhancements
- **S1 Brief enrichment**: Pipeline now uses all 15 discovery data points (previously only 4 fields)
- **Apollo search parameters**: Now extracts org_size → employee_ranges, target_geos → locations, alternatives → technologies, uvp/pain_points → keywords from discovery data
- **Apollo client extensions**: Added `technologies`, `keywords`, and `revenue_ranges` filter pass-through
- **Market Sizing prompt upgrade**: Now requires explicit methodology and source citations in the response
- **Actionable signals**: Raw SerpAPI results are now bulk-translated by LLM into actionable sales insights formatted as `[Fact] - [Why it matters / Action]`

---

## Roadmap & Future Improvements

### Data Accuracy & Relevancy
1. **Multi-query Market Sizing**: Run multiple SerpAPI queries with different angles (by vertical, by geography, by use case) and cross-reference
2. **Signal Freshness Scoring**: Weight signals by recency (last 30 days = full weight, 90+ days = half)
3. **ICP Validation against Real Deals**: Compare ICP against closed-won deals to validate accuracy
4. **Apollo Enrichment Verification**: Cross-reference Apollo data with LinkedIn profile pages via Clay

### Pipeline Performance
5. **Parallel S1 Stages**: Run independent S1 stages (NAICS + use cases) concurrently
6. **Cached LLM Responses**: Hash prompts and cache responses to avoid redundant API calls
7. **Incremental Lead Discovery**: Only fetch new leads since last run, not re-fetch everything
8. **Background Job Queue**: Move long-running pipelines to a proper job queue (Celery/ARQ) instead of in-request SSE

### New Capabilities
9. **LinkedIn Signal Scraping**: Detect leadership changes, company posts, hiring patterns directly from LinkedIn
10. **CRM Integration**: Bi-directional sync with Salesforce/HubSpot for deal stage updates
11. **A/B Testing for Outreach**: Test different email subjects/bodies per persona segment
12. **Competitive Win/Loss Analysis**: Track why deals are won/lost and feed back into personas
13. **Real Embeddings**: Replace pseudo-embeddings with actual OpenAI text-embedding-3-small when available
14. **Multi-user + RBAC**: Add authentication with role-based access control
15. **Webhook-based Signal Monitoring**: Continuous monitoring instead of manual "Run Signals" clicks
