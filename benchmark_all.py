"""Beast Mode Benchmark — Run architectural queries through all 3 engines."""
import sys
import json
import time
import os
from pathlib import Path

# Fix Windows encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent / "maestro python"))

# ============================================================
# ENGINE SETUP
# ============================================================

def setup_gemini():
    """Initialize Gemini engine, return (process_message, create_chat) tuple."""
    from engine.maestro_v13_gemini import (
        build_system_prompt, process_message, _build_gemini_tool_declarations, tool_functions
    )
    import google.generativeai as genai

    sp = build_system_prompt()
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=sp,
        tools=_build_gemini_tool_declarations(),
    )

    def create_chat():
        return model.start_chat()

    return process_message, create_chat, tool_functions, "gemini"


def setup_opus():
    """Initialize Opus engine, return (process_message_wrapper, create_chat) tuple."""
    from engine.maestro_v13_opus import (
        build_system_prompt, process_message as _opus_process, _build_claude_tools, tool_functions
    )
    claude_tools = _build_claude_tools()

    def create_chat():
        return []  # message list

    def process_message(chat, query):
        chat.append({"role": "user", "content": query})
        response, text = _opus_process(chat, claude_tools)
        return text

    return process_message, create_chat, tool_functions, "opus"


def setup_gpt():
    """Initialize GPT engine, return (process_message_wrapper, create_chat) tuple."""
    from engine.maestro_v13_gpt import (
        build_system_prompt, process_message as _gpt_process, _build_openai_tools, tool_functions
    )
    openai_tools = _build_openai_tools()
    sp = build_system_prompt()

    def create_chat():
        return [{"role": "system", "content": sp}]

    def process_message(chat, query):
        chat.append({"role": "user", "content": query})
        response, text = _gpt_process(chat, openai_tools)
        return text

    return process_message, create_chat, tool_functions, "gpt"


# ============================================================
# TOOL CALL LOGGING
# ============================================================

call_log = []

# Vision tools make live Gemini API calls — skip for knowledge benchmarks
SKIP_TOOLS = {"see_page", "see_pointer", "find_missing_pointer", "double_check_pointer"}

def make_logged(name, original_fn):
    def logged(*args, **kwargs):
        if name in SKIP_TOOLS:
            msg = f"[Vision tool '{name}' disabled for benchmark — use knowledge tools instead]"
            call_log.append({"tool": name, "args": {}, "time_s": 0, "skipped": True})
            print(f"    [{name}] SKIPPED (vision tool)")
            return msg
        start = time.time()
        try:
            result = original_fn(*args, **kwargs)
        except Exception as exc:
            result = f"ERROR: {exc}"
        elapsed = time.time() - start
        entry = {"tool": name, "args": kwargs if kwargs else (dict(zip(["arg0","arg1","arg2"], args)) if args else {}), "time_s": round(elapsed, 3)}
        call_log.append(entry)
        preview = str(result)[:150].replace("\n", " ")
        print(f"    [{name}] {elapsed:.2f}s -> {preview}")
        return result
    return logged


def patch_tools(tool_functions):
    """Wrap all tool functions with logging."""
    originals = {}
    for name, fn in list(tool_functions.items()):
        originals[name] = fn
        tool_functions[name] = make_logged(name, fn)
    return originals


def unpatch_tools(tool_functions, originals):
    """Restore original tool functions."""
    for name, fn in originals.items():
        tool_functions[name] = fn


# ============================================================
# QUERIES
# ============================================================

queries = [
    {"id": "arch_001", "query": "What architectural sheets do we have?", "type": "orientation"},
    {"id": "arch_002", "query": "Give me an overview of the egress plan.", "type": "summary"},
    {"id": "arch_003", "query": "What's getting demolished on the demolition RCP?", "type": "specific_fact"},
    {"id": "arch_004", "query": "What are the travel distances on the egress plan?", "type": "specific_fact"},
    {"id": "arch_005", "query": "What door hardware sets are specified in the door schedule?", "type": "specific_fact"},
    {"id": "arch_006", "query": "What type of roof system is specified?", "type": "specific_fact"},
    {"id": "arch_007", "query": "What are the exterior wall materials shown on the elevations?", "type": "specific_fact"},
    {"id": "arch_008", "query": "What floor finishes are called out on A111?", "type": "specific_fact"},
    {"id": "arch_009", "query": "Tell me about the refuse enclosure - what are the details?", "type": "summary"},
    {"id": "arch_010", "query": "What's the Tormax door detail on A401?", "type": "specific_fact"},
]


