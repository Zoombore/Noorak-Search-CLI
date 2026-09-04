# Using Noorak as a Plugin / Extension

Noorak can be integrated as a **built-in AI research component** inside other
software projects. Any application that needs AI-driven research capabilities
can embed Noorak.

## Quick integration

```python
from noorak_search import (
    researcher_loop,   # Full research pipeline
    chat,              # Direct chat with the configured provider
    exec_tool,         # Execute a built-in tool
    TOOLS              # Available tool definitions (for passing to the model)
)

# Set environment variables before importing (recommended):
# export NOORAK_API_KEY="..."
# export NOORAK_BASE_URL="https://api.example.com/v1"
# export NOORAK_MODEL="your-model"
# export NOORAK_API_TYPE="openai"  # or "anthropic" or "gemini"

# Run a research task
report_path = researcher_loop(
    query="What are the latest advances in AI model routing?",
    system_extra="Focus on open-source solutions.",
    max_tool_calls=8
)
print(f"Report saved to: {report_path}")
```

## Available functions

| Function | Description |
|----------|-------------|
| `chat(messages, tool_choice, max_tokens)` | Send a message to the configured provider endpoint. Returns the model's response (text + tool_calls if any). |
| `exec_tool(name, args)` | Execute a built-in tool by name (`web_search`, `fetch_page`, `save_research`). Returns the tool's output. |
| `researcher_loop(query, system_extra, max_tool_calls)` | Run the full autonomous research pipeline. Returns the path to the saved Markdown report. |
| `TOOLS` | List of tool definitions (OpenAI function schema) — pass to `chat()` to enable tool use. |

## Configuration before importing

Set one of the following before importing `noorak_search`:

- **Environment variables** (recommended):
  - `NOORAK_API_KEY` — your API key
  - `NOORAK_BASE_URL` — base URL of the endpoint
  - `NOORAK_MODEL` — model ID
  - `NOORAK_API_TYPE` — `openai` (default), `anthropic`, or `gemini`
- **Interactive prompt** — if env vars are not set, the CLI will prompt on first import.

## Supported provider types

Noorak supports three endpoint types:

1. **OpenAI-compatible** — any endpoint following the `/chat/completions` pattern.
2. **Anthropic** — uses `/v1/messages` with `x-api-key` header.
3. **Google Gemini** — uses `/v1beta/models/{model}:generateContent`.

## Use cases

- **AI-powered assistants** — embed research into your chatbot or agent.
- **Automated reporting tools** — generate research reports on demand.
- **Browser extensions** — add research capabilities to a browser tool.
- **IDE plugins** — let developers research directly from their editor.
- **Mobile/web apps** — backend research engine for any application.

## Minimal dependency

Noorak requires **only Python 3.10+ and stdlib** (json, os, ssl, subprocess,
sys, time, urllib). No pip packages are needed for the core functionality.
See `requirements.txt` for optional extras.

## Security

See `SECURITY.md` for security practices.

## License

MIT License — see `LICENSE` file.
