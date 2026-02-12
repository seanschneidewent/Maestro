# Benchmark Schema

## Per-Query Record

Each benchmark query produces one JSON record per engine tested.
Stored in `benchmarks/{discipline}_{engine}.json` as a JSON array.

```json
{
  "id": "arch_001",
  "query": "What's getting demolished on the RCP?",
  "discipline": "architectural",
  "engine": "gemini",
  "timestamp": "2026-02-11T08:00:00",
  
  "tools_called": [
    {"name": "list_pages", "args": {"discipline": "Architectural"}, "time_ms": 2},
    {"name": "get_sheet_summary", "args": {"page_name": "A002_Demolition_RCP_p001"}, "time_ms": 1},
    {"name": "get_region_detail", "args": {"page_name": "A002_Demolition_RCP_p001", "region_id": "r_20_490_860_950"}, "time_ms": 1}
  ],
  "tool_call_count": 3,
  "total_response_time_s": 6.2,
  
  "response_summary": "Listed all demolition items from the RCP with specific locations.",
  
  "grounding": {
    "score": 0.95,
    "sources_verified": ["A002_Demolition_RCP_p001/pass1.json", "A002_Demolition_RCP_p001/pointers/r_20_490_860_950/pass2.json"],
    "facts_correct": ["Existing ceiling grid removal", "Existing light fixtures to be removed"],
    "hallucinations": [],
    "missed_facts": ["Didn't mention existing HVAC diffusers being removed"],
    "notes": ""
  },
  
  "quality": {
    "answered_question": true,
    "specificity": "high",
    "actionable": true,
    "superintendent_appropriate": true,
    "cited_sheets": true,
    "cited_dimensions": false,
    "tone_correct": true
  },
  
  "learning_action": null
}
```

## Grounding Score Guide

- **1.0** — Every fact in the response is verified in the knowledge store. No hallucinations. No missed important facts.
- **0.9** — All facts correct, minor omission that wouldn't affect the superintendent's work.
- **0.8** — All facts correct, meaningful omission (missed a material, dimension, or cross-reference).
- **0.7** — Mostly correct, one soft hallucination (stated something plausible but not in the plans).
- **0.6** — Mix of correct and incorrect. Some hallucination.
- **0.5 or below** — Unreliable. Major hallucinations or fundamentally wrong answer.

## Query Set Design

Each discipline gets 5-8 queries at varying difficulty:

1. **Orientation** — "What sheets are in the [discipline] set?" (tests list_pages)
2. **Summary** — "Give me an overview of [sheet]" (tests get_sheet_summary)
3. **Specific fact** — "What are the [dimensions/materials/specs] for [item]?" (tests get_region_detail + search)
4. **Cross-reference** — "What other sheets reference [sheet]?" (tests find_cross_references)
5. **Cross-cutting search** — "Where is [material/term] used across the project?" (tests search)
6. **Coordination** — "Are there any conflicts between [discipline A] and [discipline B]?" (tests multi-tool reasoning)
7. **Vision** — "Look at [page] and tell me what you see" (tests see_page/see_pointer)
8. **Gap check** — "What's missing or incomplete?" (tests check_gaps)

Same queries run on all three engines. Results compared side by side.

## Aggregate Summary

After each discipline is benchmarked, generate:
`benchmarks/{discipline}_summary.json`

```json
{
  "discipline": "architectural",
  "total_queries": 8,
  "engines": {
    "gemini": {
      "avg_grounding_score": 0.91,
      "avg_response_time_s": 5.4,
      "avg_tool_calls": 2.8,
      "hallucination_count": 0,
      "missed_facts_count": 2
    },
    "opus": { ... },
    "gpt": { ... }
  },
  "best_engine_overall": "gemini",
  "notes": "Gemini excels at spatial questions. Opus gives most thorough answers but slower."
}
```
