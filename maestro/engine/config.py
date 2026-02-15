# config.py — Model provider configuration
#
# Maps engine names to their provider module, model identifier,
# and context window size. Add new models here.

PROVIDERS = {
    "opus": {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "display": "Opus 4.6",
        "context_limit": 1_000_000,
    },
    "gemini": {
        "provider": "google",
        "model": "gemini-3-pro-preview",
        "display": "Gemini 3 Pro",
        "context_limit": 1_000_000,
    },
    "gemini-flash": {
        "provider": "google",
        "model": "gemini-3-flash-preview",
        "display": "Gemini 3 Flash",
        "context_limit": 1_000_000,
    },
    "gpt": {
        "provider": "openai",
        "model": "gpt-5.2",
        "display": "GPT-5.2",
        "context_limit": 128_000,
    },
}

DEFAULT = "gpt"

# Compaction settings
COMPACTION_THRESHOLD = 0.65   # Compact at 65% of context window
KEEP_RECENT = 20              # Messages to keep in full after compaction
CHARS_PER_TOKEN = 4           # Rough estimate for token counting
