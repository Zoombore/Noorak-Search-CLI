# Contributing to Noorak Search CLI

Thank you for your interest in contributing to Noorak! This document explains
how to set up your development environment, submit changes, and follow
the project's conventions.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Development Setup](#development-setup)
4. [Running Tests](#running-tests)
5. [Commit Guidelines](#commit-guidelines)
6. [Pull Request Process](#pull-request-process)
7. [Code Style](#code-style)
8. [Adding New Tools](#adding-new-tools)
9. [Adding New Providers](#adding-new-providers)
10. [Reporting Issues](#reporting-issues)

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- A valid API key for an OpenAI-compatible provider (or Anthropic/Gemini)

### Fork and Clone

```bash
# Fork the repo on GitHub, then clone your fork:
git clone https://github.com/YOUR_USERNAME/Noorak-Search-CLI.git
cd Noorak-Search-CLI

# Add upstream remote:
git remote add upstream https://github.com/Zoombore/Noorak-Search-CLI.git
```

## Project Structure

```
Noorak-Search-CLI/
├── engine/                 # Orchestrator: chat, cache, EvidenceLog, save ladder
│   ├── __init__.py
│   └── noorak_search.py    # Main engine
├── lfe/                    # Light Finder Engine
│   ├── __init__.py
│   ├── deepsearch.py       # Search engines + fetch
│   ├── noor_pdna.py        # PDNA math engine
│   └── test_noor_pdna.py   # PDNA tests
├── tests/                  # Additional test suites
├── docs/                   # Documentation
├── cache/                  # TTL cache (runtime, gitignored)
├── storage/corpus/         # Raw downloaded pages (runtime, gitignored)
├── output/                 # Reports (runtime, gitignored)
├── .github/workflows/      # CI/CD
├── setup.py                # pip install
├── pyproject.toml          # Build config
├── Dockerfile              # Container
└── __main__.py             # python3 -m noorak entry point
```

## Development Setup

### 1. Clone and install

```bash
cd Noorak-Search-CLI
pip install -e .
```

This installs the `noorak` command and makes modules importable.

### 2. Set your API key

```bash
export NOORAK_API_KEY="your-api-key"
export NOORAK_BASE_URL="https://api.example.com/v1"
export NOORAK_MODEL="your-model-name"
export NOORAK_API_TYPE="openai"  # or "anthropic" or "gemini"
```

### 3. Run tests

```bash
# All tests
python -m pytest tests/ -v

# PDNA tests only
python lfe/test_noor_pdna.py

# Engine tests only
python -m pytest tests/test_engine.py -v

# Unit tests with pytest directly
python -m pytest tests/ -v --tb=short
```

### 4. Run the CLI

```bash
# Interactive
noorak

# With a query
noorak "What is the price of Tether?"

# Module mode
python3 -m noorak "What is the price of Tether?"
```

## Running Tests

Noorak uses **pytest** for testing. Test files live in `tests/`.

### Writing new tests

```python
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
import noorak_search as ns

def test_cache_roundtrip():
    """Cache stores and retrieves values correctly."""
    key = "test_key"
    ns.cache_set("test", key, "value")
    assert ns.cache_get("test", key) == "value"

def test_evidence_log():
    """EvidenceLog collects results and renders Markdown."""
    ev = ns.EvidenceLog()
    ev.add("web_search", {"query": "test"}, "result")
    md = ev.render_markdown("test query")
    assert "test query" in md
    assert "web_search" in md
```

**Test conventions:**
- Test file names: `test_*.py`
- Test function names: `test_*`
- Use descriptive docstrings
- No API key in tests (use mock/stubs)
- Tests must pass without network access

### Running tests without pytest

```bash
# PDNA tests (stdlib only)
python lfe/test_noor_pdna.py
```

## Commit Guidelines

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

Types:
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation
- `style` — formatting (no code change)
- `refactor` — code restructuring
- `test` — adding/updating tests
- `chore` — maintenance

Examples:
```
feat(cache): add TTL support for web_search results
fix(provider): handle anthropic response format correctly
docs(readme): update file paths to engine/lfe layout
test(engine): add EvidenceLog unit tests
```

### Branch naming

```
feature/<description>    # New features
fix/<description>        # Bug fixes
docs/<description>       # Documentation updates
test/<description>       # Test additions
```

## Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** and add tests.

3. **Run all tests**:
   ```bash
   python -m pytest tests/ -v
   python lfe/test_noor_pdna.py
   ```

4. **Verify the CLI works**:
   ```bash
   noorak "test query"
   ```

5. **Commit** with a conventional commit message.

6. **Push** and open a Pull Request against `main`.

7. **Wait for CI** to pass (test, lint, docker builds).

## Code Style

- Python 3.10+ syntax (no legacy code)
- Type hints on all functions
- Docstrings on all modules, classes, and public functions
- 100 character line length
- Use `Path` from `pathlib` for all file operations
- Never hardcode paths — compute relative to `__file__`
- Never commit API keys to any file
- Use `ssl._create_unverified_context()` only when necessary

### Import order

```python
# Standard library
import json, os, sys, time, urllib.request

# Third-party (none needed for core)
# from third_party import something

# Local
from pathlib import Path
sys.path.insert(0, str(__file__.resolve().parent / "engine"))
```

## Adding New Tools

To add a new tool (e.g., `web_fetch_image`):

1. Add the tool definition to `engine/noorak_search.py`:
   ```python
   TOOLS.append({
       "type": "function",
       "function": {
           "name": "web_fetch_image",
           "description": "Fetch an image from a URL and return analysis.",
           "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
       }
   })
   ```

2. Handle execution in `exec_tool()`:
   ```python
   if name == "web_fetch_image":
       return _handle_web_fetch_image(args)
   ```

3. Add tests in `tests/test_engine.py`.

4. Document in `docs/`.

## Adding New Providers

To support a new provider type (e.g., Ollama):

1. Add the handler function in `engine/noorak_search.py`:
   ```python
   def _chat_ollama(messages, max_tokens):
       # Build payload and send to Ollama API
       ...
   ```

2. Update `chat()` to route to the new handler.

3. Add provider type constant and update the interactive prompt.

4. Add tests.

## Reporting Issues

When filing an issue, include:

1. **Environment**: Python version, OS, provider/model
2. **Reproduction steps**
3. **Expected vs actual behavior**
4. **Full error output** (sanitize API keys!)
5. **Logs** if applicable

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
