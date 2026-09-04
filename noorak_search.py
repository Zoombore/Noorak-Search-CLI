#!/usr/bin/env python3
"""
Noorak Search CLI

A tool-capable model performs deep research by itself:
it decides what to search, fetches pages, and writes a final Markdown report
via tool-calling loops.

Three modes:
 - Light bobble  : baseline deep research (~4 tool calls)
 - Light caster  : two-phase plan, each phase gathers sources and writes a chunk (~8 tool calls)
 - RayCaster     : four-phase plan, each phase gathers sources and writes a chunk (~16 tool calls)

User picks mode, enters query, gets a Markdown report, then can:
 - run another search
 - view the last report
 - exit

Provider is chosen interactively at launch — you enter base URL, API key, and model name.
The CLI asks whether the endpoint is OpenAI-compatible, Anthropic, or Google Gemini
and configures the request format accordingly.
Nothing is hard-coded and no keys are written to disk.
Non-interactive mode: set NOORAK_API_KEY, NOORAK_BASE_URL, NOORAK_MODEL env vars.
"""

import json, os, ssl, subprocess, sys, time, urllib.request, urllib.parse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# ---------- Provider selection (interactive) ----------

def select_provider():
    """Ask the user for base URL, API key, model, and API type.
    Returns (api_key, base_url, model, api_type)."""
    print("\n=== Provider Setup ===")
    print("Supported endpoint types:")
    print("  1) OpenAI-compatible (default) — any endpoint following /chat/completions")
    print("  2) Anthropic — uses /v1/messages endpoint")
    print("  3) Google Gemini — uses /v1beta/models/{model}:generateContent")
    while True:
        choice = input("Select endpoint type [1-3]: ").strip()
        if choice in ("1", "2", "3"):
            break
        print("Invalid choice.")
    api_type = {"1": "openai", "2": "anthropic", "3": "gemini"}[choice]
    base_url = input("Enter base URL (e.g. https://api.example.com/v1): ").strip()
    api_key = input("Enter API key: ").strip()
    model = input("Enter model name: ").strip()
    return api_key, base_url, model, api_type

# Allow env-based non-interactive override
if (os.environ.get("NOORAK_API_KEY") and os.environ.get("NOORAK_BASE_URL")
        and os.environ.get("NOORAK_MODEL")):
    API_KEY = os.environ["NOORAK_API_KEY"]
    BASE_URL = os.environ["NOORAK_BASE_URL"]
    MODEL = os.environ["NOORAK_MODEL"]
    # Default to openai-compatible if not specified
    API_TYPE = os.environ.get("NOORAK_API_TYPE", "openai")
    print(f"[Noorak] Using provider from environment: {MODEL} ({API_TYPE}) @ {BASE_URL}")
else:
    API_KEY, BASE_URL, MODEL, API_TYPE = select_provider()

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
    # Anthropic messages format: role "user" or "assistant" with content list
    anthropic_messages = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "tool":
            # skip tool results in the first pass (not used by Anthropic directly)
            continue
        anthropic_messages.append({"role": role, "content": content})
    # For tool use, Anthropic uses content blocks
    body_messages = []
    for m in messages:
        if m["role"] == "system":
            body_messages.append({"role": "user", "content": [{"type": "text", "text": m["content"]}]})
        elif m["role"] == "user":
            body_messages.append({"role": "m.user", "content": [{"type": "text", "text": m["content"]}]})
        elif m["role"] == "assistant":
            blocks = []
            if isinstance(m["content"], str):
                blocks.append({"type": "text", "text": m["content"]})
            else:
                for b in m["content"]:
                    if b.get("type") == "tool_use":
                        blocks.append({"type": "tool_use", "id": b["id"],
                                       "name": b["function"]["name"],
                                       "input": b["function"]["arguments"]})
                    else:
                        blocks.append({"type": "text", "text": str(b)})
            body_messages.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            # tool results as user message
            pass
    # Simple approach: send as user/assistant pairs, let model decide
    simple_msgs = []
    for m in messages:
        if m["role"] == "system":
            simple_msgs.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            simple_msgs.append({"role": "assistant", "content": m["content"]})
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
                             "arguments": json.dumps(block.get("input", {}))}
            })
    return {"content": text, "tool_calls": tool_calls}

def _chat_gemini(messages, max_tokens):
    # Google Gemini: model name as path param, API key as query param
    encoded_model = urllib.parse.quote(MODEL)
    url = f"{BASE_URL.rstrip('/')}/v1beta/models/{encoded_model}:generateContent"
    api_key_param = f"?key={API_KEY}"
    # Convert messages to Gemini content format
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
]

# ---------- Local search engine (stdlib only) ----------
def run_deepsearch(args, cap_chars=8000):
    """Run our local deepsearch.py tool (stdlib only) and return captured stdout (truncated)."""
    p = subprocess.run([sys.executable, "deepsearch.py"] + args,
                       cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=120)
    out = p.stdout
    if not out.strip():
        out = (p.stderr or "no output")[-4000:]
    return out[:cap_chars]

