# Benchmark Runner Design

## Overview

`run_benchmark.py` — runs queries from JSON files through each engine, captures results in schema format.

## Usage
```bash
# Run one discipline, one engine
python benchmarks/run_benchmark.py --discipline architectural --engine gemini

# Run one discipline, all engines
python benchmarks/run_benchmark.py --discipline architectural --engine all

# Run all disciplines, all engines (full benchmark)
python benchmarks/run_benchmark.py --discipline all --engine all

# Resume (skip already-completed query IDs)
python benchmarks/run_benchmark.py --discipline architectural --engine gemini --resume
```

## Architecture

```
run_benchmark.py
├── load queries from benchmarks/queries_{discipline}.json
├── for each engine:
│   ├── import engine module (maestro_v13_{engine}.py)
│   ├── create chat session (engine-specific)
│   ├── for each query:
│   │   ├── time the full interaction
│   │   ├── monkey-patch tool functions to capture calls
│   │   ├── call process_message(chat, query)
│   │   ├── collect: response text, tools called, timing
│   │   ├── build result record (SCHEMA.md format)
│   │   ├── grounding fields left blank (manual scoring)
│   │   └── append to results/{discipline}_{engine}.json
│   └── print summary stats
└── print cross-engine comparison table
```

## Key Design Decisions

### 1. Tool Call Capture
Wrap each tool function to log calls:
```python
def make_logged_tool(name, original_fn):
    def logged(*args, **kwargs):
        start = time.time()
        result = original_fn(*args, **kwargs)
        elapsed_ms = int((time.time() - start) * 1000)
        call_log.append({"name": name, "args": kwargs or dict(zip(param_names, args)), "time_ms": elapsed_ms})
        return result
    return logged
```

### 2. Fresh Chat Per Query
Each query gets a fresh chat session — no conversation history bleed.
This matches real-world "new question" behavior.

### 3. Engine Initialization
Each engine has different setup:
- **Gemini**: `genai.GenerativeModel(...).start_chat()`
- **Opus**: `anthropic.Anthropic().messages` (stateless, accumulate messages)
- **GPT**: `openai.OpenAI().chat.completions` (stateless, accumulate messages)

The runner needs an `init_engine(name)` that returns a standardized interface.

### 4. Output Format
Results saved incrementally — one record appended after each query completes.
If the script crashes mid-run, completed queries are preserved.

File: `benchmarks/results/{discipline}_{engine}.json`

### 5. Grounding Verification
Automated where possible:
- **Tool selection score**: Compare `tools_called` names vs `expected_tools` from query file
- **Sheet citation check**: Does response mention specific sheet names?
- **Grounding score**: LEFT BLANK — requires manual review against knowledge store

Manual scoring fields in output:
```json
"grounding": {
    "score": null,          // Fill manually: 0.0-1.0
    "sources_verified": [],  // Auto-populated from tool calls
    "facts_correct": [],     // Fill manually
    "hallucinations": [],    // Fill manually  
    "missed_facts": [],      // Fill manually
    "notes": ""
}
```

### 6. Automated Metrics (no human needed)
- `tool_call_count` — how many tools called
- `tool_selection_match` — % overlap with expected_tools
- `total_response_time_s` — wall clock
- `response_length` — character count
- `cited_sheets` — boolean, did it mention sheet names
- `answered_question` — boolean, is response non-empty and non-error

### 7. Summary Output
After each discipline+engine run, print:
```
=== Architectural × Gemini ===
Queries: 10 | Avg time: 4.2s | Avg tools: 2.8
Tool match: 85% | Cited sheets: 90%
Errors: 0
```

After all engines for a discipline:
```
=== Architectural Cross-Engine ===
           Gemini   Opus    GPT
Avg time:  4.2s    6.1s    5.3s
Avg tools: 2.8     3.1     2.5
Tool match: 85%    90%     80%
Sheet cite: 90%    100%    85%
Errors:     0       0       1
```

## Dependencies
- Engine modules (after import fixes applied)
- Knowledge store (after ingest complete)
- Query files (already written)
- `.env` with all 3 API keys

## File Structure
```
benchmarks/
├── SCHEMA.md                    # Record format
├── RUNNER_DESIGN.md             # This file
├── queries_architectural.json   # 10 queries
├── queries_structural.json      # 8 queries
├── queries_mep.json             # 8 queries
├── queries_civil.json           # 8 queries
├── queries_kitchen.json         # 6 queries
├── queries_canopy.json          # 6 queries
├── queries_vapor_mitigation.json # 6 queries
├── run_benchmark.py             # Runner script (to build)
└── results/                     # Output (created by runner)
    ├── architectural_gemini.json
    ├── architectural_opus.json
    ├── architectural_gpt.json
    └── ...
```

## Implementation Order
1. Build `run_benchmark.py` with Gemini engine only (simplest — native tool use)
2. Add Opus engine (message-based tool use, different protocol)
3. Add GPT engine (similar to Opus)
4. Add cross-engine comparison output
5. Add `--resume` flag for crash recovery
