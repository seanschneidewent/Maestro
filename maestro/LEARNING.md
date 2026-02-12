# Maestro Learning System — Architecture Spec

## 1. Vision

Every workspace Maestro builds is a claim about the plans. "This hood mounts at 64" AFF." "The duct is 16 GA black steel." "Ansul fusible links are 450°F." These claims are either grounded in the plans or they're not.

The Learning System is Maestro's self-discipline. It runs automatically in the background after every workspace build and after every direct user correction. It extracts claims, sends Gemini agentic vision to verify them against the actual plan sheets, scores the results, and patches the system — knowledge store, tool descriptions, and experience — so that the next workspace Maestro builds is sharper than the last.

The superintendent never interacts with Learning. They talk to Maestro. One voice, one relationship. Learning hums in the background, visible only as a single ambient status line at the bottom of the terminal. Maestro gets smarter mid-conversation because Learning is continuously writing corrections and enrichments into the system Maestro reads from.

---

## 2. Architecture Overview

### Roles

| | Maestro (Opus) | Learning (GPT 5.2) | Vision (Gemini) |
|---|---|---|---|
| **Role** | Superintendent's partner | Auditor / system sharpener | The eyes |
| **Knowledge tools** | ✅ read | ✅ read | — |
| **Workspace tools** | ✅ create, add, remove, note | ❌ | — |
| **Vision** | ❌ | ✅ spawns missions | ✅ executes missions |
| **Knowledge editing** | ❌ | ✅ patch regions, enrich pointers | — |
| **Tool description editing** | ❌ | ✅ rewrite tool hints in experience | — |
| **Experience editing** | ❌ | ✅ update patterns, disciplines, lessons | — |

### The Flow

```
Superintendent asks Maestro to build a workspace
        │
        ▼
Maestro (Opus) builds workspace — pages, notes, watch items
        │
        ▼
Workspace build triggers queue entry (automatic)
        │
        ▼
Learning agent (GPT 5.2) picks up queue entry
        │
        ├── Extracts verifiable claims from workspace
        │
        ├── Builds vision missions per claim
        │
        ├── Sends missions to Gemini agentic vision
        │
        ├── Scores results: grounded / corrected / enriched / conflict
        │
        └── Patches the system (in order):
            1. Knowledge store (fix/enrich source data)
            2. Tool descriptions (sharpen how tools are used)
            3. Experience (distilled lessons and patterns)
        │
        ▼
Status bar updates at bottom of terminal
Maestro reads from patched system on next tool call — just smarter
```

### Two Trigger Paths

1. **Workspace built** → automatic. Any time workspace tools fire during a Maestro turn, the full workspace state gets queued for verification.
2. **User correction** → Maestro packages the user's feedback + its own context and queues it. Learning processes the correction, verifies it with vision, and patches accordingly.

---

## 3. Folder Structure

### Code (`maestro/`)

```
maestro/
├── engine/                         # Maestro's mind — chat engines
│   ├── maestro_v13_opus.py              # PRIMARY — superintendent's partner
│   ├── maestro_v13_gpt.py              # Alternate engine
│   ├── maestro_v13_gemini.py           # Alternate engine
│   └── __init__.py
│
├── learning/                       # NEW — Learning system
│   ├── agent.py                         # GPT 5.2 learning agent — core loop
│   ├── claims.py                        # Claim extraction from workspaces
│   ├── missions.py                      # Vision mission builder
│   ├── scorer.py                        # Scores verification results
│   ├── patcher.py                       # Writes patches to knowledge/experience/tools
│   ├── queue.py                         # Queue worker — watches queue, processes sequentially
│   ├── status.py                        # Status bar — writes current state for terminal display
│   ├── prompts/
│   │   ├── extract_claims.txt           # System prompt for claim extraction
│   │   ├── build_missions.txt           # System prompt for mission building
│   │   ├── score_results.txt            # System prompt for scoring
│   │   └── generate_patches.txt         # System prompt for patch generation
│   └── __init__.py
│
├── identity/                       # Who Maestro IS (read by engine, written by learning)
│   ├── experience_v13.py               # Loads the experience tree
│   ├── experience/                     # The JSON tree
│   │   ├── soul.json
│   │   ├── tone.json
│   │   ├── tools.json                  # ← Learning can update tool hints here
│   │   ├── patterns.json               # ← Learning writes cross-discipline patterns
│   │   ├── disciplines/
│   │   │   ├── architectural.json
│   │   │   ├── structural.json
│   │   │   ├── mep.json
│   │   │   ├── kitchen.json
│   │   │   ├── civil.json
│   │   │   ├── canopy.json
│   │   │   └── vapor_mitigation.json
│   │   └── learning_log.json           # Append-only log of all learning actions
│   └── __init__.py
│
├── knowledge/                      # Project data (written by ingest + learning)
│   ├── ingest.py
│   ├── gemini_service.py
│   ├── knowledge_v13.py
│   ├── prompts/
│   │   ├── pass1.txt
│   │   └── pass2.txt
│   └── __init__.py
│
├── tools/                          # Maestro's tools (read-only + workspace CRUD)
│   ├── tools_v13.py                    # Knowledge tools
│   ├── vision.py                       # Maestro's own vision (see_page, see_pointer)
│   ├── workspaces.py                   # Workspace management
│   └── __init__.py
│
├── tests/
└── benchmarks/
```

