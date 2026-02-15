# ARCHITECTURE.md — How Maestro Works

## What Is Maestro

One AI mind per project, per superintendent. Maestro ingests construction plans, builds deep knowledge, proactively finds coordination gaps, and talks to the super via iMessage. The super texts Maestro. Maestro texts back. One continuous thread that never ends.

The web frontend is the super's window into Maestro's brain — opened via links that Maestro texts. Read-only. All mutations happen through conversation.

## System Architecture

```
                    ┌─────────────────────────────────────┐
                    │           server.py                  │
                    │    FastAPI + Heartbeat Runner        │
                    │                                     │
  iMessage ◄──────►│  /sendblue-webhook   (inbound text)  │
  (Sendblue)       │  /api/*              (REST, 14 endpoints)
                    │  /ws                (WebSocket push) │
                    │  /health, /stats    (server health)  │
                    └──────────┬──────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
        conversation.py   heartbeat.py     api/routes.py
        (the one thread)  (background)     (read-only API)
              │                │
              └───────┬────────┘
                      ▼
              engine/providers/*
              (Opus, Gemini, GPT)
                      │
                      ▼
                 tools/* (29)
              ┌────┬────┬────┬────┬────┐
              ▼    ▼    ▼    ▼    ▼    ▼
           know  vis  work sched learn switch
           (10)  (3)  (6)  (6)   (3)   (1)
```

## Entry Point

```
python server.py +16823521836              # Start with default engine (GPT)
python server.py +16823521836 gemini-flash  # Start with specific engine
```

Starts FastAPI on port 8000. Initializes the conversation engine, loads the project knowledge store into memory, creates/resumes DB state, sends an intro text, starts the heartbeat background thread, and begins listening.

**Requires:** ngrok tunnel (`ngrok http 8000`) for Sendblue webhook delivery.

## Folder Structure

```
Maestro/
├── server.py                 # Entry point — FastAPI + heartbeat + webhook
├── maestro.db                # SQLite database (auto-created)
├── .env                      # API keys (Gemini, Anthropic, OpenAI, Sendblue)
├── requirements.txt
├── AGENT.md                  # Instructions for coding agents
├── ARCHITECTURE.md           # This file
│
├── maestro/                  # All source code (on sys.path)
│   ├── engine/               # How Maestro thinks
│   │   ├── config.py         # Provider configs, defaults, compaction settings
│   │   ├── engine.py         # Setup utilities (load project, wire tools)
│   │   ├── heartbeat.py      # Proactive decision engine (4 modes)
│   │   └── providers/        # API adapters
│   │       ├── anthropic.py  # Claude (Opus)
│   │       ├── google.py     # Gemini (Pro/Flash)
│   │       └── openai.py     # GPT
│   │
│   ├── messaging/            # How Maestro communicates
│   │   ├── conversation.py   # The one continuous thread — DB-backed + compaction
│   │   └── sendblue.py       # iMessage API (send, typing indicator, formatting)
│   │
│   ├── tools/                # What Maestro can do (29 tools)
│   │   ├── registry.py       # Master tool list — single source of truth
│   │   ├── knowledge.py      # 10 tools — search, read, cross-reference
│   │   ├── vision.py         # 3 tools — see pages/pointers via Gemini vision
│   │   ├── workspaces.py     # 6 tools — workspace CRUD (→ DB)
│   │   ├── schedule.py       # 6 tools — schedule management (→ DB)
│   │   └── learning.py       # 3 tools — experience updates + audit log (→ DB)
│   │   # + switch_engine: registered dynamically by conversation.py
│   │
│   ├── knowledge/            # What Maestro knows (DO NOT TOUCH ingest.py)
│   │   ├── ingest.py         # PDF → knowledge store pipeline
│   │   ├── loader.py         # Load project JSON into memory at startup
│   │   ├── gemini_service.py # Shared Gemini client (ingest + vision tools)
│   │   └── prompts/          # Ingest prompt templates (pass1.txt, pass2.txt)
│   │
│   ├── identity/             # Who Maestro is
│   │   ├── soul.json         # Static identity (DENYLIST — DO NOT MODIFY)
│   │   ├── tone.json         # Static communication style (DENYLIST)
│   │   ├── prompt.py         # System prompt builder
│   │   └── experience/       # Dynamic — what Maestro has learned over time
│   │
│   ├── db/                   # Database layer
│   │   ├── models.py         # 8 SQLAlchemy models
│   │   ├── repository.py     # 20+ CRUD functions (tools call these)
│   │   └── session.py        # SQLite (local) / Postgres (prod) via DATABASE_URL
│   │
│   └── api/                  # Frontend-facing layer
│       ├── routes.py         # 14 REST endpoints under /api
│       └── websocket.py      # Real-time push (8 event types)
│
├── frontend/                 # React web app (super-facing)
│   ├── src/
│   │   ├── pages/            # Auth, AppShell, Home, Workspaces, WorkspaceDetail,
│   │   │                     # Schedule, Knowledge
│   │   ├── components/       # ProtectedRoute
│   │   ├── contexts/         # AuthContext (Supabase Google OAuth)
│   │   └── lib/              # api.js, websocket.js, supabase.js
│   └── vite.config.js        # Dev proxy: /api → :8000, /ws → ws://:8000
│
├── knowledge_store/          # Runtime: extracted plan data (read-only after ingest)
├── tests/                    # 303 passing tests (DB, rewire, API, WebSocket, workspaces)
└── old/                      # Frozen: V1-V12 history + migration script
```

