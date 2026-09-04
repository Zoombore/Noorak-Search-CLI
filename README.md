# Noorak Search CLI

A command-line tool that lets **Gemma-4-31B-IT** (or any tool-capable model via FreeTheAI) perform **deep research** by itself: it decides what to search, fetches pages, and writes a final Markdown report — all via tool-calling loops.
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)

## Features

- Three research depth modes:
  - **Light bobble** – ~4 tool calls (quick baseline).
  - **Light caster** – ~8 tool calls (two-phase deeper dive).
  - **RayCaster** – ~16 tool calls (four-phase extensive study).
- Model drives the search: uses `web_search` to discover sources, `fetch_page` to read them, and finally `save_research` to write the report.
- You only nudge the model with helpful user messages when it pauses; no hard forcing of tool calls (respects model's own reasoning time).
- Provider flexibility:
  - **SelfLab / ArvanCloud** (default) – uses `Gemma-4-31B-IT`.
  - **FreeTheAI** – set `NOORAK_PROVIDER=freetheai` and optionally `NOORAK_MODEL_FTAI`.
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)
- Budget control via `NOORAK_MAX_TOOLCALLS` (overrides mode's internal tool-call limit).
- Outputs timestamped Markdown files under `./output/`.

## Setup

1. Clone this repo (or copy the files).
2. Ensure you have provider credentials:

   - For **SelfLab** (default): the CLI expects the same files as your SelfLab setup:
     ```
     /workspace/selflab/gemma4/.provider_key
     /workspace/selflab/gemma4/.provider_base
     ```
   - For **FreeTheAI**: create two files in the CLI directory:
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)
     ```
     .ftai_key    # your FreeTheAI API key (starts with sta_...)
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)
     .ftai_base   # https://api.freetheai.xyz/v1
     ```
     (They are automatically `.gitignore`d.)

3. (Optional) Python 3.8+ is required; no external packages needed (stdlib only).

## Usage

Run the CLI:

```bash
python3 noorak_search.py
```

You’ll see a menu:

```
=== Noorak Search CLI ===
 1) Light bobble - Baseline deep research (same as earlier).
 2) Light caster - First, output a concise research plan (2-3 bullet points). Then, execute the plan in two phases: each phase should gather sources and write a substantive chunk (~100k tokens worth of content). Finally, combine the two chunks into one cohesive report, explain why the chosen sources are reliable, and end with a short summary asking if the user is satisfied. Aim for a total output size around 200k tokens.
 3) RayCaster - First, output a detailed research plan with 4 clear parts. Then, execute each part as a separate phase, gathering sources and writing deep chunks. Combine all four parts into one extensive report, explain source reliability, and conclude with a summary asking if the user is satisfied. Aim for a total output size around 500k tokens.
Select mode [1-3]:
```

Pick a mode, then enter your research query.

After the search finishes, you’ll be offered to:
- Run another search
- View the last report (first few lines)
- Exit

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NOORAK_PROVIDER` | `"selflab"` (default) or `"freetheai"` | `selflab` |
| `NOORAK_MODEL_FTAI` | Model ID to use with FreeTheAI (ignored for SelfLab) | `kai/nvidia/nemotron-3-ultra-550b-a55b:free` |
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)
| `NOORAK_MAX_TOOLCALLS` | Override the mode’s tool‑call budget (integer) | mode’s internal value |
| `NOORAK_MAX_ITERS` | **Deprecated** – use `NOORAK_MAX_TOOLCALLS` instead (kept for backward compatibility) | ignored |

Example: run a Light bobble search but allow at most 6 tool calls:

```bash
NOORAK_MAX_TOOLCALLS=6 python3 noorak_search.py
```

## How It Works

1. You select a mode → each mode has a **tool‑call budget** (Light bobble: 4, Light caster: 8, RayCaster: 16).
2. The CLI calls the model with a system prompt that explains the tools and the budget.
3. The model **freely decides** when to call `web_search` or `fetch_page` (tool_choice="auto").
4. After each model response:
   - If it called tools → we execute them, increment the counter, and return the results.
   - If it gave a final answer (no tool calls):
        - If budget not exhausted → we nudge: “Continue researching, you still have X tool calls left.”
        - If budget exhausted → we ask it to finalize by calling `save_research`.
5. When the model finally calls `save_research`, we write the Markdown to `output/research_<timestamp>.md`.
6. As a last resort, if the model never calls `save_research` after the budget, we save its last text as the report (so you always get something).

## Example Output

The final Markdown includes:
- Executive Summary
- Answers to your specific sub‑questions (if any)
- Architecture diagrams (Mermaid) when relevant
- Implementation roadmap
- Technology decision matrix
- Risks & mitigations
- Recommended next steps
- Appendix: Sources (all URLs the model actually fetched)

## Notes

- The first search can take a while because the model performs several rounds of reasoning and tool use. Subsequent searches on similar topics may be faster if the model reuses knowledge.
- If the provider (ArvanCloud or FreeTheAI) is slow or rate‑limited, the CLI will appear to hang; it is waiting for the HTTP response. Adjust your timeout or try again later.
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)
- All API keys stay **only in memory**; they are never written to logs.

## Troubleshooting

- **Provider credentials missing** → double‑check the paths `.provider_key`/`.provider_base` (SelfLab) or `.ftai_key`/`.ftai_base` (FreeTheAI).
            (default model: kai/openrouter/free, override via NOORAK_MODEL_FTAI)
- **Model refuses to call tools** → increase the budget via `NOORAK_MAX_TOOLCALLS` or check that the model listed actually supports tool‑calling (we verified `kai/nvidia/nemotron-3-ultra-550b-a55b:free` works).
- **No output file** → in the extremely unlikely case the model returns nothing, the CLI will still attempt to save its last utterance.

## License

MIT – feel free to fork and adapt.

