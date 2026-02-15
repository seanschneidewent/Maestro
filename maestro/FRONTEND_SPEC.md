# FRONTEND_SPEC.md — Maestro Web App

## The Vision

Maestro has two faces:
- **iMessage** — Maestro's voice. It talks to you.
- **Web app** — Maestro's desk. You see what it's been working on.

The super receives a link, creates an account, and Maestro takes over from there — texting them, walking their plans, reporting findings. The web app is where they manage their project, upload plans, and see Maestro's work.

---

## User Journey

### 1. Invitation
- Super receives a link from someone they know (GC, PM, another super)
- Or: Super finds Maestro through marketing and signs up directly

### 2. Auth Screen
- Lands on clean auth page
- **Phone number first** — this is the primary identity (Maestro texts you here)
- **Google OAuth** for account creation (fast, everyone has it)
- Supabase handles auth + JWTs
- After auth: Supabase stores user (phone, email, name, Google ID)

### 3. Onboarding — Plan Upload
- Maestro's first job: help you upload your plans
- **Upload sources:**
  - Google Drive picker (most plans live in shared drives)
  - Device file upload (PDF from Files app)
- Upload triggers ingest pipeline (PDF → knowledge store)
- Progress indicator while Maestro reads the plans
- Once ingest completes: Maestro texts the super introducing itself

### 4. Maestro Takes Over
- Maestro sends first iMessage: "Hey — I just finished reading your plans. I found [X] pages across [Y] disciplines. I'm going to start reviewing them now. I'll text you when I find something worth knowing."
- From here: iMessage is the primary interface
- Heartbeats run, Maestro proactively reviews, texts findings

### 5. Web App (Ongoing)
- Super can always open the web app to see:
  - **Workspaces** — Maestro's active investigations
  - **Schedule** — What's coming up, what Maestro is watching
  - **Knowledge** — Browse the plans, search, see details
  - **Findings feed** — Stream of what Maestro has discovered
- Maestro texts deep links: "Found a coordination gap → [link to workspace]"

---

## Architecture Decisions

### Auth: Supabase
- Supabase project: `ybyqobdyvbmsiehdmxwp`
- Auth providers: Google OAuth + phone (for future SMS OTP)
- JWTs for API auth (frontend sends `Authorization: Bearer <jwt>`)
- Row-Level Security (RLS) on all tables
- Phone number stored in user profile (used for Sendblue routing)

### Frontend Stack
- **React** (Vite) — fast, simple
- **Tailwind CSS** — utility-first, mobile-responsive
- **Supabase JS client** — auth + realtime
- Lives in `Maestro/frontend/`
- Builds to static files, served by FastAPI in prod (or separate CDN)

### API Auth Flow
1. Frontend authenticates via Supabase (Google OAuth)
2. Gets Supabase JWT
3. Sends JWT in `Authorization` header to Maestro API
4. Maestro API validates JWT against Supabase (verify signature)
5. Extracts user_id, looks up project association
6. Returns scoped data

### Local Dev
- Frontend: `npm run dev` → `localhost:5173`
- Backend: `python server.py` → `localhost:8000`
- Vite proxies `/api` and `/ws` to `localhost:8000`
- Auth still goes through Supabase (works from localhost)

### Production
- Frontend: static build served by CDN or FastAPI
- Backend: FastAPI on a server (or serverless)
- Domain: TBD (maestro.viewm4d.com? app.maestroconstruction.ai?)
- HTTPS required (Supabase OAuth needs it)

---

## Data Model Changes (Supabase)

Current local SQLite models need Supabase equivalents:

```
users (Supabase auth.users + profile)
  - id (UUID, from Supabase auth)
  - phone_number (required — Maestro texts here)
  - display_name
  - company
  - created_at

projects
  - id
  - user_id (FK → users)  ← NEW: projects belong to users
  - name
  - plan_source (google_drive | upload)
  - ingest_status (pending | processing | complete | failed)
  - page_count, pointer_count (cached stats)
  - created_at

-- Everything else stays the same, scoped by project_id
-- RLS policies scope by user_id through project ownership
```

---

## Pages / Routes

```
/                     → Landing / marketing (if logged out)
/auth                 → Auth screen (phone + Google OAuth)
/onboarding           → Plan upload flow (after first auth)
/app                  → Main app shell (authenticated)
/app/workspaces       → All workspaces (cards)
/app/workspaces/:slug → Workspace detail (pages, notes, findings)
/app/schedule         → Schedule view
/app/knowledge        → Plan browser (by discipline)
/app/knowledge/:page  → Page detail (with image?)
/app/search           → Search across knowledge store
/app/settings         → Account, phone number, engine preference
```

---

## What Maestro Texts (Deep Links)

```
"Hey — I found a coordination gap in the foundation. Take a look:
https://app.maestro.ai/app/workspaces/foundation_framing"

"Your schedule shows a pour in 2 days. Here's what I'm watching:
https://app.maestro.ai/app/schedule"

"I just finished reviewing the kitchen plans. 3 new findings:
https://app.maestro.ai/app/workspaces/kitchen_rough_in"
```

---

## Build Order

### Phase 1: Scaffold + Auth (minimum viable)
- [ ] Vite + React + Tailwind + Supabase JS
- [ ] Auth page (Google OAuth via Supabase)
- [ ] Phone number capture (post-auth profile step)
- [ ] Protected route wrapper
- [ ] API middleware: JWT validation on FastAPI side

### Phase 2: Plan Upload
- [ ] Upload page (drag-and-drop PDF)
- [ ] Google Drive picker integration
- [ ] Trigger ingest pipeline from upload
- [ ] Progress/status polling
- [ ] First Maestro text after ingest completes

### Phase 3: Core Views
- [ ] Workspaces list (cards with page count, note count, last updated)
- [ ] Workspace detail (pages, notes, findings)
- [ ] Schedule view (timeline or list)
- [ ] Knowledge browser (disciplines → pages → detail)
- [ ] Search

### Phase 4: Real-Time
- [ ] WebSocket connection from frontend
- [ ] Live feed of messages/findings/heartbeats
- [ ] Toast notifications for new findings
- [ ] Auto-refresh workspace when Maestro updates it

### Phase 5: Polish
- [ ] Plan page images in workspace (PNG viewer)
- [ ] Region highlighting on plan images
- [ ] Mobile optimization (this is THE platform)
- [ ] Push notifications (PWA?)

---

## Open Questions

1. **Multi-project:** Can a super have multiple projects? (Probably yes eventually)
2. **Sharing:** Can a super share a workspace link with their PM? (Read-only viewer?)
3. **Plan images:** Serve PNGs from FastAPI? Or upload to Supabase Storage?
4. **Ingest compute:** Where does ingest run? Local machine? Cloud function? This is the heaviest operation.
5. **Domain:** What URL does the super see in their texts?

---

*Created: 2026-02-13*
