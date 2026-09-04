#!/usr/bin/env python3
"""
Token Optimizer — Reduce context usage per chat turn.

The biggest token waster: sending full TOOLS schema on EVERY turn.
This module compresses tool definitions and manages context trimming.

Savings estimate:
  - Full TOOLS schema: ~1500-2000 tokens per turn × 16 turns = 32K tokens
  - Compressed tools: ~300-400 tokens per turn × 16 turns = 6.4K tokens
  - Total savings: ~25K tokens per research session
"""
import json
from pathlib import Path

# ---------- Compressed tool definitions (for later turns) ----------
# These are minimal schemas sent AFTER the first round to save tokens.
COMPRESSED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search internet (engines: ddg,bing,gh,arxiv). Returns ranked results.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
                "engines": {"type": "string"},
                "top": {"type": "integer"}
            }, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Fetch a URL and return cleaned text.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}
            }, "required": ["url"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_research",
            "description": "Write final research report Markdown to disk.",
            "parameters": {"type": "object", "properties": {
                "markdown": {"type": "string"}
            }, "required": ["markdown"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pdna",
            "description": "NoorPDNA manifold computation.",
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "enum": ["base","changer","iterate","sphere","summary"]}
            }, "required": ["action"]}
        }
    }
]

# ---------- Full tool definitions (first turn only) ----------
def get_full_tools() -> list:
    """Full tool schemas with descriptions. Send ONLY on the first turn."""
    return _load_tools()

def get_compressed_tools() -> list:
    """Compressed tool schemas. Send on subsequent turns to save tokens."""
    return COMPRESSED_TOOLS

def _load_tools() -> list:
    """Load TOOLS from engine/noorak_search.py without importing (avoid prompt trigger)."""
    # Import the actual TOOLS from the engine module
    import sys
    engine_path = Path(__file__).resolve().parent
    sys.path.insert(0, str(engine_path))
    import noorak_search as ns
    return ns.TOOLS

# ---------- Context trimming ----------
def trim_messages(messages: list, keep_system: bool = True, max_chars: int = 4000) -> list:
    """
    Trim old messages to save context tokens.
    Keeps: system prompt, most recent assistant+tool rounds.
    Removes: old user messages that are just confirmations.

    Strategy:
    1. Always keep system prompt
    2. Keep the most recent 3 assistant+tool pairs
    3. For older rounds, keep only the last user message (query confirmation)
    """
    if not messages:
        return messages

    system_msg = None
    user_msg = None
    assistant_pairs = []

    for m in messages:
        role = m.get("role", "")
        if role == "system" and keep_system:
            system_msg = m
        elif role == "user" and user_msg is None:
            user_msg = m  # Keep the original query
        elif role == "assistant":
            assistant_pairs.append(m)

    # Rebuild: system + user query + last 3 assistant pairs
    trimmed = []
    if system_msg:
        trimmed.append(system_msg)
    if user_msg:
        trimmed.append(user_msg)

    # Keep last 3 assistant rounds (with their tool calls and results)
    recent_pairs = assistant_pairs[-3:]
    for pair in recent_pairs:
        trimmed.append(pair)

    # Estimate total characters
    total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in trimmed)
    if total_chars > max_chars and len(assistant_pairs) > 3:
        # Trim more aggressively: keep only last 2
        trimmed = []
        if system_msg:
            trimmed.append(system_msg)
        if user_msg:
            trimmed.append(user_msg)
        for pair in assistant_pairs[-2:]:
            trimmed.append(pair)

    return trimmed

# ---------- Tool schema byte-size estimator ----------
def estimate_tokens(msg: dict) -> int:
    """Rough token estimate for a message dict (1 token ≈ 4 chars for English)."""
    text = json.dumps(msg, ensure_ascii=False)
    return len(text) // 4

def estimate_total_tokens(messages: list) -> int:
    """Estimate total tokens for a message list."""
    return sum(estimate_tokens(m) for m in messages)

# ---------- Usage example ----------
if __name__ == "__main__":
    import noorak_search as ns
    full = get_full_tools()
    compressed = get_compressed_tools()

    print(f"Full tools schema: {len(json.dumps(full, ensure_ascii=False))} chars ≈ {len(json.dumps(full, ensure_ascii=False))//4} tokens")
    print(f"Compressed tools:  {len(json.dumps(compressed, ensure_ascii=False))} chars ≈ {len(json.dumps(compressed, ensure_ascii=False))//4} tokens")
    print(f"Savings per turn (after first): {len(json.dumps(full, ensure_ascii=False))//4 - len(json.dumps(compressed, ensure_ascii=False))//4} tokens")
    print(f"\nWith 16 turns: ~{(len(json.dumps(full, ensure_ascii=False))//4 - len(json.dumps(compressed, ensure_ascii=False))//4) * 15} tokens saved total")