## Data Model

### Database (SQLite local / Postgres prod)

8 tables, managed by SQLAlchemy:

| Table | Purpose |
|-------|---------|
| `projects` | One row per project (id, name, path) |
| `workspaces` | Grouped page collections with status |
| `workspace_pages` | Pages assigned to workspaces (with reason) |
| `workspace_notes` | Notes/findings attached to workspaces |
| `schedule_events` | Timeline events (phases, milestones, deadlines) |
| `messages` | Every message as individual rows (queryable, pageable) |
| `conversation_state` | Running summary, exchange count, compaction count |
| `experience_log` | Audit trail of learning tool usage |

### Knowledge Store (files, in-memory)

Loaded once at startup into a Python dict. ~197 pages, ~1321 pointers for the current project (CFA Love Field). Not in the database — too large, read-heavy, write-once after ingest.

### Identity (files, denylist)

`soul.json` and `tone.json` are static. `experience/` directory is dynamic and writable by Maestro's learning tools.

## Data Flows

### 1. Ingest: PDF → Knowledge Store (one-time)

```
PDF plan set → ingest.py → PNG pages (200 DPI)
  → Gemini Pass 1: page-level analysis (discipline, reflection, index)
  → Gemini Pass 2: region-level deep extraction (pointers, cross-refs)
  → knowledge_store/{project}/ → JSON files (read-only from here on)
```

### 2. Conversation: Super ↔ Maestro (continuous)

```
Super sends iMessage
  → Sendblue webhook → server.py → asyncio background task
  → typing indicator sent immediately
  → conversation.py feeds message to active provider
  → Provider runs tool loop (AI calls tools → results → AI responds)
  → Response persisted to DB (individual message rows)
  → Compaction check (65% of context → Gemini Flash summarizes old messages)
  → Response formatted and sent via Sendblue iMessage
  → WebSocket emit: message event to connected frontends
```

### 3. Heartbeat: Maestro thinks on its own (background, every 60s)

```
Timer fires → heartbeat.py evaluates priority:
  URGENT:   Schedule event within 48h → review related pages
  TARGETED: Active workspace with pages → deepen analysis, find gaps
  CURIOUS:  Known gaps → investigate cross-references
  BORED:    Nothing pressing → explore new disciplines

Decision → prompt → same engine as conversation (with all 29 tools)
  → Maestro works (reads plans, cross-references, takes notes)
  → If finding is worth sharing → iMessage to super
  → WebSocket emit: heartbeat + finding events
```

### 4. Compaction (automatic, after every exchange)

```
Estimate token usage from message history
  → If > 65% of active model's context window:
      Keep last 20 messages in full
      Older messages → Gemini Flash summary
      Delete old message rows from DB
      Update conversation_state with new summary
      → WebSocket emit: compaction event
```

### 5. Brain Switch (conversational)

```
Super texts "switch to flash"
  → AI calls switch_engine tool
  → Provider/model/context-limit swapped live
  → Conversation history preserved
  → Compaction re-checked (models have different context sizes)
  → WebSocket emit: engine_switch event
```

