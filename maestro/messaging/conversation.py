# conversation.py — Maestro's single continuous conversation
#
# One Maestro. One super. One thread. Forever.
#
# REWIRED: Messages stored in DB (one row per message) instead of
# conversation.json. Summary + metadata in conversation_state table.
# Compaction deletes old message rows and updates the summary.
#
# On startup: loads summary + recent messages from DB.
# After every exchange: persists to DB.
# At 65% context usage: compacts.

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import PROVIDERS, DEFAULT, COMPACTION_THRESHOLD, KEEP_RECENT, CHARS_PER_TOKEN
from knowledge.loader import load_project
from identity.prompt import build_system_prompt
from tools.registry import build_tool_registry
from maestro.db import repository as repo
from maestro.db.session import init_db


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token count from character length."""
    return len(text) // CHARS_PER_TOKEN


def _estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += _estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += _estimate_tokens(json.dumps(block))
                else:
                    total += _estimate_tokens(str(block))
        else:
            total += _estimate_tokens(str(content))
    return total


# ---------------------------------------------------------------------------
# Compaction helpers
# ---------------------------------------------------------------------------

def _needs_compaction(
    system_tokens: int,
    summary_tokens: int,
    message_tokens: int,
    context_limit: int,
) -> bool:
    total = system_tokens + summary_tokens + message_tokens
    usage_pct = total / context_limit if context_limit > 0 else 1.0
    return usage_pct >= COMPACTION_THRESHOLD


def _messages_to_text(messages: list[dict[str, Any]]) -> str:
    """Convert message list to readable text for summarization."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        texts.append(f"[Tool: {block.get('name', '?')}]")
                    elif block.get("type") == "tool_result":
                        texts.append(f"[Tool result: {str(block.get('content', ''))[:200]}]")
            text = " ".join(texts)
        else:
            text = str(content)

        if text.strip():
            label = "Super" if role == "user" else "Maestro"
            lines.append(f"{label}: {text[:500]}")

    return "\n".join(lines)


def _build_compaction_prompt(existing_summary: str, old_text: str) -> str:
    parts = [
        "You are summarizing a conversation between Maestro (an AI construction plan analyst) "
        "and a superintendent. Produce a concise summary that preserves:",
        "- Key decisions made",
        "- Open questions and RFIs",
        "- Important findings (coordination gaps, conflicts, missing info)",
        "- Schedule items discussed (dates, deadlines, pour dates)",
        "- Any commitments or action items",
        "- The super's preferences and communication style",
        "",
        "Be factual and specific. Include dates, sheet numbers, and detail references.",
        "Do NOT include pleasantries, greetings, or filler.",
    ]

    if existing_summary:
        parts.append(f"\n--- EXISTING SUMMARY ---\n{existing_summary}")

    parts.append(f"\n--- NEW CONVERSATION TO INCORPORATE ---\n{old_text}")
    parts.append("\n--- UPDATED SUMMARY ---")

    return "\n".join(parts)


def _summarize_with_gemini_flash(prompt: str) -> str:
    import google.generativeai as genai
    import os
    from dotenv import load_dotenv

    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text.strip()


def _fallback_summary(existing_summary: str, old_text: str) -> str:
    truncated = old_text[:2000] + "\n[...truncated...]" if len(old_text) > 2000 else old_text
    if existing_summary:
        return f"{existing_summary}\n\n[Additional context]\n{truncated}"
    return truncated


# ---------------------------------------------------------------------------
# Conversation class — DB-backed
# ---------------------------------------------------------------------------