### Data (root level)

```
Maestro/
├── maestro/                  # Code
├── knowledge_store/          # Project knowledge (written by ingest + learning)
├── workspaces/               # Workspace data (written by Maestro)
├── learning_queue/           # NEW — queue files
│   ├── pending/              # Waiting to be processed
│   │   └── 20260212T014245_workspace_fryer_hoods.json
│   ├── processing/           # Currently being worked on
│   └── done/                 # Completed (kept for audit trail)
│       └── 20260212T014245_workspace_fryer_hoods.json
├── learning_status.json      # NEW — current status for terminal display
├── chat.py
└── .env
```

---

## 4. Queue System

### Queue Entry Schema — Workspace Trigger

```json
{
  "id": "20260212T014245_workspace_fryer_hoods",
  "type": "workspace",
  "timestamp": "2026-02-12T01:42:45",
  "workspace_slug": "fryer_hoods_full_install",
  "workspace_path": "workspaces/fryer_hoods_full_install",
  "pages": ["M904", "M502", "M905", "K001", ...],
  "notes": [
    {
      "text": "Hood #1 mounts DIFFERENT from #2-4...",
      "source_page": "M904"
    }
  ],
  "status": "pending"
}
```

### Queue Entry Schema — Feedback Trigger

```json
{
  "id": "20260212T015530_feedback",
  "type": "feedback",
  "timestamp": "2026-02-12T01:55:30",
  "user_message": "that's wrong, the hood is 66 inches not 64",
  "maestro_context": "I told the user hood mounts at 64 AFF based on M-904 region r_0.12_0.08",
  "relevant_pages": ["M904"],
  "status": "pending"
}
```

### File Lifecycle

1. Engine writes JSON to `learning_queue/pending/`
2. Queue worker picks up oldest file, moves to `processing/`
3. Learning agent runs (claim extraction → vision → scoring → patching)
4. Worker moves file to `done/` with results appended
5. If worker crashes mid-process, file stays in `processing/` — restart picks it up

### Single Writer Guarantee

One queue worker process. Processes files sequentially. No parallel writes to experience or knowledge store. File system move (`pending/` → `processing/`) is the lock.

---

## 5. Claim Extraction

When Learning picks up a workspace queue entry, GPT 5.2 reads the workspace data (pages.json + notes.json) and extracts every verifiable claim.

### What Counts as a Claim

- **Dimensional:** "hood bottom at 64" AFF", "duct 16 GA", "collar 14"×8""
- **Material:** "black steel", "430 S.S.", "Fyrewrap"
- **Model/Part:** "Halton KVL-2", "Ansul R-102", "Henny Penny PFE-500"
- **Specification:** "473 CFM", "450°F fusible links", "0.72A blower"
- **Coordination:** "GC owns penetrations", "mech contractor installs hoods"
- **Location:** "fryer connections at 2'-0" AFF", "pull station at 4'-0" AFF"

### What Doesn't Count

- Subjective opinions ("clearances are tight")
- General descriptions ("this sheet covers kitchen equipment")
- Procedural advice ("field verify before fabrication") — these are good advice but not verifiable against a sheet

### Claim Schema

```json
{
  "claim_id": "c_001",
  "text": "Hood H-1L mounts at 64\" AFF (bottom of hood)",
  "source_page": "M904_Mechanical_Specifications_p001",
  "source_note_index": 0,
  "claim_type": "dimensional",
  "verification_priority": "high"
}
```

