# Noorak Search CLI — Tutorial

## Quick Start (2 commands)

```bash
cd Noorak-Search-CLI
NOORAK_API_KEY="your-key" NOORAK_BASE_URL="https://api.example.com/v1" NOORAK_MODEL="your-model" python3 engine/noorak_search.py
```

Or without env vars — it will prompt you interactively:
```bash
cd Noorak-Search-CLI
python3 engine/noorak_search.py
```

## Modes

When you launch, pick a research depth:

| Mode | Tool Calls | Use Case |
|------|-----------|----------|
| **1) Light bobble** | ~4 | Quick factual answers |
| **2) Light caster** | ~8 | Multi-source analysis |
| **3) RayCaster** | ~16 | Deep comprehensive research |

## Example Queries

```
قیمت تتر چنده و چه خبری باعث افزایش قیمت تتر شد؟
Latest developments in AI model routing 2026
Tether USDT price news impact analysis
What are the best open-source LLMs in 2026?
```

## What Happens Under the Hood

1. **Search**: `web_search` queries Bing/Ddg/Gh/Arxiv → cached
2. **Fetch**: `fetch_page` reads top URLs with real browser headers → cached
3. **Analyze**: Model synthesizes results into a Markdown report
4. **Save**: Report auto-saved to `output/research_YYYYMMDD-HHMMSS.md`

## Cache Behavior

- Every search result is cached for **24 hours** by default
- Re-running the same query is **instant** (no API cost)
- Cache files live in `cache/` (can be deleted anytime)
- Configure TTL: `NOORAK_CACHE_TTL=1` (1 hour) or `NOORAK_CACHE_TTL=0` (disable)

## Using as a Python Library

```python
import sys
sys.path.insert(0, "Noorak-Search-CLI/engine")
import noorak_search as ns

# Set provider from environment (NOORAK_API_KEY etc.)
result_path = ns.researcher_loop(
    query="What is the price of Tether?",
    max_tool_calls=6
)
print(f"Report saved to: {result_path}")
```

## Providers Supported

Any **OpenAI-compatible** endpoint, **Anthropic**, or **Google Gemini**:
- ArvanCloud AI (`https://api.arvancloudai.ir/v1`)
- OpenRouter (`https://openrouter.ai/api/v1`)
- Any self-hosted vLLM / Ollama / LM Studio
- OpenAI, Anthropic, Google directly

## Security

- **No API keys on disk** — only in memory
- Credentials cleared when process exits
- No `.env` files, no config files
- All network traffic via HTTPS (with optional certificate bypass)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `HTTPError 403` from fetch_page | Some sites block automated requests. Try `NOORAK_CACHE_TTL=0` to clear cache and re-fetch |
| No results from web_search | Check internet connectivity and API key |
| `Noorak` prompt never appears | Provider env vars not set correctly |
| Slow responses | Higher `max_tokens` in chat or check provider rate limits |
