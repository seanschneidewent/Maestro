# engine/ — How Maestro Thinks

The engine handles the conversation loop: receive user message, call tools as needed, return a response.

## Files

- **engine.py** — The unified engine. Loads project, wires tools, runs the chat loop. Never needs to change when adding a new model.
- **heartbeat.py** — The proactive engine. Decides what Maestro should do when nobody's talking to it. Priority cascade: urgent → targeted → curious → bored. Returns a prompt that gets fed through the normal engine.
- **config.py** — Model switch. Maps engine names to providers and model identifiers. Add new models here.
- **providers/** — One file per API provider. Each handles the translation between our generic tool interface and the provider's specific API format.
  - `anthropic.py` — Claude (Messages API, multimodal tool results)
  - `google.py` — Gemini (function declarations, stateful chat)
  - `openai.py` — GPT (function tools, Chat Completions)

## Adding a New Model

1. If the provider already exists (e.g. another Anthropic model), just add an entry to `config.py`.
2. If it's a new provider, create a new file in `providers/` implementing `create_client()`, `build_tool_schemas()`, and `send_message()`. Then add a provider handler in `engine.py`.

## What Does NOT Go Here

- Tool definitions → `tools/registry.py`
- System prompt → `identity/prompt.py`
- Project loading → `knowledge/loader.py`