# ============================================================
# RUN BENCHMARK
# ============================================================

def run_engine(engine_name, setup_fn):
    print(f"\n{'#'*70}")
    print(f"# ENGINE: {engine_name.upper()}")
    print(f"{'#'*70}")

    try:
        process_message, create_chat, tool_functions, name = setup_fn()
    except Exception as exc:
        print(f"  SETUP FAILED: {exc}")
        return []

    originals = patch_tools(tool_functions)
    results = []

    for i, q in enumerate(queries):
        print(f"\n  [{i+1}/{len(queries)}] {q['query']}")
        print(f"  {'-'*50}")

        call_log.clear()
        chat = create_chat()

        start = time.time()
        try:
            response = process_message(chat, q["query"])
        except Exception as exc:
            response = f"ENGINE ERROR: {exc}"
            print(f"  ERROR: {exc}")
        elapsed = round(time.time() - start, 2)

        # Detect if model asked a question instead of answering
        asked_question = any(phrase in response.lower() for phrase in [
            "can you tell me", "which sheet", "do you want me to",
            "could you", "can you give me", "which building",
            "did you mean", "do you know"
        ])

        result = {
            "id": q["id"],
            "engine": engine_name,
            "query": q["query"],
            "query_type": q["type"],
            "response": response,
            "response_time_s": elapsed,
            "response_length": len(response),
            "tools_called": [dict(c) for c in call_log],
            "tool_count": len(call_log),
            "tool_names": list(dict.fromkeys(c["tool"] for c in call_log)),  # unique, ordered
            "asked_question_instead": asked_question,
        }
        results.append(result)

        status = "❌ ASKED QUESTION" if asked_question else "✅"
        print(f"  {status} {elapsed}s | {len(call_log)} tools | {len(response)} chars")
        preview = response[:200].replace("\n", " ")
        print(f"  > {preview}")

        time.sleep(1)  # Rate limit buffer

    unpatch_tools(tool_functions, originals)
    return results


# ============================================================
# MAIN
# ============================================================

all_results = {}
out_dir = Path("maestro python/benchmarks/results")
out_dir.mkdir(parents=True, exist_ok=True)

# Load existing Gemini results
gemini_path = out_dir / "arch_gemini.json"
if gemini_path.exists():
    with open(gemini_path, "r", encoding="utf-8") as f:
        all_results["gemini"] = json.load(f)
    print(f"Loaded existing Gemini results: {len(all_results['gemini'])} queries")

# Run each engine
for engine_name, setup_fn in [("opus", setup_opus), ("gpt", setup_gpt)]:
    results = run_engine(engine_name, setup_fn)
    all_results[engine_name] = results

    # Save per-engine results
    with open(out_dir / f"arch_{engine_name}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_dir / f'arch_{engine_name}.json'}")


# ============================================================
# CROSS-ENGINE COMPARISON
# ============================================================

print(f"\n\n{'='*70}")
print("CROSS-ENGINE COMPARISON — Architectural Queries")
print(f"{'='*70}")

# Header
print(f"\n{'Query':<50} {'Gemini':>10} {'Opus':>10} {'GPT':>10}")
print(f"{'-'*50} {'-'*10} {'-'*10} {'-'*10}")

for q in queries:
    qid = q["id"]
    row = f"{q['query'][:48]:<50}"
    for engine_name in ["gemini", "opus", "gpt"]:
        r = next((r for r in all_results.get(engine_name, []) if r["id"] == qid), None)
        if r:
            mark = "❌" if r["asked_question_instead"] else "✅"
            row += f" {mark}{r['response_time_s']:>6.1f}s"
        else:
            row += f" {'N/A':>9}"
    print(row)

# Summary stats
print(f"\n{'SUMMARY':}")
print(f"{'-'*70}")
for engine_name in ["gemini", "opus", "gpt"]:
    results = all_results.get(engine_name, [])
    if not results:
        print(f"  {engine_name.upper()}: No results")
        continue
    avg_time = sum(r["response_time_s"] for r in results) / len(results)
    avg_tools = sum(r["tool_count"] for r in results) / len(results)
    asked = sum(1 for r in results if r["asked_question_instead"])
    answered = len(results) - asked
    total_tools = sum(r["tool_count"] for r in results)
    print(f"  {engine_name.upper():>8}: Avg {avg_time:.1f}s | {avg_tools:.1f} tools/query | {answered}/{len(results)} answered | {asked} asked back | {total_tools} total tool calls")

print(f"\nFull results in: {out_dir}")
