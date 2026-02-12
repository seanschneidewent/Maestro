"""Test Maestro's architectural knowledge — run queries, capture tool calls and responses."""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "maestro python"))

from engine.maestro_v13_gemini import build_system_prompt, process_message, _build_gemini_tool_declarations, tool_functions
import google.generativeai as genai

# Monkey-patch tool functions to log calls
_call_log = []
_original_functions = dict(tool_functions)

def _make_logged(name, fn):
    def logged(*args, **kwargs):
        start = time.time()
        result = fn(*args, **kwargs)
        elapsed = time.time() - start
        _call_log.append({"tool": name, "args": kwargs or (args[0] if args else {}), "time_s": round(elapsed, 2)})
        print(f"  [Tool] {name}({kwargs or args}) -> {str(result)[:200]}")
        return result
    return logged

for name, fn in _original_functions.items():
    tool_functions[name] = _make_logged(name, fn)

sp = build_system_prompt()
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction=sp,
    tools=_build_gemini_tool_declarations(),
)

queries = [
    "What architectural sheets do we have?",
    "Give me an overview of the egress plan.",
    "What's getting demolished on the demolition RCP?",
    "What are the travel distances on the egress plan?",
    "What door hardware sets are specified in the door schedule?",
    "What type of roof system is specified?",
    "What are the exterior wall materials shown on the elevations?",
    "What floor finishes are called out on A111?",
    "Tell me about the refuse enclosure — what are the details?",
    "What's the Tormax door detail on A401?",
]

results = []

for i, query in enumerate(queries):
    print(f"\n{'='*60}")
    print(f"Query {i+1}/{len(queries)}: {query}")
    print(f"{'='*60}")
    
    _call_log.clear()
    chat = model.start_chat()  # Fresh chat per query
    
    start = time.time()
    response = process_message(chat, query)
    elapsed = round(time.time() - start, 1)
    
    print(f"\nMaestro ({elapsed}s): {response}")
    
    result = {
        "id": f"arch_{i+1:03d}",
        "query": query,
        "tools_called": list(_call_log),
        "tool_count": len(_call_log),
        "response": response,
        "response_time_s": elapsed,
        "response_length": len(response),
    }
    results.append(result)
    
    # Brief pause to avoid rate limits
    time.sleep(1)

# Save results
out_path = Path("maestro python/benchmarks/results")
out_path.mkdir(parents=True, exist_ok=True)
with open(out_path / "arch_gemini_test1.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for r in results:
    tools = ", ".join(c["tool"] for c in r["tools_called"]) or "none"
    print(f"  Q{r['id'][-3:]}: {r['response_time_s']}s | {r['tool_count']} tools ({tools}) | {r['response_length']} chars")
print(f"\nResults saved to {out_path / 'arch_gemini_test1.json'}")
