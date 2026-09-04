# Security Guide — Noorak Search CLI

## Principle: keys never touch disk

Noorak **never** writes API keys, base URLs, or model names to disk or to
version control. All credentials are kept in memory only.

## Environment variables (recommended)

For production, CI/CD, or automated use, configure the following variables
in your shell or CI environment — never in a file:

```bash
export NOORAK_API_KEY="your-api-key-here"
export NOORAK_BASE_URL="https://api.example.com/v1"
export NOORAK_MODEL="your-model-name"
export NOORAK_API_TYPE="openai"   # or "anthropic" or "gemini"
```

If all three of `NOORAK_API_KEY`, `NOORAK_BASE_URL`, and `NOORAK_MODEL`
are set, the CLI skips the interactive prompt entirely.

## Interactive mode

If environment variables are not set, the CLI prompts you for credentials
at runtime. Your input is used only for that session and is not logged
or persisted.

## `.gitignore`

The `.gitignore` file ensures that sensitive files are never committed:

```
__pycache__/
*.pyc
output/
.ftai_key
.ftai_base
.env
```

## TLS / certificate handling

Noorak uses `ssl._create_unverified_context()` when communicating with
providers. This is intentional to handle endpoints with self-signed
certificates. If you prefer strict verification, modify the context in
`noorak_search.py`.

## Best practices

1. **Never commit** API keys to version control — even accidentally via
   `git add .`. Check your repo with `git status` before pushing.
2. **Rotate keys** regularly, especially if you suspect a leak.
3. **Use separate keys** for development vs. production.
4. **Restrict key permissions** (read-only if full access is not needed).
5. **Audit** your environment regularly for stray `.env` files.

## What Noorak does NOT do

- Does not store credentials in `~/.noorak_config.json` or any other file.
- Does not print keys to stdout or logs (the `[Noorak]` info line shows
  only the model name and base URL, never the key).
- Does not transmit keys to third parties — only to the provider you configure.
