# CLAUDE.md — Maestro Learning Workspace

## What This Is

This is Sean's personal workspace for learning Python by building Maestro from scratch. Each version (V1→V13) introduces new concepts. This is NOT the production Maestro app (that's `Maestro-Super`).

**Owner:** Sean (learning Python)
**Current version:** V13 (in `maestro python/`)
**History:** V1-V12 preserved in `old/`

## Rules

1. **NEVER modify old version files.** Everything in `old/` is frozen history. V1-V12 are Sean's learning record.
2. **NEVER modify files outside this repo** unless explicitly asked.
3. **Active code lives in `maestro python/`** — that's where V13 is.
4. **V13 spec doc:** `maestro python/v13.md` — the full architecture and implementation plan. Read it before making changes.
5. **Keep it learnable.** Sean is learning. Don't over-engineer. Don't add abstractions he hasn't been taught yet. Code should be readable and obvious.

## Structure

```
Maestro/
├── .env                    # API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY)
├── README.md               # Project overview
├── requirements.txt        # Python dependencies
├── maestro python/         # ← ACTIVE CODE (V13)
│   ├── v13.md              # Full V13 spec — READ THIS FIRST
│   ├── maestro_v13_*.py    # Engine files (one per model provider)
│   ├── experience_v13.py   # Identity/personality config
│   ├── knowledge_v13.py    # Loads knowledge_store/ into memory
│   ├── tools_v13.py        # All tool declarations + functions
│   ├── vision.py           # Agentic vision tools (Gemini code execution)
│   ├── gemini_service.py   # Pass 1 + Pass 2 Gemini calls
│   ├── ingest.py           # CLI: PDF → PNG → Pass 1 → Pass 2 → knowledge_store/
│   └── prompts/            # Pass 1 and Pass 2 prompt templates
├── old/                    # ← FROZEN HISTORY (V1-V12)
│   ├── maestro.py          # V1-V6
│   ├── maestro_v7.py       # V7: Agentic tool use
│   ├── maestro_v8.py       # V8: Interactive chat loop
│   ├── maestro_v9.py       # V9: Engine/identity separation
│   ├── maestro_v10.py      # V10: Learning tool
│   ├── maestro_v11.py      # V11: Knowledge extraction
│   ├── maestro_v12_*.py    # V12: Multi-model engines
│   └── ...                 # Supporting files for each version
└── knowledge_store/        # Generated data from ingest (not in git)
```

## Key Architecture (V13)

- **Ingest pipeline:** `python ingest.py "D:\Plans\..."` → PDF→PNG→Gemini Pass 1→Pass 2→knowledge_store/
- **Three engines:** Gemini (`maestro_v13_gemini.py`), Claude (`maestro_v13_opus.py`), GPT (`maestro_v13_gpt.py`)
- **Knowledge tools:** Read from in-memory project data (loaded from JSON files at startup)
- **Vision tools:** Call Gemini on-demand with code execution for live image inspection
- **Full trace capture:** Every Gemini call captures text, code, code_result (with outcome), and images. All persisted to disk.
- **No forced JSON:** No `response_mime_type="application/json"` anywhere. Gemini outputs naturally; we parse structured data from text.

## Agentic Vision — Gemini Code Execution

Maestro's vision system is built on Gemini's code execution API. Before working on any vision-related code (`vision.py`, `gemini_service.py`, prompts), read:

- **Code Execution docs:** https://ai.google.dev/gemini-api/docs/code-execution
- **Gemini 3 model info:** https://ai.google.dev/gemini-api/docs/gemini-3
- **Gen AI SDK (Python):** https://ai.google.dev/gemini-api/docs/libraries

### Key facts

- **4 response part types:** `part.text`, `part.executable_code`, `part.code_execution_result`, `part.as_image()` — capture ALL of them, always.
- **`code_execution_result` has `.outcome`** — `OUTCOME_OK` or `OUTCOME_FAILED`. Model retries failed code up to 5 times. A single response can have multiple code→result cycles.
- **Code execution + Thinking must both be enabled** for image I/O (Gemini 3).
- **Sandbox has PIL, numpy, opencv, matplotlib, scipy, scikit-learn, pandas** — Gemini can crop, zoom, annotate, measure, do pixel math.
- **30-second runtime limit** per code execution block.
- **No `response_mime_type="application/json"`** — this kills code execution output. Let Gemini output naturally.
- **Images are inline** in response parts, interleaved with text and code. Order matters.
- **Model implicitly zooms** when details are too small. Prompt explicitly for other tasks (counting, rotating, annotating).

### Our pattern

Every Gemini call uses `_collect_response()` → `_save_trace()` from `gemini_service.py`. Full trace (thinking, code, results, images) persisted to disk as JSON + PNG files. No exceptions.

## Test Data

- Plan set: `D:\MOCK DATA\Chick-fil-A Love Field FSU 03904 -CPS` (~87 pages)
