# sendblue.py — Sendblue iMessage API wrapper
#
# Send and receive iMessages via Sendblue.
# Docs: https://docs.sendblue.co

from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.sendblue.co/api"
API_KEY_ID = os.getenv("SENDBLUE_API_KEY_ID")
API_SECRET_KEY = os.getenv("SENDBLUE_API_SECRET_KEY")
FROM_NUMBER = os.getenv("SENDBLUE_FROM_NUMBER")

HEADERS = {
    "Content-Type": "application/json",
    "sb-api-key-id": API_KEY_ID,
    "sb-api-secret-key": API_SECRET_KEY,
}


def send_typing_indicator(to_number: str) -> dict:
    """Send a typing indicator (the "..." bubble) to a recipient.

    Args:
        to_number: Recipient phone number (E.164 format)

    Returns:
        Sendblue API response dict
    """
    payload = {
        "number": to_number,
        "from_number": FROM_NUMBER,
    }
    try:
        resp = requests.post(f"{API_BASE}/send-typing-indicator", json=payload, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}  # Non-critical — don't break the flow if this fails


def send_message(to_number: str, content: str, media_url: str | None = None) -> dict:
    """Send an iMessage via Sendblue.

    Args:
        to_number: Recipient phone number (E.164 format, e.g. +16823521836)
        content: Message text
        media_url: Optional URL to an image/file to attach

    Returns:
        Sendblue API response dict
    """
    payload = {
        "number": to_number,
        "from_number": FROM_NUMBER,
        "content": content,
    }
    if media_url:
        payload["media_url"] = media_url

    resp = requests.post(f"{API_BASE}/send-message", json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_for_imessage(text: str) -> str:
    """Clean up engine output for iMessage.

    iMessage doesn't support markdown, so we strip or convert formatting:
    - **bold** → CAPS or just plain
    - Headers → plain text with emphasis
    - Code blocks → plain text
    - Keep it conversational — this is a text message, not a report
    """
    import re

    # Strip markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Convert **bold** to plain (iMessage doesn't render it)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)

    # Convert *italic* to plain
    text = re.sub(r'\*(.+?)\*', r'\1', text)

    # Strip code block markers
    text = re.sub(r'```\w*\n?', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)

    # Collapse excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
