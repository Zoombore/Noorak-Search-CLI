# How Noorak Works — Architecture & Flow

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                    USER (CLI / API)                  │
└──────────────────────┬──────────────────────────────┘
                       │ query
                       ▼
┌─────────────────────────────────────────────────────┐
│              ENGINE (engine/noorak_search.py)         │
│  ┌──────────────┐  ┌───────────┐  ┌───────────────┐ │
│  │   CHAT       │  │   CACHE   │  │  EvidenceLog  │ │
│  │  (provider)  │◄─┤ (TTL)     │  │  (collects)   │ │
│  └──────┬───────┘  └───────────┘  └──────┬────────┘ │
│         │                               │          │
│         ▼                               ▼          │
│  ┌───────────────┐  ┌────────────────────────────┐ │
│  │  lfe/deep     │  │  SAVE GUARANTEED LADDER:   │ │
│  │  _search.py   │  │  1) model saves naturally  │ │
│  │  (Bing,Ddg)   │  │  2) forced tool_choice     │ │
│  └───────┬───────┘  │  3) auto-save fallback     │ │
│          │          └──────────┬─────────────────┘ │
│          │                     │                   │
│          ▼                     ▼                   │
│  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ lfe/deep     │  │  OUTPUT/                 │   │
│  │ _search.py   │  │  research_*.md           │   │
│  │ (fetch_page) │  │  (final reports)         │   │
│  └──────────────┘  └──────────────────────────┘   │
│          │                                        │
│          ▼                                        │
│  ┌──────────────┐                                │
│  │ storage/corp │                                │
│  │ us/          │                                │
│  └──────────────┘                                │
└─────────────────────────────────────────────────────┘
```

## Step-by-Step Flow

1. **User enters query** → `researcher_loop(query, ...)` in `engine/`
2. **System prompt sent** to provider with tool definitions
3. **Model calls web_search** → `engine/exec_tool('web_search', args)`
   - Cache key generated: `sha256("web_search|query|engines|top")`
   - If cached and fresh → return immediately (0 tokens, <1ms)
   - Else → `lfe/deepsearch.py` fetches via Bing/Ddg/Gh/Arxiv
   - Result cached to `cache/` before returning
4. **Model calls fetch_page** → `engine/exec_tool('fetch_page', {url})`
   - Cache key: `sha256("fetch_page|url")`
   - If cached → return immediately
   - Else → `direct_fetch_page(url)` with real browser UA
   - Result written to `storage/corpus/` and cached
5. **Model iterates** until budget exhausted or `save_research` called
6. **Save Guaranteed** via 3-step ladder:
   - ✅ Normal: model calls `save_research`
   - ✅ Budget: forced `tool_choice={"name":"save_research"}`
   - ✅ Auto-save: `EvidenceLog.render_markdown()` written to `output/`
7. **User sees** path to saved Markdown report

## Cache System

- **Location:** `cache/` at repo root
- **Format:** JSON files named `{kind}_{sha256hash}.json`
- **Content:** `{"ts": <unix_time>, "key": "<query>", "value": <result>}`
- **TTL:** Configurable via `NOORAK_CACHE_TTL` env var (default: 24 hours)
- **Disabled:** Set `NOORAK_CACHE_TTL=0` to bypass cache entirely
- **Scope:** Only affects web_search and fetch_page calls within the same Noorak installation

## Save Guarantee

`researcher_loop()` **NEVER** returns `None` for a valid run:

```python
# Ladder 1: normal path
res = exec_tool('save_research', {markdown})
if res.startswith('SAVED:'):
    return res.split(':',1)[1]  # path to file

# Ladder 2: budget forced
msg = chat(messages, tool_choice={"name":"save_research"}, max_tokens=6000)
# process tool_calls, save

# Ladder 3: auto-save from evidence log
return auto_save_report(query, evidence_log)
```

## Dynamic Paths

All file paths are computed relative to `Path(__file__)`. Nothing is hardcoded:

```python
ENGINE_DIR = Path(__file__).resolve().parent      # .../engine
ROOT_DIR = ENGINE_DIR.parent                        # repo root
CACHE_DIR = ROOT_DIR / "cache"
STORAGE_DIR = ROOT_DIR / "storage"
OUTPUT_DIR = ROOT_DIR / "output"
```

Install anywhere, run anywhere. No absolute paths needed.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NOORAK_API_KEY` | — | Provider API key (never on disk) |
| `NOORAK_BASE_URL` | — | Provider endpoint URL |
| `NOORAK_MODEL` | — | Model identifier |
| `NOORAK_API_TYPE` | `openai` | `openai`, `anthropic`, or `gemini` |
| `NOORAK_CACHE_TTL` | `24` | Cache TTL in hours (0 to disable) |
| `NOORAK_MAX_TOOLCALLS` | `999` | Max tool calls per query |
