# knowledge/ — What Maestro Knows

The ingest pipeline and knowledge loader. Takes raw PDF plan sets and turns them into structured, searchable knowledge.

## Files

- **ingest.py** — The ingest pipeline. PDF → PNG → Gemini Pass 1 → Pass 2 → knowledge_store/. Standalone masterpiece. Do not touch without good reason.
- **loader.py** — Loads a project from knowledge_store/ into an in-memory dict at startup. All knowledge tools read from this dict.
- **gemini_service.py** — Gemini API calls for Pass 1 (page analysis) and Pass 2 (region extraction). Used by ingest.py.
- **prompts/** — Prompt templates for Pass 1 and Pass 2. These shape how Gemini analyzes each page and region.

## Knowledge Store Structure

```
knowledge_store/{project_name}/
├── project.json          # Project metadata
├── index.json            # Aggregated cross-project index
└── pages/
    └── {page_name}/
        ├── page.png      # Original page image
        ├── pass1.json    # Page-level analysis (reflection, regions, index)
        └── pointers/
            └── {region_id}/
                ├── crop.png    # Cropped region image
                └── pass2.json  # Region-level deep extraction
```

## What Does NOT Go Here

- Knowledge query tools (reading from the loaded project) → `tools/knowledge.py`
- Vision tools (on-demand image inspection) → `tools/vision.py`