### Priority

- **high** — dimensions, specs, part numbers (wrong = real money)
- **medium** — materials, coordination responsibilities
- **low** — general references, cross-sheet mentions

---

## 6. Verification Missions

For each claim (or batch of related claims on the same sheet), GPT builds a vision mission — a targeted instruction for Gemini agentic vision.

### Mission Schema

```json
{
  "mission_id": "m_001",
  "claim_ids": ["c_001", "c_003"],
  "target_page": "M904_Mechanical_Specifications_p001",
  "instruction": "Find the hood mounting height dimension. Look for 'AFF' or 'above finished floor' near the hood elevation or section view. Also find the hood collar dimensions — look for the duct connection size in the hood schedule or detail.",
  "expected_values": {
    "c_001": "64\" AFF",
    "c_003": "14\"x8\" collar"
  }
}
```

### How Gemini Executes

Learning calls `gemini_service.py` with:
- The page image (full resolution PNG from knowledge store)
- The mission instruction as the prompt
- Code execution enabled (Gemini can draw, crop, annotate)
- Thinking enabled

Gemini returns:
- Text response with findings
- Any code execution traces
- Any annotated images

All saved to a verification trace file in `done/`.

### Batching

Claims on the same page get batched into one vision mission. No point sending Gemini to the same sheet 5 times for 5 different claims. One mission per page, multiple claims verified per mission.

---

## 7. Scoring

After vision missions return, GPT scores each claim.

### Score Categories

| Score | Meaning | Action |
|---|---|---|
| **verified** | Vision confirmed the exact value | None — claim is grounded |
| **corrected** | Vision found a different value | Patch knowledge store with correct value |
| **enriched** | Vision found additional detail not in knowledge store | Add to knowledge store |
| **ungrounded** | Vision couldn't find any evidence for the claim | Flag in learning log, may update experience |
| **conflict** | Two sheets disagree on the same value | Patch based on source hierarchy (detail > schedule > general notes) |

### Score Schema

```json
{
  "claim_id": "c_001",
  "score": "verified",
  "vision_found": "64\" AFF noted on hood elevation detail",
  "confidence": "high",
  "action_taken": null
}
```

```json
{
  "claim_id": "c_003",
  "score": "conflict",
  "vision_found": "M-904 shows 14\"x8\", M-902 schedule shows 14\"x10\"",
  "confidence": "high",
  "resolution": "detail_sheet_authority",
  "action_taken": "patched M-902 knowledge to 14\"x8\" per detail sheet hierarchy"
}
```

### Source Hierarchy (for automatic conflict resolution)

1. **Detail sheets** — fabrication-level drawings (most authoritative)
2. **Enlarged plans** — zoomed views with dimensions
3. **Schedules** — tabular data (may have transcription errors)
4. **General notes** — project-wide requirements
5. **Specifications** — written spec sections (can be boilerplate from other projects)

Learning applies this hierarchy automatically. If a detail sheet and a schedule disagree, the detail sheet wins. This hierarchy itself lives in `patterns.json` and can be refined by experience.

---

## 8. Patching — The Three Layers

Patching happens in order. Knowledge first, tools second, experience last. Each layer builds on the previous.

### 8a. Knowledge Store Patches

**What Learning can edit:**

- `summary.json` — fix or enrich the sheet reflection text
- `pointers.json` — correct pointer descriptions, add missing pointers
- `regions/r_*.json` — update region descriptions, add detail that was missed during ingest

**Patch schema:**

```json
{
  "patch_id": "p_001",
  "type": "knowledge",
  "target": "knowledge_store/Chick-fil-A.../pages/M902_.../pointers.json",
  "operation": "update",
  "path": "pointers[3].description",
  "old_value": "Hood collar: 14\"x10\"",
  "new_value": "Hood collar: 14\"x8\" (corrected per M-904 detail sheet)",
  "reason": "Vision verification found M-904 detail shows 14\"x8\", M-902 schedule had transcription error",
  "claim_id": "c_003",
  "timestamp": "2026-02-12T01:48:30"
}
```

**Every patch records old_value.** This is an audit trail. If a patch is wrong, it can be reversed.

**What Learning CANNOT edit in knowledge store:**
- Page images (PNG files)
- Pass 1 raw traces (original Gemini output preserved)

