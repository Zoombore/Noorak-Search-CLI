#!/usr/bin/env python3
"""
Noorak Search CLI — Engine v2.0

A tool-capable model performs deep research by itself:
it decides what to search, fetches pages, and writes a final Markdown report
via tool-calling loops.

Layered project layout:
  engine/   -> this orchestrator (loop, tool-calling, provider)
  lfe/      -> Light Finder Engine (deepsearch.py, noor_pdna.py)
  cache/    -> TTL cache for web_search / fetch_page results
  storage/  -> raw corpus / downloaded pages
  output/   -> final Markdown reports
  docs/     -> how-it-works, tutorial, architecture

Key guarantees:
  - Cache: every web_search / fetch_page result is cached under cache/
    for NOORAK_CACHE_TTL hours (default 24, set 0 to disable).
    Identical queries cost 0 tokens and run instantly.
  - Save is GUARANTEED. Fallback ladder:
      1) model calls save_research (normal path)
      2) budget reached -> forced tool_choice save_research
      3) last resort -> AUTO-SAVE: report is built from the collected
         evidence log and written to output/.
    researcher_loop NEVER returns without a saved file (unless fatal error).
  - All paths are DYNAMIC (relative to installation directory).
    Nothing is hardcoded to any machine.

Modes:
 - Light bobble  : baseline deep research (~4 tool calls)
 - Light caster  : two-phase plan with combined report (~8 tool calls)
 - RayCaster     : four-phase plan with combined report (~16 tool calls)

Provider:
 - Interactive prompt, or env vars:
   NOORAK_API_KEY, NOORAK_BASE_URL, NOORAK_MODEL, NOORAK_API_TYPE
 - No keys are ever written to disk.
"""

import json, os, ssl, subprocess, sys, time, hashlib, shutil, urllib.request, urllib.parse
from pathlib import Path

