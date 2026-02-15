# tools/ — What Maestro Can Do

Every tool Maestro can use lives here. Each file is a category of tools. The registry wires them all together for the engine.

## Files

- **registry.py** — Master tool list. ALL tool definitions and function mappings in one place. The engine imports this once. This is the single source of truth.
- **knowledge.py** — Knowledge store query tools. Search, list pages, get summaries, read regions. These read from the in-memory project data loaded at startup.
- **vision.py** — Visual inspection tools. `see_page` and `see_pointer` return images for Opus to see directly. `gemini_vision_agent` dispatches Gemini for deep pixel-level extraction.
- **workspaces.py** — Workspace CRUD. Create workspaces, add/remove pages, add notes. Workspaces persist to disk as JSON in the `workspaces/` directory.
- **learning.py** — Learning tools. `update_experience` modifies experience JSON files. `update_tool_description` adds tool usage tips. `update_knowledge` corrects/enriches the knowledge store. All changes are audit-logged.
- **schedule.py** — Schedule management. Add/update/remove events, view upcoming. iCal-compatible fields for future Google Calendar/Procore integration. Data lives in `workspaces/schedule.json`.

## Adding a New Tool

1. Write the function in the appropriate category file (or create a new one).
2. Add the tool definition to `registry.py` in the appropriate `*_TOOL_DEFINITIONS` list.
3. Wire the function in `build_tool_registry()`.

## What Does NOT Go Here

- Tool definitions scattered in engine files (all go in registry.py)
- Identity/experience logic (goes in identity/)
- Ingest pipeline (goes in knowledge/)