### 8b. Tool Description Patches

Learning reads how Maestro used tools during the workspace build (from the queue entry context) and compares against what would have been optimal.

**What Learning can edit:**

- `identity/experience/tools.json` — the tool hints that get injected into Maestro's system prompt

**Example patch:**

```json
{
  "patch_id": "p_002",
  "type": "tool_description",
  "target": "identity/experience/tools.json",
  "tool": "get_region_detail",
  "change": "Added hint: 'When verifying dimensions, prefer regions from detail sheets over schedule sheets. Detail sheets contain fabrication-level accuracy.'",
  "reason": "Maestro cited M-902 schedule for collar dimension when M-904 detail was available and more accurate",
  "timestamp": "2026-02-12T01:48:30"
}
```

**When tool descriptions change:**
- Maestro used the wrong tool for a task
- Maestro used the right tool but on the wrong page (schedule vs detail)
- A tool returned data that Maestro misinterpreted
- A tool wasn't used when it should have been

### 8c. Experience Patches

The distilled lesson. After knowledge is corrected and tool hints are sharpened, Learning writes the pattern it discovered.

**What Learning can edit:**

- `identity/experience/patterns.json` — cross-discipline patterns
- `identity/experience/disciplines/*.json` — discipline-specific lessons

**Example patch:**

```json
{
  "patch_id": "p_003",
  "type": "experience",
  "target": "identity/experience/patterns.json",
  "operation": "add_to_learned",
  "entry": {
    "pattern": "detail_sheet_authority",
    "lesson": "Detail sheets (fabrication drawings) are more accurate than schedules for physical dimensions. When a schedule and detail disagree, trust the detail.",
    "source": "Fryer hoods workspace verification — M-904 vs M-902 collar dimension conflict",
    "confidence": "high",
    "timestamp": "2026-02-12T01:48:30"
  }
}
```

**Experience is the last layer because it's the most abstract.** Knowledge patches fix specific data. Tool patches fix specific behavior. Experience patches encode general wisdom that applies everywhere.

---

## 9. Learning Agent Tools

GPT 5.2 gets these function declarations:

### Knowledge Tools (read-only, same as Maestro)

| Tool | Description |
|---|---|
| `list_pages()` | List all pages in the knowledge store |
| `get_sheet_summary(page)` | Get the sheet reflection for a page |
| `get_sheet_index(page)` | Get the searchable index (keywords, items, cross-refs) |
| `list_regions(page)` | List all regions on a page |
| `get_region_detail(page, region)` | Get full detail for a specific region |
| `search_knowledge(query)` | Semantic search across all pointers |

### Vision Tools (Learning-exclusive)

| Tool | Description |
|---|---|
| `verify_claim(page, instruction, expected)` | Send Gemini agentic vision to a page with a targeted mission. Returns vision findings + trace. |

### Patch Tools (Learning-exclusive)

| Tool | Description |
|---|---|
| `patch_knowledge(target_path, operation, path, old_value, new_value, reason)` | Update a specific field in a knowledge store JSON file. Records old value for audit. |
| `patch_tool_hint(tool_name, hint_text, reason)` | Add or update a tool usage hint in `tools.json`. |
| `patch_experience(target_file, operation, entry, reason)` | Add a learned entry to a patterns or discipline JSON file. |
| `log_learning(action, details)` | Append to `learning_log.json`. Every action gets logged. |

### Status Tool

| Tool | Description |
|---|---|
| `update_status(message)` | Write current status to `learning_status.json` for terminal display. |

---

## 10. Terminal Status Bar

### `learning_status.json`

```json
{
  "active": true,
  "message": "21/23 verified · 1 corrected · 1 enriched · vision reading P-201...",
  "updated_at": "2026-02-12T01:47:15"
}
```

### Terminal Display

The chat loop (`chat.py`) reads `learning_status.json` after every Maestro response and prints the status bar:

```
─────────────────────────────────────────────────────────
 📚 21/23 verified · 1 corrected · 1 enriched · vision reading P-201...
```

If `active` is `false` or the file doesn't exist, no status bar is shown.

The status bar is **read-only from the terminal's perspective**. The super never interacts with it. It's ambient awareness — a pulse that says "Learning is alive and working."

### Status Progression Examples