## API Layer

### REST (14 endpoints, read-only)

All under `/api`, powered by the database + in-memory knowledge store:

- **Project:** `GET /project` — metadata + knowledge stats + active engine
- **Workspaces:** `GET /workspaces`, `GET /workspaces/:slug` — list + detail with pages/notes
- **Schedule:** `GET /schedule`, `GET /schedule/upcoming?days=N`, `GET /schedule/:id`
- **Conversation:** `GET /conversation` (state + stats), `GET /conversation/messages?limit=N&before=ID`
- **Knowledge:** `GET /knowledge/disciplines`, `GET /knowledge/pages?discipline=X`, `GET /knowledge/pages/:name`, `GET /knowledge/search?q=X`
- **Health:** `GET /health` — status, engine, project_id, tool count

### WebSocket (`/ws`)

8 event types pushed to connected clients:
`message`, `heartbeat`, `finding`, `workspace`, `schedule`, `compaction`, `engine_switch`, `status`

Thread-safe via `broadcast_sync()` for heartbeat/tool emissions from background threads.

## Frontend

React (Vite + Tailwind) — the super's window into Maestro's brain.

- **Auth:** Google OAuth via Supabase → JWT
- **Home:** Project overview, active workspaces, upcoming schedule, live activity feed
- **Workspaces:** Browse workspaces → drill into pages + notes
- **Schedule:** Timeline view of events
- **Knowledge:** Browse disciplines/pages, search across the knowledge store
- **Real-time:** WebSocket connection for live updates as Maestro works

Mobile-first. Opened from deep links that Maestro texts to the super.

Dev: `npm run dev` from `frontend/` → Vite on :5173, proxies API/:8000 and WS/:8000.

## Engines

| Name | Provider | Model | Context |
|------|----------|-------|---------|
| `gpt` (default) | OpenAI | GPT-5.2 | 128K |
| `opus` | Anthropic | Claude Opus 4.6 | 1M |
| `gemini` | Google | Gemini 3 Pro | 1M |
| `gemini-flash` | Google | Gemini 3 Flash | 1M |

Switch mid-conversation via text ("switch to opus") or tool call. Conversation history preserved across switches.

## Key Design Decisions

- **One engine, any model.** Provider logic isolated in `providers/`. Adding a model = one config entry + one provider file.
- **One thread, forever.** Every interaction (texts + heartbeats) flows through one conversation. Compaction handles context limits. The running summary IS Maestro's long-term memory.
- **Identity is static, experience is dynamic.** `soul.json` and `tone.json` are denylist. Everything in `experience/` is learned and modifiable by Maestro's tools.
- **Tools registered centrally.** `registry.py` is the single source of truth for 28 tools. `switch_engine` added dynamically (needs `self` reference from Conversation).
- **Knowledge in memory.** Entire project loaded at startup. Fast reads, no DB overhead for the hot path.
- **Heartbeat = same brain.** Heartbeat prompts go through the normal engine with all tools. No separate system.
- **Frontend is read-only.** Web app displays state. All mutations happen through conversation (iMessage or heartbeat).
- **DB for structured state, files for bulk content.** Workspaces, schedule, messages, conversation state → SQLite/Postgres. Knowledge store + identity → files.

## Running Locally

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Set API keys in .env
# GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY
# SENDBLUE_API_KEY_ID, SENDBLUE_API_SECRET_KEY, SENDBLUE_FROM_NUMBER

# 3. Ingest plans (one-time)
python -m maestro.knowledge.ingest /path/to/plans.pdf

# 4. Start ngrok tunnel (for Sendblue webhook)
ngrok http 8000
# → Set webhook URL in Sendblue dashboard

# 5. Start Maestro
python server.py +16823521836

# 6. Start frontend (optional)
cd frontend && npm run dev
```

## Test Suite

303 tests across 5 files:
- `test_db.py` (69) — Models, CRUD, all repository functions
- `test_rewire.py` (130) — Tools delegating to DB correctly
- `test_api.py` (66) — All 14 REST endpoints
- `test_websocket.py` (38) — WebSocket events + broadcast
- `test_workspaces.py` — Workspace-specific edge cases

All use in-memory SQLite. Run: `pytest tests/`
