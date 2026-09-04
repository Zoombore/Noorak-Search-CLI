# Noorak Search CLI — Architecture

## Directory Structure

```
Noorak-Search-CLI/          # Repository root
├── engine/                 # Orchestrator layer
│   ├── __init__.py
│   └── noorak_search.py    # Main orchestrator: chat, cache, EvidenceLog, save ladder
├── lfe/                    # Light Finder Engine (computation)
│   ├── __init__.py
│   ├── deepsearch.py       # Web search engines (Bing, Ddg, Gh, Arxiv) + fetch
│   ├── noor_pdna.py        # PDNA manifold math engine
│   └── test_noor_pdna.py   # Unit tests for PDNA
├── cache/                  # TTL cache (JSON files, auto-generated)
├── storage/                # Raw data storage
│   └── corpus/             # Downloaded pages, organized by source
├── output/                 # Final Markdown reports (auto-saved)
├── docs/                   # Documentation (this directory)
├── tests/                  # Test scripts and legacy tests
├── .gitignore
├── README.md
├── SECURITY.md
├── LICENSE
└── requirements.txt        # Python 3.10+ stdlib only
```

## Component Responsibilities

### `engine/noorak_search.py` — Orchestrator

**Purpose:** Coordinate the research loop, manage the provider connection, guarantee save.

**Key classes/functions:**
- `EvidenceLog` — Collects every tool result for fallback reports
- `researcher_loop(query, ...)` — Main research loop with 3-step save guarantee
- `exec_tool(name, args)` — Dispatches to lfe/ or handles tool-specific logic
- `chat(messages, ...)` — Sends messages to configured provider
- `cache_get` / `cache_set` — TTL-based cache management

**Import path:** `sys.path.insert(0, "engine"); import noorak_search`

### `lfe/deepsearch.py` — Search & Fetch Engine

**Purpose:** Low-level internet access — search engines and page fetching.

**Components:**
- `eng_ddg(q)` — DuckDuckGo HTML endpoint search
- `eng_bing(q)` — Bing RSS feed search
- `eng_gh(q)` — GitHub repository search
- `eng_arxiv(q)` — arXiv API paper search
- `http_get(url)` — HTTP GET with realistic browser headers
- `html_to_text(raw)` — HTML → clean text extraction
- `direct_fetch_page(url)` — Fetch a URL with real browser headers (used by engine/)

**Import path:** `sys.path.insert(0, "lfe"); import deepsearch`

### `lfe/noor_pdna.py` — PDNA Manifold Engine

**Purpose:** Mathematical identity manifold for search narrowing (3D sphere).

**Functions:**
- `pdna_base(y, z, x)` → Y*Z*X (continuous [-1,+1])
- `pdna_changer(y, z, x)` → 8 sign combinations
- `pdna_to_integer(y, z, x, m, n)` → integer domain mapping
- `pdna_iterate(y, z, x, n)` → full iteration from m=n to 1
- `pdna_sphere_sample(resolution)` → 3D sphere surface points
- `pdna_summary(states)` → statistical summary

**Import path:** `sys.path.insert(0, "lfe"); import noor_pdna`

## Data Flow

```
User Query
    │
    ▼
engine/researcher_loop()
    │
    ├──► chat() ──► Provider API ──► Tool calls (web_search / fetch_page)
    │         │
    │         ▼
    │    exec_tool('web_search', ...) ──► cache_get/check ──► lfe/deepsearch.py
    │                                                    │
    │                                                    ▼
    │                                          cache_set / EvidenceLog
    │
    ├──► [loop continues until budget or save_research]
    │
    └──► SAVE LADDER ──► output/research_*.md
```

## Cache Architecture

```
Key: sha256("web_search|query|engines|top")  →  cache/search_{hash}.json
Key: sha256("fetch_page|url")                →  cache/page_{hash}.json

Format: {"ts": <float>, "key": "<original>", "value": <result_string>}
TTL: NOORAK_CACHE_TTL hours (default 24)
```

## Save Guarantee (3-Step Fallback)

```
┌────────────────────────────────────────────────────┐
│ Step 1: Normal Path                                │
│   model calls save_research(markdown)              │
│   → writes output/research_*.md                    │
│   → returns path                                   │
├────────────────────────────────────────────────────┤
│ Step 2: Budget Forcing                             │
│   loop detects max_tool_calls reached              │
│   → chat(tool_choice={"name":"save_research"})     │
│   → model forced to call save_research             │
│   → if model refuses: last_text written directly   │
├────────────────────────────────────────────────────┤
│ Step 3: Auto-Save (EvidenceLog)                    │
│   if all else fails                                │
│   → EvidenceLog.render_markdown(query)             │
│   → writes output/research_*_auto.md               │
│   → ALWAYS returns a file path                     │
└────────────────────────────────────────────────────┘
```

## Provider Compatibility

**OpenAI-compatible** (most providers):
- ArvanCloud AI, OpenRouter, OpenAI, DeepSeek, Groq, Together AI
- Any vLLM, Ollama, LM Studio server
- Format: `POST /chat/completions` with `tools` array

**Anthropic:**
- `POST /v1/messages` with `x-api-key` header
- Content blocks format

**Google Gemini:**
- `POST /v1beta/models/{model}:generateContent`
- API key as query parameter

## Testing

```bash
# PDNA unit tests
cd Noorak-Search-CLI
python3 lfe/test_noor_pdna.py

# Full E2E test (requires API key)
export NOORAK_API_KEY="..." NOORAK_BASE_URL="..." NOORAK_MODEL="..."
python3 engine/noorak_search.py
```