```
📚 Extracting claims from Fryer Hoods workspace...
📚 12 claims extracted · building vision missions...
📚 Vision verifying claim 3/12 — reading M-904...
📚 Vision verifying claim 8/12 — reading K-602...
📚 Scoring 12 claims...
📚 10/12 verified · 1 corrected · 1 enriched
📚 Patching knowledge store...
📚 Complete ✅ 10/12 verified · 1 corrected · 1 enriched
```

---

## 11. Constraints

### Learning CANNOT:
- Delete pages from workspaces
- Delete pages from knowledge store
- Modify engine code (`.py` files)
- Modify `soul.json` (Maestro's core identity is sacred)
- Interact with the superintendent directly
- Block or slow down Maestro's responses
- Run during ingest (queue pauses if ingest is active)

### Learning CAN:
- Read everything Maestro can read
- Write to knowledge store JSON files (with audit trail)
- Write to experience JSON files (with audit trail)
- Write to `tools.json` hints (with audit trail)
- Append to `learning_log.json`
- Update `learning_status.json`
- Spawn Gemini vision missions
- Resolve conflicts automatically using source hierarchy
- Create new discipline JSON files if a new discipline is discovered

### Safety Rails:
- Every patch records `old_value` — reversible
- `learning_log.json` is append-only — full audit trail
- Queue files are preserved in `done/` — full provenance
- Vision traces are saved — you can see exactly what Gemini saw
- `soul.json` is read-only — Learning cannot change who Maestro is

---

## 12. Implementation Order

### Phase 1: Queue Infrastructure
- Create `learning_queue/` folder structure (pending/processing/done)
- Create `learning/queue.py` — file watcher, lifecycle management
- Create `learning/status.py` — writes `learning_status.json`
- Modify `tools/workspaces.py` — write queue entry to `pending/` after any workspace tool fires
- Modify `chat.py` — read and display `learning_status.json` after each turn
- **Test:** Workspace build creates queue file. Status bar shows in terminal.

### Phase 2: Claim Extraction
- Create `learning/claims.py` — GPT 5.2 reads workspace JSON, extracts claims
- Create `learning/prompts/extract_claims.txt`
- Create `learning/agent.py` — orchestrates the pipeline
- **Test:** Queue entry → claims extracted → logged

### Phase 3: Vision Verification
- Create `learning/missions.py` — builds vision missions from claims
- Create `learning/prompts/build_missions.txt`
- Wire to `knowledge/gemini_service.py` for agentic vision calls
- Save vision traces to queue `done/` entry
- **Test:** Claims → missions → Gemini looks at sheets → findings returned

### Phase 4: Scoring
- Create `learning/scorer.py` — GPT 5.2 scores vision results against claims
- Create `learning/prompts/score_results.txt`
- Implement source hierarchy for automatic conflict resolution
- **Test:** Vision findings → scores → conflicts auto-resolved

### Phase 5: Patching
- Create `learning/patcher.py` — writes patches to knowledge/experience/tools
- Implement `patch_knowledge`, `patch_tool_hint`, `patch_experience`
- Implement audit trail (old_value recording, learning_log.json)
- **Test:** Scores → patches applied → knowledge store updated → experience updated

### Phase 6: Feedback Trigger
- Modify engine to detect user corrections and queue them
- Add `feedback` queue entry type handling in agent.py
- **Test:** User says "that's wrong" → queued → verified → patched

### Phase 7: Integration Test
- Full loop: workspace build → queue → claims → vision → score → patch → Maestro reads patched data on next query
- Verify Maestro's next response reflects the corrections
- Verify status bar shows progression in real time

---

## 13. Environment

- **OS:** Windows 11
- **Python:** Anaconda (base env)
- **Opus:** Claude Opus 4.6 via `anthropic` SDK
- **GPT:** GPT 5.2 via `openai` SDK
- **Gemini:** Gemini 3 Flash via `google-generativeai` SDK
- **Knowledge store:** `C:\Users\Sean Schneidewent\Maestro\knowledge_store\`
- **Workspaces:** `C:\Users\Sean Schneidewent\Maestro\workspaces\`
- **Experience:** `C:\Users\Sean Schneidewent\Maestro\maestro\identity\experience\`
- **API keys:** `.env` file at repo root (GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY)
- **Existing dependencies:** `anthropic`, `openai`, `google-generativeai`, `Pillow`

---

*Written: 2026-02-12 03:00 CST*
*Authors: Sean + Ember*
