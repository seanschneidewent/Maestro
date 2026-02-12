# Learning Harness V2 — Design Doc

## Current State (learning_v12.py)

- Uses a secondary AI model to rewrite `experience_v13.py` (a Python file)
- String manipulation on Python source code
- Fragile: syntax errors can break the file
- Limited: flat dict, no structure, no domain-specific learning

## New Design: GPT 5.2 Powered, JSON-Based, Hierarchical

### Model

GPT 5.2 — best reasoning model available for deep analysis.

### What the Learning Agent Can Read

1. **Experience tree** (`identity/experience/`) — all JSON files
2. **Knowledge store** (`knowledge_store/`) — pass1.json, pass2.json for context
3. **Benchmark results** (`benchmarks/`) — where Maestro is strong/weak
4. **The query + response that triggered learning** — what happened

### What the Learning Agent Can Write

1. **Discipline JSONs** (`identity/experience/disciplines/*.json`)
   - Add to `learned` array: specific lessons from interactions
   - Update `what_to_watch`: new patterns discovered
   - Update `common_superintendent_questions`: new question types seen

2. **Patterns JSON** (`identity/experience/patterns.json`)
   - Add cross-discipline lessons
   - Add project-specific observations
   - Add benchmark-derived insights

3. **Tone JSON** (`identity/experience/tone.json`)
   - Refine communication principles based on feedback

4. **Tools JSON** (`identity/experience/tools.json`)
   - Improve tool usage strategy based on what works

### Learning Triggers

1. **Explicit feedback** — superintendent says "that's wrong" or "be more specific"
2. **Benchmark gaps** — grounding score below 0.8, hallucinations detected
3. **Self-correction** — Maestro used wrong tools or missed obvious information
4. **New patterns** — cross-reference discovered, coordination issue found

### Learning Flow

```
Trigger (feedback, benchmark, self-correction)
    │
    ▼
Learning Agent (GPT 5.2) receives:
    - The trigger context (query, response, feedback)
    - Current experience tree (all JSONs)
    - Relevant knowledge store data (if applicable)
    - Recent benchmark results (if applicable)
    │
    ▼
Learning Agent decides:
    - WHICH file(s) to update
    - WHAT to add/modify
    - WHY (reasoning logged)
    │
    ▼
Learning Agent outputs:
    {
      "updates": [
        {
          "file": "disciplines/architectural.json",
          "action": "append_to_learned",
          "value": "When asked about demolition, always check both the demo floor plan AND the demo RCP — they show different scope.",
          "reasoning": "Superintendent asked about demo scope and Maestro only checked one sheet."
        }
      ]
    }
    │
    ▼
Harness applies updates:
    - json.load() → modify → json.dump()
    - Log the update to learning_log.json
    - No Python file manipulation
```

### Learning Log

Every learning action gets logged:
`identity/experience/learning_log.json`

```json
[
  {
    "timestamp": "2026-02-11T08:30:00",
    "trigger": "benchmark_gap",
    "query": "What's getting demolished?",
    "engine": "gemini",
    "grounding_score": 0.7,
    "updates": [
      {
        "file": "disciplines/architectural.json",
        "field": "learned",
        "added": "Check both demo floor plan and demo RCP for complete scope"
      }
    ],
    "model": "gpt-5.2"
  }
]
```

### build_system_prompt() Update

Instead of reading a flat Python dict, walk the experience tree:

```python
def build_system_prompt():
    """Assemble system prompt from hierarchical experience JSON."""
    experience_dir = Path(__file__).parent / "identity" / "experience"
    
    prompt_parts = []
    
    # Soul
    soul = json.loads((experience_dir / "soul.json").read_text())
    prompt_parts.append(f"You are {soul['name']}. {soul['role']}.")
    prompt_parts.append(soul['purpose'])
    prompt_parts.append(soul['boundaries'])
    
    # Tone
    tone = json.loads((experience_dir / "tone.json").read_text())
    prompt_parts.append(f"Communication: {tone['style']}")
    for principle in tone.get('principles', []):
        prompt_parts.append(f"- {principle}")
    
    # Tools strategy
    tools = json.loads((experience_dir / "tools.json").read_text())
    prompt_parts.append(f"Tool strategy: {tools['strategy']}")
    prompt_parts.append(f"Search: {tools['search_tips']}")
    prompt_parts.append(f"Vision: {tools['vision_strategy']}")
    
    # Discipline knowledge
    disc_dir = experience_dir / "disciplines"
    if disc_dir.exists():
        for disc_file in sorted(disc_dir.glob("*.json")):
            disc = json.loads(disc_file.read_text())
            prompt_parts.append(f"\n### {disc['discipline']}")
            for item in disc.get('what_to_watch', []):
                prompt_parts.append(f"- Watch: {item}")
            for lesson in disc.get('learned', []):
                prompt_parts.append(f"- Learned: {lesson}")
    
    # Patterns
    patterns = json.loads((experience_dir / "patterns.json").read_text())
    if patterns.get('cross_discipline'):
        prompt_parts.append("\n### Cross-Discipline Patterns")
        for p in patterns['cross_discipline']:
            prompt_parts.append(f"- {p}")
    if patterns.get('project_specific'):
        prompt_parts.append("\n### Project-Specific")
        for p in patterns['project_specific']:
            prompt_parts.append(f"- {p}")
    
    return "\n".join(prompt_parts)
```

### Implementation Plan

1. Write `identity/learning.py` — the new harness
2. Update `build_system_prompt()` in all three engines to walk the JSON tree
3. Remove dependency on `learning_v12.py`
4. Test learning cycle: trigger → GPT 5.2 analysis → JSON update → verify prompt changes
