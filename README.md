# Noorak Search CLI

A command-line tool that lets any tool-capable AI model perform deep research by itself:
it decides what to search, fetches pages, and writes a final Markdown report via tool-calling loops.

The **NoorPDNA** (Psychological-Domain Navigation Architecture) engine controls the search narrowing process — like a 3D sphere collapsing toward a precise target.

## Overview

Noorak is a research agent CLI. You pick a research mode, enter a query, and the model
uses four built-in tools (`web_search`, `fetch_page`, `save_research`, `pdna`) to conduct
the research autonomously. The model decides when to call each tool. The **PDNA narrowing**
system ensures each iteration brings the search domain closer to the exact answer.

## NoorPDNA — Three-Dimensional Identity Manifold

PDNA controls search narrowing via three axes forming a 3D manifold:

- **Y-Axis:** Identity & Expression (-1 Suppressed → +1 Fully Expressive)
- **Z-Axis:** Sensory Processing (-1 Muted → +1 Hyperaware)
- **X-Axis:** Executive Control (-1 Chaotic → +1 Fully Controlled)

The engine uses `m` (iteration counter, decreases each step) and `n` (multiplier/paths):

- **High m, low n** = broad exploration (search widely)
- **Low m, high n** = precise targeting (narrow to specific results)
- **Sphere collapse** = each iteration brings the search domain closer to the exact answer

### PDNA narrowing in practice

```
Stage 1: Y=0.567, Z=0.567, X=0.567 → broad search (m=n down to 1)
Stage 2: Y=0.633, Z=0.633, X=0.633 → focused (m=n-1)
Stage 3: Y=0.700, Z=0.700, X=0.700 → precise (m=n-2)
Stage 4: Y=0.767, Z=0.767, X=0.767 → exact match (m=n-3)
```

## Provider compatibility

The CLI works with **any OpenAI-compatible endpoint**, **Anthropic**, or **Google Gemini**.
At first run you are asked which type of endpoint you are using, and the CLI adapts its
request format accordingly:

- **OpenAI-compatible** (`/chat/completions`) — default, works with any provider that
  follows the OpenAI API shape.
- **Anthropic** (`/v1/messages`) — adapts messages and headers for Anthropic's format.
- **Google Gemini** (`/v1beta/models/{model}:generateContent`) — uses Gemini's
  generateContent endpoint.

### Quick start

```bash
python3 noorak_search.py
# Follow the interactive prompts for endpoint type, base URL, API key, and model name.
```

### Non-interactive mode

Set environment variables to skip the prompt:

| Variable | Description |
|----------|-------------|
| `NOORAK_API_KEY` | Your API key |
| `NOORAK_BASE_URL` | Base URL of the endpoint (e.g. `https://api.example.com/v1`) |
| `NOORAK_MODEL` | Model ID to use |
| `NOORAK_API_TYPE` | `openai` (default), `anthropic`, or `gemini` |

If all three of `NOORAK_API_KEY`, `NOORAK_BASE_URL`, and `NOORAK_MODEL` are set,
the CLI skips the prompt and uses them directly.

## Research modes

Pick one of three depth modes when starting a search:

1. **Light bobble** — baseline deep research (~4 tool calls).
2. **Light caster** — two-phase plan, each phase gathers sources and writes a chunk
   (~100k tokens worth), then combined (~8 tool calls).
3. **RayCaster** — four-phase plan, each phase gathers sources and writes a deep chunk,
   then combined (~16 tool calls).

Override the tool-call budget with `NOORAK_MAX_TOOLCALLS` (integer).

## Usage

```bash
cd /path/to/Noorak-Search-CLI
python3 noorak_search.py
```

1. Select a mode (1‑3).
2. Enter your research query.
3. When research finishes, choose:
   - 1) New search
   - 2) View last report (first 30 lines)
   - 3) Exit

Reports are saved as timestamped Markdown files under `./output/`.

## Using Noorak as a plugin / extension

Noorak can be used as a **plug-in component** inside other software projects that need
built-in AI research capabilities. Import the core functions and integrate them into
your own pipeline:

```python
from noorak_search import researcher_loop, chat, exec_tool, TOOLS, noor_pdna

# Run a research task with a custom system prompt
result_path = researcher_loop(
    query="What is the latest in AI model routing?",
    system_extra="Focus on open-source solutions.",
    max_tool_calls=8
)

# PDNA narrowing stages
stages = noor_pdna.pdna_iterate(0.5, 0.5, 0.5, n=5)

# Direct PDNA computation
result = noor_pdna.pdna_base(0.5, 0.5, 0.5)  # → 0.125

# All 8 sign combinations
states = noor_pdna.pdna_changer(0.5, 0.5, 0.5)
```

Key functions available for plug-in use:

- `chat(messages, tool_choice, max_tokens)` — send a message to the configured provider.
- `exec_tool(name, args)` — execute a built-in tool by name.
- `researcher_loop(query, system_extra, max_tool_calls)` — run the full research pipeline.
- `TOOLS` — the list of available tool definitions (for passing to the model).
- `noor_pdna` — the PDNA manifold engine (`pdna_base`, `pdna_changer`, `pdna_to_integer`, `pdna_iterate`, `pdna_sphere_sample`, `pdna_summary`).

All provider configuration is read at import time from environment variables or the
interactive prompt, so your project can configure it before importing.

## Files

| File | Description |
|------|-------------|
| `noorak_search.py` | Main CLI engine |
| `noor_pdna.py` | PDNA mathematical engine |
| `deepsearch.py` | Local search tool (stdlib) |
| `README.md` | This file |
| `SECURITY.md` | Security guide |
| `requirements.txt` | Dependencies |
| `.gitignore` | Git ignore rules |

## Requirements

- Python 3.10+ (stdlib only — no pip dependencies needed for basic usage)
- Internet access (for `web_search` and `fetch_page` tools)
- A valid API key for your chosen provider/endpoint

See `requirements.txt` and `SECURITY.md` for additional details.

## Security

- API keys are **never** written to disk or committed to version control.
- Credentials stay in memory only.
- Use environment variables for CI/CD or automated workflows to avoid interactive input.
- See `SECURITY.md` for full security guidance.

## License

MIT License — see `LICENSE` file.