def exec_tool(name, args):
    if name == "web_search":
        q = args.get("query","")
        eng = args.get("engines") or "bing,gh,arxiv"
        top = int(args.get("top") or 8)
        return run_deepsearch([q,"--engines",eng,"--top",str(top)])
    if name == "fetch_page":
        return run_deepsearch(["--url",args.get("url",""),"--name","_tool","--id","x"])
    if name == "save_research":
        md = args.get("markdown","")
        out_dir = SCRIPT_DIR / "output"
        out_dir.mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        fname = out_dir / f"research_{ts}.md"
        open(fname,"w",encoding="utf-8").write(md)
        return f"SAVED:{fname}"
    return "unknown tool"

# ---------- Research loop ----------
def researcher_loop(query, system_extra="", max_tool_calls=4):
    """Run the model with tool use. Let the model call tools naturally; we only nudge
    it via user messages and enforce a tool-call budget. No hard tool_choice forcing
    except as a last-resort fallback if nothing was produced."""
    sys_prompt = (
        "You are the Deep-Research sub-agent. "
        "You have REAL internet search tools: web_search (discover sources) and fetch_page (read a page). "
        "YOUR JOB: do the research YOURSELF using these tools - do not rely on prior knowledge. "
        "1) Use web_search to find authoritative sources (GitHub repos, arXiv papers, official docs). "
        "2) Use fetch_page on the most promising URLs to read them in depth. "
        "3) Ground every claim in a fetched source; cite URL inline. Mark [Personal Analysis] only when truly needed. "
        "4) When you have gathered enough material, call save_research ONCE with the complete Markdown "
        "document (Executive Summary, findings, architecture with Mermaid if needed, roadmap, decision matrix, "
        "risks, next steps, and a Sources appendix of all URLs you used). "
        "5) You have a BUDGET of " + str(max_tool_calls) + " tool calls. Keep searching until you reach that budget "
        "or have enough sources, then call save_research. Do not stop early. "
        "Be concrete and pragmatic."
    )
    if system_extra:
        sys_prompt += " " + system_extra

    messages = [
        {"role":"system","content":sys_prompt},
        {"role":"user","content":query}
    ]

    tool_count = 0
    saved_path = None
    safety = max_tool_calls * 3 + 6

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
                messages.append({"role":"tool","tool_call_id":t["id"],"content":res[:16000]})
                if name == "save_research" and res.startswith("SAVED:"):
                    return res.split(":",1)[1]

            if tool_count >= max_tool_calls:
                messages.append({"role":"user","content":
                    f"You have reached your tool-call budget ({tool_count}/{max_tool_calls}). "
                    "Stop searching now. Finalize by calling save_research with the complete report."})
            continue

        else:
            if tool_count < max_tool_calls:
                messages.append({"role":"user","content":
                    f"You have not finished researching. Tool calls used: {tool_count}/{max_tool_calls}. "
                    "Continue by calling web_search or fetch_page to gather more sources."})
            else:
                messages.append({"role":"user","content":
                    "Tool budget reached. Call save_research now with the final Markdown report."})
                msg2 = chat(messages, max_tokens=3000)
                tcs2 = msg2.get("tool_calls") or []
                if tcs2:
                    for t in tcs2:
                        fn = t["function"]; name = fn["name"]
                        try: args = json.loads(fn.get("arguments") or "{}")
                        except Exception: args = {}
                        res = exec_tool(name, args)
                        if name == "save_research" and res.startswith("SAVED:"):
                            return res.split(":",1)[1]
                last_text = msg2.get("content") or assistant.get("content") or ""
                if last_text.strip():
                    out_dir = SCRIPT_DIR / "output"
                    out_dir.mkdir(exist_ok=True)
                    ts = time.strftime("%Y%m%d-%H%M%S")
                    fname = out_dir / f"research_{ts}.md"
                    open(fname,"w",encoding="utf-8").write(last_text)
                    return str(fname)
                msg3 = chat(messages, tool_choice={"type":"function","function":{"name":"save_research"}}, max_tokens=3000)
                for t in (msg3.get("tool_calls") or []):
                    fn = t["function"]; name = fn["name"]
                    try: args = json.loads(fn.get("arguments") or "{}")
                    except Exception: args = {}
                    res = exec_tool(name, args)
                    if name == "save_research" and res.startswith("SAVED:"):
                        return res.split(":",1)[1]
                return None

    return saved_path

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
    print('\n=== Noorak Search CLI ===')
    for key, val in MODES.items():
        print(' %s) %s - %s' % (key, val['name'], val['desc']))
    while True:
        choice = input('Select mode [1-3]: ').strip()
        if choice in MODES:
            return choice
        print('Invalid choice.')

def main():
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
            print("⚠️ Research did not produce a saved report (maybe hit iteration limit).")
            again = input("Try again with same query? (y/n): ").strip().lower()
            if again != "y":
                continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!")
        sys.exit(0)