class Conversation:
    """Maestro's single continuous conversation.

    One thread. One brain. Persists to DB. Compacts when needed.
    """

    def __init__(self, engine_name: str | None = None, project_id: str | None = None):
        self.engine_name = engine_name or DEFAULT
        provider_config = PROVIDERS[self.engine_name]
        self.provider_name = provider_config["provider"]
        self.model = provider_config["model"]
        self.context_limit = provider_config.get("context_limit", 200_000)

        # Ensure DB tables exist
        init_db()

        # Load project + get/create DB project
        self.project = load_project()
        project_name = self.project.get("name", "default") if self.project else "default"

        if project_id:
            self.project_id = project_id
        else:
            p = repo.get_or_create_project(project_name)
            self.project_id = p["id"]

        # Initialize tools + system prompt (registry handles init of workspaces + schedule)
        self.tool_definitions, self.tool_functions = build_tool_registry(self.project, project_id=self.project_id)
        self.system_prompt = build_system_prompt()

        # Estimate fixed token costs
        tools_text = json.dumps(self.tool_definitions)
        self._fixed_tokens = _estimate_tokens(self.system_prompt) + _estimate_tokens(tools_text)

        # Per-provider setup
        self._client = None
        self._tools = None
        self._chat = None
        self._init_provider()

        # Ensure conversation state exists in DB
        repo.get_or_create_conversation(self.project_id)

        # Register the brain-switch tool
        self.tool_functions["switch_engine"] = lambda engine: self.switch_engine(engine)
        self.tool_definitions.append({
            "name": "switch_engine",
            "description": (
                "Switch Maestro's AI engine mid-conversation. Use when the super asks to "
                "change models, or when a task would benefit from a different engine. "
                "Options: opus (Claude Opus 4.6 — deepest analysis, most expensive), "
                "gpt (GPT-5.2 — strong all-around), "
                "gemini (Gemini 3 Pro — fast and capable), "
                "gemini-flash (Gemini 3 Flash — fastest and cheapest, great for quick questions)."
            ),
            "params": {
                "engine": {
                    "type": "string",
                    "description": "Engine name: opus, gpt, gemini, or gemini-flash",
                    "required": True,
                },
            },
        })

        self._rebuild_tool_schemas()

    def _init_provider(self):
        if self.provider_name == "anthropic":
            from engine.providers.anthropic import create_client, build_tool_schemas
            self._client = create_client()
            self._tools = build_tool_schemas(self.tool_definitions)
        elif self.provider_name == "google":
            from engine.providers.google import create_client, build_tool_schemas, create_chat
            create_client()
            self._tools = build_tool_schemas(self.tool_definitions)
            self._chat = create_chat(self.model, self.system_prompt, self._tools)
        elif self.provider_name == "openai":
            from engine.providers.openai import create_client, build_tool_schemas
            self._client = create_client()
            self._tools = build_tool_schemas(self.tool_definitions)

    def _rebuild_tool_schemas(self):
        if self.provider_name == "anthropic":
            from engine.providers.anthropic import build_tool_schemas
            self._tools = build_tool_schemas(self.tool_definitions)
        elif self.provider_name == "google":
            from engine.providers.google import build_tool_schemas, create_chat
            self._tools = build_tool_schemas(self.tool_definitions)
            self._chat = create_chat(self.model, self.system_prompt, self._tools)
        elif self.provider_name == "openai":
            from engine.providers.openai import build_tool_schemas
            self._tools = build_tool_schemas(self.tool_definitions)

    def _get_summary(self) -> str:
        """Get the conversation summary from DB."""
        state = repo.get_or_create_conversation(self.project_id)
        return state.get("summary", "")

    def _get_messages(self) -> list[dict[str, Any]]:
        """Get all messages from DB as the format the providers expect."""
        rows = repo.get_messages(self.project_id)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def _build_messages_for_api(self) -> list[dict[str, Any]]:
        """Build the message list for the API call.

        If there's a summary, inject it as the first user/assistant exchange.
        """
        messages = []

        summary = self._get_summary()
        if summary:
            messages.append({
                "role": "user",
                "content": "[Conversation history summary — this is context from our previous exchanges]",
            })
            messages.append({
                "role": "assistant",
                "content": f"I remember. Here's what we've covered:\n\n{summary}",
            })

        messages.extend(self._get_messages())
        return messages

    def send(self, message: str) -> str:
        """Send a message and get Maestro's response.

        This is the single entry point. Everything goes through here.
        """
        # Add user message to DB
        repo.add_message(self.project_id, "user", message)

        # Check compaction
        self._maybe_compact()

        # Build full message list
        api_messages = self._build_messages_for_api()

        # Send through provider
        if self.provider_name == "anthropic":
            answer = self._send_anthropic(api_messages)
        elif self.provider_name == "google":
            answer = self._send_google(message)
        elif self.provider_name == "openai":
            answer = self._send_openai(api_messages)
        else:
            answer = "Engine not configured."

        # Add assistant response to DB
        repo.add_message(self.project_id, "assistant", answer)

        # Increment exchange count
        repo.update_conversation_state(self.project_id, increment_exchanges=True)

        return answer

    def _send_anthropic(self, messages: list[dict[str, Any]]) -> str:
        from engine.providers.anthropic import send_message
        messages, answer = send_message(
            self._client, self.model, self.system_prompt,
            messages, self._tools, self.tool_functions,
        )
        return answer

    def _send_google(self, message: str) -> str:
        from engine.providers.google import send_message
        return send_message(
            self._chat, self.model, self.system_prompt,
            message, self._tools, self.tool_functions,
        )

    def _send_openai(self, messages: list[dict[str, Any]]) -> str:
        from engine.providers.openai import send_message
        messages, answer = send_message(
            self._client, self.model, self.system_prompt,
            messages, self._tools, self.tool_functions,
        )
        return answer

    def _maybe_compact(self) -> None:
        """Check context usage and compact if needed."""
        summary = self._get_summary()
        messages = self._get_messages()

        summary_tokens = _estimate_tokens(summary)
        message_tokens = _estimate_messages_tokens(messages)

        if not _needs_compaction(
            self._fixed_tokens, summary_tokens, message_tokens, self.context_limit
        ):
            return

        total = self._fixed_tokens + summary_tokens + message_tokens
        print(f"\n[Compaction] Triggering — estimated {total} tokens "
              f"({total / self.context_limit:.0%} of {self.context_limit})")

        if len(messages) <= KEEP_RECENT:
            return  # Nothing to compact

        # Split: old to summarize, recent to keep
        old_messages = messages[:-KEEP_RECENT]
        # We need the DB message IDs to know what to delete
        all_rows = repo.get_messages(self.project_id)
        if len(all_rows) <= KEEP_RECENT:
            return

        cutoff_id = all_rows[-KEEP_RECENT]["id"]  # Keep messages with id >= this

        # Summarize old messages
        old_text = _messages_to_text(old_messages)
        prompt = _build_compaction_prompt(summary, old_text)

        try:
            new_summary = _summarize_with_gemini_flash(prompt)
        except Exception as exc:
            print(f"[Compaction] Gemini Flash failed ({exc}), using fallback")
            new_summary = _fallback_summary(summary, old_text)

        # Delete old messages from DB
        deleted = repo.delete_messages_before(self.project_id, cutoff_id)

        # Update summary + compaction count
        repo.update_conversation_state(
            self.project_id,
            summary=new_summary,
            increment_compactions=True,
        )

        remaining_tokens = _estimate_tokens(new_summary) + _estimate_messages_tokens(
            [{"content": m["content"]} for m in all_rows[-KEEP_RECENT:]]
        )
        print(f"[Compaction] Done — deleted {deleted} messages, "
              f"{remaining_tokens + self._fixed_tokens} tokens "
              f"({(remaining_tokens + self._fixed_tokens) / self.context_limit:.0%} of {self.context_limit})")

    def switch_engine(self, engine_name: str) -> str:
        """Switch Maestro's brain mid-conversation. History preserved in DB."""
        if engine_name not in PROVIDERS:
            available = ", ".join(PROVIDERS.keys())
            return f"Unknown engine '{engine_name}'. Available: {available}"

        if engine_name == self.engine_name:
            return f"Already running on {engine_name}."

        old_engine = self.engine_name
        self.engine_name = engine_name
        provider_config = PROVIDERS[engine_name]
        self.provider_name = provider_config["provider"]
        self.model = provider_config["model"]
        self.context_limit = provider_config.get("context_limit", 200_000)

        self._init_provider()

        tools_text = json.dumps(self.tool_definitions)
        self._fixed_tokens = _estimate_tokens(self.system_prompt) + _estimate_tokens(tools_text)

        self._maybe_compact()

        return f"Switched from {old_engine} to {engine_name} ({provider_config['display']}). Conversation preserved."

    def get_stats(self) -> dict[str, Any]:
        """Get conversation statistics."""
        summary = self._get_summary()
        messages = self._get_messages()

        summary_tokens = _estimate_tokens(summary)
        message_tokens = _estimate_messages_tokens(messages)
        total_tokens = self._fixed_tokens + summary_tokens + message_tokens

        state = repo.get_or_create_conversation(self.project_id)

        return {
            "engine": self.engine_name,
            "context_limit": self.context_limit,
            "estimated_tokens": total_tokens,
            "usage_pct": f"{total_tokens / self.context_limit:.1%}",
            "messages_in_memory": len(messages),
            "total_exchanges": state.get("total_exchanges", 0),
            "compactions": state.get("compactions", 0),
            "has_summary": bool(summary),
            "summary_length": len(summary),
        }
