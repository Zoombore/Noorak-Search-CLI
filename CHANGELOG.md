# Changelog

All notable changes to Noorak Search CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-09-04

### Added
- **Token Optimizer** (`engine/token_optimizer.py`):
  - Compressed tool schemas (saves ~1500 tokens per turn after first)
  - Context trimming for long conversations
  - Token estimation utilities
- **Injection Guard** (`engine/injection_guard.py`):
  - 20+ injection pattern regex (ignore, forget, jailbreak, DAN, role confusion)
  - Pre-processing sanitization
  - Post-processing model response scanning
  - Audit logging to `output/injection_audit.jsonl`
- **Local Search** (`engine/local_search.py`):
  - File indexer with word map (fast keyword search)
  - Relevance ranking (TF-IDF-like scoring)
  - Structure analyzer with opinion on file organization
  - Reference finder across project
  - 3 new tools: `local_search`, `analyze_structure`, `find_references`
- 3 new TOOLS in `engine/noorak_search.py`: `local_search`, `analyze_structure`, `find_references`

### Changed
- `engine/noorak_search.py` — Added local search tools, injection guard integration
- `README.md` — Updated with new engine files and capabilities
- `CONTRIBUTING.md` — Added local search contribution guide section

## [2.0.0] - 2026-09-04

### Added
- **Layered project layout**: `engine/`, `lfe/`, `storage/`, `cache/`, `docs/`
- **Cache system with TTL**: SHA-256 hashed cache for `web_search` and `fetch_page`
  - Configurable TTL via `NOORAK_CACHE_TTL` env var (default 24h)
  - Identical queries cost **0 tokens**, run in **<1ms**
  - Benchmark: 0.001s cached vs 8.8s first run (8800x faster)
- **Save Guarantee (3-step ladder)**:
  1. Model calls `save_research` naturally
  2. Budget reached → forced `tool_choice={"name":"save_research"}`
  3. **Auto-save** from `EvidenceLog` — **NEVER returns None**
- **EvidenceLog class** — collects all tool results for fallback reports
- **Direct `fetch_page`** with real browser User-Agent headers
  - Now returns **15,000+ chars** of real content (was 55 chars)
- **Dynamic paths** — all file paths computed relative to `__file__`, nothing hardcoded
- **`__main__.py`** — enables `python3 -m noorak` usage
- **`setup.py` + `pyproject.toml`** — pip installable (`pip install .` then `noorak`)
- **`Dockerfile`** — container image for deployment
- **`.github/workflows/ci.yml`** — GitHub Actions CI (test, lint, docker)
- **`tests/test_engine.py`** — pytest-compatible unit tests for engine core
- **`docs/ARCHITECTURE.md`** — Full architecture guide
- **`docs/HOW_IT_WORKS.md`** — Step-by-step flow documentation
- **`docs/TUTORIAL.md`** — Quick start tutorial
- **Provider types**: OpenAI-compatible, Anthropic, Google Gemini
- **3 research modes**: Light bobble, Light caster, RayCaster
- **PDNA manifold engine** (lfe/noor_pdna.py)
- **Local search engine** (lfe/deepsearch.py): Bing, Ddg, Gh, Arxiv

### Changed
- `noorak_search.py` moved to `engine/noorak_search.py`
- `deepsearch.py`, `noor_pdna.py`, `test_noor_pdna.py` moved to `lfe/`
- `corpus/` renamed to `storage/corpus/`
- README.md updated with correct paths and new sections
- CONTRIBUTING.md rewritten as proper developer guide
- SECURITY.md completed with full security guide

### Fixed
- `deepsearch.py` now uses `storage/corpus/` instead of hardcoded `corpus/`
- `fetch_page` returns real content via `direct_fetch_page()` with browser UA
- Cache hit: **0.001s** vs **8.8s** first run

## [1.0.0] - 2026-09-02

### Added
- Initial release
- PDNA manifold engine
- Deep search with Bing, Ddg, Gh, Arxiv
- Basic research loop
- Interactive provider setup
