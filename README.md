# Maestro

Maestro is a construction-plan assistant with multi-model chat engines and a V13 ingestion pipeline.

## Environment

Create a `.env` file in repo root with:

- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Install dependencies:

```bash
pip install -r requirements.txt
```

## V13 Ingestion

Run from `maestro python/`:

```bash
python ingest.py "D:\Plans\CFA Love Field"
```

This generates:

```text
knowledge_store/{project}/
  project.json
  index.json
  pages/{page}/
    page.png
    pass1.json
    pointers/{region}/
      crop.png
      pass2.json
      trace_*.png
```

## V13 Engines

From `maestro python/`:

```bash
python maestro_v13_gemini.py
python maestro_v13_opus.py
python maestro_v13_gpt.py
```

## Notes

- V12 files remain available and are not replaced by V13.
- If no ingested project exists, V13 tools return explicit "No project loaded" messages.
