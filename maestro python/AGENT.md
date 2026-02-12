# CLAUDE.md — Maestro V13 Active Code

## Read First

**`v13.md`** — the full V13 architecture spec. Every file, every function, every data flow is documented there. Read it before changing anything.

## Rules

1. **NEVER modify files in `../old/`** — that's frozen learning history.
2. **No `response_mime_type="application/json"`** — Gemini outputs naturally. We parse structured data from text via `_extract_json_from_text()`.
3. **Every Gemini call captures full trace** — text, executable_code, code_execution_result (with outcome), and as_image(). Use `_collect_response()` and `_save_trace()` from `gemini_service.py`.
4. **No binary data in JSON files** — pop `_crop_candidates` and `_trace_images` before `json.dump()`. Save bytes to disk as PNG files.
5. **Code execution enabled on every Gemini call** — `tools=[types.Tool(code_execution=types.ToolCodeExecution)]` plus `thinking_config`.
6. **Keep it learnable** — Sean is learning Python through this project. No unnecessary abstractions.

## Files

| File | Purpose |
|------|---------|
| `maestro_v13_gemini.py` | Chat engine — Gemini 3 Pro |
| `maestro_v13_opus.py` | Chat engine — Claude Opus 4.6 |
| `maestro_v13_gpt.py` | Chat engine — GPT-5.2 |
| `experience_v13.py` | Identity/personality config dict |
| `knowledge_v13.py` | Loads `knowledge_store/` JSON into memory at startup |
| `tools_v13.py` | All tool declarations + knowledge tool functions |
| `vision.py` | 4 vision tools: `see_page`, `see_pointer`, `find_missing_pointer`, `double_check_pointer` |
| `gemini_service.py` | `run_pass1()`, `run_pass2()`, `_collect_response()`, `_save_trace()` |
| `ingest.py` | CLI entry point: `python ingest.py "D:\Plans\..."` |
| `prompts/pass1.txt` | Pass 1 prompt template |
| `prompts/pass2.txt` | Pass 2 prompt template |

## Data Flow

```
INGEST: python ingest.py <folder>
  PDF → PNG (PyMuPDF 200 DPI)
  → Pass 1 (Gemini: regions, reflection, index)
  → PIL crop per region
  → Pass 2 (Gemini: deep pointer analysis per crop)
  → knowledge_store/{project}/pages/{page}/pointers/{region}/

CHAT: python maestro_v13_gemini.py
  Loads knowledge_store/ into memory
  → Superintendent asks question
  → Engine uses tools (knowledge from memory, vision on-demand via Gemini)
  → Answers
```

## Trace Capture Pattern

Every Gemini call follows this pattern:
```python
response = client.models.generate_content(...)
collected = _collect_response(response)  # text, images, trace (with outcome)
_save_trace(collected["trace"], collected["images"], directory, prefix="...")
# Save trace JSON
with open(directory / "..._trace.json", "w") as f:
    json.dump(collected["trace"], f, indent=2)
```

## Dependencies

See `../requirements.txt`. Key: `google-genai`, `anthropic`, `openai`, `PyMuPDF`, `Pillow`, `python-dotenv`.

## Test Data

Plan set: `D:\MOCK DATA\Chick-fil-A Love Field FSU 03904 -CPS`