# ---------- Dynamic paths (installation-independent) ----------
ENGINE_DIR = Path(__file__).resolve().parent        # .../engine
ROOT_DIR = ENGINE_DIR.parent                        # repo root
LFE_DIR = ROOT_DIR / "lfe"
CACHE_DIR = ROOT_DIR / "cache"
STORAGE_DIR = ROOT_DIR / "storage"
CORPUS_DIR = STORAGE_DIR / "corpus"
OUTPUT_DIR = ROOT_DIR / "output"
for _d in (CACHE_DIR, STORAGE_DIR, CORPUS_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------- Cache layer (TTL) ----------
CACHE_TTL_HOURS = float(os.environ.get("NOORAK_CACHE_TTL", "24"))

def _cache_path(kind: str, key: str) -> Path:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{kind}_{h}.json"

def cache_get(kind: str, key: str):
    """Return cached value if fresh, else None. key is a stable string
    (e.g. 'web_search|query|engines|top' or 'fetch_page|<url>')."""
    if CACHE_TTL_HOURS <= 0:
        return None
    p = _cache_path(kind, key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data["ts"] > CACHE_TTL_HOURS * 3600:
            p.unlink(missing_ok=True)
            return None
        return data["value"]
    except Exception:
        return None

def cache_set(kind: str, key: str, value) -> None:
    if CACHE_TTL_HOURS <= 0:
        return
    try:
        _cache_path(kind, key).write_text(
            json.dumps({"ts": time.time(), "key": key, "value": value}, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass

# ---------- Provider configuration ----------
# Deferred: resolved on first chat() call or when main() runs.
# Environment vars override interactive prompt.
_API_KEY = os.environ.get("NOORAK_API_KEY")
_BASE_URL = os.environ.get("NOORAK_BASE_URL")
_MODEL = os.environ.get("NOORAK_MODEL")
_API_TYPE = os.environ.get("NOORAK_API_TYPE", "openai")

if _API_KEY and _BASE_URL and _MODEL:
    API_KEY, BASE_URL, MODEL, API_TYPE = _API_KEY, _BASE_URL, _MODEL, _API_TYPE
    print(f"[Noorak] Using provider from environment: {MODEL} ({API_TYPE}) @ {BASE_URL}")
else:
    API_KEY = BASE_URL = MODEL = API_TYPE = None
    print("[Noorak] Provider not configured yet. Will prompt on first use.")

# ---------- API helpers ----------
def _openai_headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def _anthropic_headers():
    # Anthropic: x-api-key header instead of Authorization Bearer
    return {"x-api-key": API_KEY, "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"}

def _gemini_headers():
    # Google Gemini: uses API key as query param
    return {"Content-Type": "application/json"}

def chat(messages, tool_choice="auto", max_tokens=2500):
    """Send a message to the configured provider and return the model's reply."""
    _ensure_provider()
    if API_TYPE == "openai":
        return _chat_openai(messages, tool_choice, max_tokens)
    elif API_TYPE == "anthropic":
        return _chat_anthropic(messages, max_tokens)
    elif API_TYPE == "gemini":
        return _chat_gemini(messages, max_tokens)
    else:
        return _chat_openai(messages, tool_choice, max_tokens)

def _openai_chat_url():
    return BASE_URL.rstrip("/") + "/chat/completions"

def _chat_openai(messages, tool_choice, max_tokens):
    payload = json.dumps({
        "model": MODEL, "messages": messages, "tools": TOOLS,
        "tool_choice": tool_choice, "temperature": 0.4, "max_tokens": max_tokens
    })
    req = urllib.request.Request(_openai_chat_url(), data=payload.encode(),
                                 headers=_openai_headers())
    resp = urllib.request.urlopen(req, timeout=120,
                                  context=ssl._create_unverified_context()).read()
    data = json.loads(resp)
    msg = data["choices"][0]["message"]
    # DeepSeek-V4 etc. may return reasoning_content; keep it available
    reasoning = data.get("choices",[{}])[0].get("message",{}).get("reasoning_content","")
    if reasoning:
        msg["reasoning"] = reasoning
    # Some models (DeepSeek) put text in reasoning instead of content
    if not msg.get("content") and reasoning:
        msg["content"] = reasoning
    return msg

def _chat_anthropic(messages, max_tokens):
    # Simple approach: send flattened user/assistant pairs
    simple_msgs = []
    for m in messages:
        if m["role"] == "system":
            simple_msgs.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            c = m["content"]
            if isinstance(c, list):
                c = " ".join(str(b.get("text","")) for b in c if b.get("type")=="text")
            simple_msgs.append({"role": "assistant", "content": c})
        elif m["role"] == "user":
            simple_msgs.append({"role": "user", "content": m["content"]})
    payload = json.dumps({
        "model": MODEL, "messages": simple_msgs,
        "max_tokens": max_tokens, "temperature": 0.4
    })
    url = BASE_URL.rstrip("/") + "/v1/messages"
    req = urllib.request.Request(url, data=payload.encode(), headers=_anthropic_headers())
    resp = urllib.request.urlopen(req, timeout=120,
                                  context=ssl._create_unverified_context()).read()
    data = json.loads(resp)
    # Normalize to openai-like format
    content = data.get("content", [])
    text = ""
    tool_calls = []
    for block in content:
        if block.get("type") == "text":
            text += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {"name": block.get("name", ""),
                             "arguments": json.dumps(block.get("input", {}), ensure_ascii=False)}
            })
    return {"content": text, "tool_calls": tool_calls}

def _chat_gemini(messages, max_tokens):
    # Google Gemini: model name as path param, API key as query param
    encoded_model = urllib.parse.quote(MODEL)
    url = f"{BASE_URL.rstrip('/')}/v1beta/models/{encoded_model}:generateContent"
    api_key_param = f"?key={API_KEY}"
    contents = []
    for m in messages:
        if m["role"] == "system":
            contents.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] in ("user", "assistant"):
            contents.append({"role": m["role"],
                             "parts": [{"text": m["content"]}]})
    payload = json.dumps({"contents": contents, "generationConfig": {
        "maxOutputTokens": max_tokens, "temperature": 0.4
    }})
    req = urllib.request.Request(url + api_key_param, data=payload.encode(),
                                 headers=_gemini_headers())
    resp = urllib.request.urlopen(req, timeout=120,
                                  context=ssl._create_unverified_context()).read()
    data = json.loads(resp)
    candidates = data.get("candidates", [])
    text = ""
    tool_calls = []
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        for p in parts:
            text += p.get("text", "")
    return {"content": text, "tool_calls": tool_calls}

# ---------- Tool definitions ----------
TOOLS = [
    {"type":"function","function":{
        "name":"web_search",
        "description":"Search the real internet (engines: bing, gh=GitHub, arxiv). Returns ranked results (title, URL, snippet).",
        "parameters":{"type":"object","properties":{
            "query":{"type":"string"},
            "engines":{"type":"string","description":"comma list subset of ddg,bing,gh,arxiv (default bing,gh,arxiv)"},
            "top":{"type":"integer","description":"how many results to return (default 8)"}
        },"required":["query"]}}},
    {"type":"function","function":{
        "name":"fetch_page",
        "description":"Fetch a single URL from the internet and return its cleaned text (title + body). Use after web_search to read a promising source in depth.",
        "parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{
        "name":"save_research",
        "description":"Write the COMPLETE final research document (Markdown) to disk. Call exactly once at the end.",
        "parameters":{"type":"object","properties":{"markdown":{"type":"string"}},"required":["markdown"]}}},
    {"type":"function","function":{
        "name":"pdna",
        "description":"NoorPDNA — Three-Dimensional Identity Manifold Engine. Compute psychological state values on a 3D sphere.",
        "parameters":{"type":"object","properties":{
            "action":{"type":"string","description":"base|changer|iterate|sphere|summary",
                "enum":["base","changer","iterate","sphere","summary"]},
            "y":{"type":"number","description":"Identity & Expression axis value [-1, +1]", "minimum":-1, "maximum":1},
            "z":{"type":"number","description":"Sensory Processing axis value [-1, +1]", "minimum":-1, "maximum":1},
            "x":{"type":"number","description":"Executive Control axis value [-1, +1]", "minimum":-1, "maximum":1},
            "n":{"type":"integer","description":"Multiplier (for iterate)", "minimum":1, "default":5},
            "resolution":{"type":"integer","description":"Sphere sampling resolution", "minimum":3, "maximum":10, "default":5},
            "states":{"type":"array","description":"Array of state dicts (for summary)"}
        },"required":["action"]}}},
]

# ---------- Light Finder Engine (lfe/) imports ----------
def _import_lfe():
    sys.path.insert(0, str(LFE_DIR))
    import deepsearch as _ds   # noqa
    import noor_pdna as _pd    # noqa
    return _ds, _pd

DS, PDNA = _import_lfe()

def run_deepsearch(args, cap_chars=8000):
    """Run our local deepsearch.py tool (stdlib only) and return captured stdout (truncated)."""
    p = subprocess.run([sys.executable, str(LFE_DIR / "deepsearch.py")] + args,
                       cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=120)
    out = p.stdout
    if not out.strip():
        out = (p.stderr or "no output")[-4000:]
    return out[:cap_chars]

# ---------- Direct fetch_page (bypass deepsearch.py for better results) ----------
FETCH_UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def direct_fetch_page(url, timeout=25):
    """Fetch a URL directly with realistic headers and return cleaned text."""
    req = urllib.request.Request(url, headers=FETCH_UA)
    with urllib.request.urlopen(req, timeout=timeout,
                                 context=ssl._create_unverified_context()) as r:
        raw = r.read().decode("utf-8", "replace")
    # Use deepsearch.html_to_text for text extraction
    text = DS.html_to_text(raw)
    # Extract title
    import re as _re, html as _html
    m = _re.search(r"<title[^>]*>(.*?)</title>", raw, _re.S | _re.I)
    title = _html.unescape(m.group(1)).strip() if m else url.split("/")[2]
    return f"TITLE: {title}\nURL: {url}\nFETCHED: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{text[:15000]}"

# ---------- Tool execution (with cache) ----------
def exec_tool(name, args):
    if name == "web_search":
        q = args.get("query", "")
        eng = args.get("engines") or "bing,gh,arxiv"
        top = int(args.get("top") or 8)
        key = f"web_search|{q}|{eng}|{top}"
        cached = cache_get("search", key)
        if cached is not None:
            return cached
        res = run_deepsearch([q, "--engines", eng, "--top", str(top)])
        cache_set("search", key, res)
        return res
    if name == "fetch_page":
        url = args.get("url", "")
        if not url:
            return "ERROR: no url provided."
        key = f"fetch_page|{url}"
        cached = cache_get("page", key)
        if cached is not None:
            return cached
        res = direct_fetch_page(url)
        cache_set("page", key, res)
        return res
    if name == "save_research":
        md = args.get("markdown", "")
        if not md.strip():
            return "ERROR: empty markdown, nothing saved."
        out_dir = OUTPUT_DIR
        out_dir.mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        fname = out_dir / f"research_{ts}.md"
        fname.write_text(md, encoding="utf-8")
        return f"SAVED:{fname}"
    if name == "pdna":
        return _pdna_tool(args)
    return f"unknown tool: {name}"

# ---------- NoorPDNA tool integration ----------
def _pdna_tool(args: dict) -> str:
    """Handle pdna tool calls from the model. Uses lfe/noor_pdna.py"""
    import noor_pdna
    action = args.get("action", "base")
    if action == "base":
        y = args.get("y", 0); z = args.get("z", 0); x = args.get("x", 0)
        return json.dumps({"action": "base", "result": noor_pdna.pdna_base(y, z, x)}, ensure_ascii=False)
    elif action == "changer":
        y = args.get("y", 0); z = args.get("z", 0); x = args.get("x", 0)
        results = noor_pdna.pdna_changer(y, z, x)
        return json.dumps({"action": "changer", "results": results}, ensure_ascii=False)
    elif action == "iterate":
        y = args.get("y", 0); z = args.get("z", 0); x = args.get("x", 0)
        n = args.get("n", 5)
        results = noor_pdna.pdna_iterate(y, z, x, n)
        return json.dumps({"action": "iterate", "results": results}, ensure_ascii=False)
    elif action == "sphere":
        resolution = args.get("resolution", 5)
        results = noor_pdna.pdna_sphere_sample(resolution)
        return json.dumps({"action": "sphere", "results": results}, ensure_ascii=False)
    elif action == "summary":
        states = args.get("states", [])
        return json.dumps({"action": "summary", "result": noor_pdna.pdna_summary(states)}, ensure_ascii=False)
    return json.dumps({"error": f"unknown pdna action: {action}"})

# ---------- Evidence log (for auto-save fallback) ----------
class EvidenceLog:
    """Collects every tool result during a run so a report can be built
    even when the model never calls save_research."""
    def __init__(self):
        self.entries = []   # list of (tool_name, args_str, result)
    def add(self, name, args, result):
        self.entries.append((name, json.dumps(args, ensure_ascii=False)[:200], result))
    def render_markdown(self, query):
        lines = [
            "# Auto-saved Research Report (evidence log)",
            "",
            f"**Query:** {query}",
            f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Tool calls:** {len(self.entries)}",
            "",
            "> ⚠️ The model did not call `save_research`, so this report was",
            "> auto-compiled by the engine from the collected search & fetch results.",
            "",
            "## Evidence",
            "",
        ]
        for i, (name, args, result) in enumerate(self.entries, 1):
            lines.append(f"### {i}. `{name}` {args}")
            lines.append("")
            lines.append("```")
            lines.append(result[:6000])
            lines.append("```")
            lines.append("")
        sources = []
        for name, args, result in self.entries:
            if name == "fetch_page":
                try:
                    a = json.loads(args)
                    if a.get("url"): sources.append(a["url"])
                except Exception: pass
        if sources:
            lines.append("## Sources")
            lines.append("")
            for s in dict.fromkeys(sources):
                lines.append(f"- {s}")
            lines.append("")
        return "\n".join(lines)

def auto_save_report(query, evidence: EvidenceLog) -> str:
    """Last-resort save: build a report from the evidence log and write it."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = OUTPUT_DIR / f"research_{ts}_auto.md"
    fname.write_text(evidence.render_markdown(query), encoding="utf-8")
    return str(fname)

# ---------- Research loop (save GUARANTEED) ----------
def researcher_loop(query, system_extra="", max_tool_calls=4):
    """Run the model with tool use. Save is guaranteed via a 3-step ladder:
       1) model calls save_research naturally
       2) budget reached -> forced tool_choice=save_research
       3) auto-save from evidence log (never returns None for a real run)
    """
    sys_prompt = (
        "You are the Deep-Research sub-agent. "
        "You have REAL internet search tools: web_search (discover sources) and fetch_page (read a page). "
        "YOUR JOB: do the research YOURSELF using these tools - do not rely on prior knowledge. "
        "1) Use web_search to find authoritative sources (GitHub repos, arXiv papers, official docs). "
        "2) Use fetch_page on the most promising URLs to read them in depth. "
        "3) Ground every claim in a fetched source; cite URL inline. Mark [Personal Analysis] only when truly needed. "
        "4) When you have gathered enough material, call save_research ONCE with the complete Markdown "
        "document (Executive Summary, findings, analysis, risks, next steps, and a Sources appendix of all URLs you used). "
        "5) You have a BUDGET of " + str(max_tool_calls) + " tool calls. Keep searching until you reach that budget "
        "or have enough sources, then call save_research. Do not stop early. "
        "6) MANDATORY: you MUST end your research by calling save_research. A run that never calls "
        "save_research is a FAILED run."
        "Be concrete and pragmatic."
    )
    if system_extra:
        sys_prompt += " " + system_extra

    messages = [
        {"role":"system","content":sys_prompt},
        {"role":"user","content":query}
    ]

    tool_count = 0
    safety = max_tool_calls * 3 + 6
    evidence = EvidenceLog()

    for _ in range(safety):
        msg = chat(messages, max_tokens=1800)
        tcs = msg.get("tool_calls") or []

        assistant = {"role":"assistant","content":msg.get("content") or ""}
        if tcs:
            assistant["tool_calls"] = [{"id":t["id"],"type":"function",
                                        "function":{"name":t["function"]["name"],
                                                    "arguments":t["function"]["arguments"]}}
                                       for t in tcs]

        messages.append(assistant)

        if tcs:
            tool_count += len(tcs)
            for t in tcs:
                fn = t["function"]; name = fn["name"]
                try: args = json.loads(fn.get("arguments") or "{}")
                except Exception: args = {}
                res = exec_tool(name, args)
                evidence.add(name, args, res)
                messages.append({"role":"tool","tool_call_id":t["id"],"content":res[:16000]})
                if name == "save_research" and res.startswith("SAVED:"):
                    return res.split(":",1)[1]

            if tool_count >= max_tool_calls:
                messages.append({"role":"user","content":
                    f"You have reached your tool-call budget ({tool_count}/{max_tool_calls}). "
                    "Stop searching now. Call save_research ONCE with the complete final Markdown report."})
            continue

        else:
            if tool_count < max_tool_calls:
                messages.append({"role":"user","content":
                    f"You have not finished researching. Tool calls used: {tool_count}/{max_tool_calls}. "
                    "Continue by calling web_search or fetch_page to gather more sources."})
            else:
                # ---- Fallback ladder: force the save ----
                messages.append({"role":"user","content":
                    "Tool budget reached. Call save_research now with the final Markdown report."})
                try:
                    msg2 = chat(messages, tool_choice={"type":"function","function":{"name":"save_research"}},
                                max_tokens=6000)
                    for t in (msg2.get("tool_calls") or []):
                        fn = t["function"]; name = fn["name"]
                        try: args = json.loads(fn.get("arguments") or "{}")
                        except Exception: args = {}
                        res = exec_tool(name, args)
                        if name == "save_research" and res.startswith("SAVED:"):
                            return res.split(":",1)[1]
                    last_text = msg2.get("content") or assistant.get("content") or ""
                    if last_text.strip():
                        out = OUTPUT_DIR / f"research_{time.strftime('%Y%m%d-%H%M%S')}_final.md"
                        out.write_text(last_text, encoding="utf-8")
                        return str(out)
                except Exception as e:
                    print(f"[Noorak] forced-save attempt failed: {e}")
                # ---- Last resort: auto-save from evidence ----
                return auto_save_report(query, evidence)

    return auto_save_report(query, evidence)

# ---------- Modes ----------
MODES = {
    "1": {"name":"Light bobble","tool_calls":4,"extra":"","desc":"Baseline deep research (~4 tool calls)."},
    "2": {"name":"Light caster","tool_calls":8,"extra":
          "First, output a concise research plan (2-3 bullet points). Then, execute the plan in two phases: "
          "each phase should gather sources and write a substantive chunk (~100k tokens worth of content). "
          "Finally, combine the two chunks into one cohesive report, explain why the chosen sources are reliable, "
          "and end with a short summary asking if the user is satisfied. Aim for ~200k tokens total.",
          "desc":"Two-phase plan with combined report (~8 tool calls)."},
    "3": {"name":"RayCaster","tool_calls":16,"extra":
          "First, output a detailed research plan with 4 clear parts. Then, execute each part as a separate phase, "
          "gathering sources and writing deep chunks. Combine all four parts into one extensive report, "
          "explain source reliability, and conclude with a summary asking if the user is satisfied. Aim for ~500k tokens total.",
          "desc":"Four-phase plan with combined report (~16 tool calls)."},
}

def pick_mode():
    print('\n=== Noorak Search CLI v2.0 ===')
    print(f'    cache: {CACHE_DIR} (TTL {CACHE_TTL_HOURS}h)')
    print(f'    output: {OUTPUT_DIR}')
    for key, val in MODES.items():
        print(' %s) %s - %s' % (key, val['name'], val['desc']))
    while True:
        choice = input('Select mode [1-3]: ').strip()
        if choice in MODES:
            return choice
        print('Invalid choice.')

def main():
    _ensure_provider()
    while True:
        mode = pick_mode()
        cfg = MODES[mode]
        print(f"\n--- {cfg['name']} ---")
        query = input("Enter your research query (or empty to cancel): ").strip()
        if not query:
            print("Returning to mode selection...")
            continue
        print("\nResearching... this may take a minute or two.\n")
        cap = int(os.environ.get("NOORAK_MAX_TOOLCALLS", "999"))
        eff_tool_calls = min(cfg["tool_calls"], cap)
        md_path = researcher_loop(query, system_extra=cfg["extra"], max_tool_calls=eff_tool_calls)
        if md_path:
            print(f"\n✅ Research complete! Report saved to: {md_path}")
            while True:
                nxt = input("\nOptions: 1) New search  2) View last report  3) Exit  > ").strip()
                if nxt == "1":
                    break
                elif nxt == "2":
                    try:
                        print("\n--- Report preview (first 30 lines) ---")
                        with open(md_path,encoding="utf-8") as f:
                            lines = f.readlines()
                            for i,line in enumerate(lines[:30]):
                                print(f"{i+1:3}: {line.rstrip()}")
                        if len(lines) > 30:
                            print("... (truncated)")
                    except Exception as e:
                        print(f"Could not read file: {e}")
                elif nxt == "3":
                    print("Goodbye!")
                    return
                else:
                    print("Invalid option.")
        else:
            print("⚠️ Research did not produce a saved report (unexpected error).")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!")
        sys.exit(0)