#!/usr/bin/env python3

"""

Noorak Search CLI

Three modes:

 - Light bobble  : same as the deep research we performed (baseline)

 - Light caster  : plan -> two 100k-token-ish research chunks -> combined report (~200k tokens target)

 - RayCaster     : plan -> four phases with more iterations (~500k tokens target)



User picks mode, enters query, gets a Markdown report, then can:

 - run another search

 - view the last report

 - exit



All heavy lifting done by Gemma-4-31B-IT via tool-calling loop:

  web_search -> fetch_page -> save_research (once at end)

We support two providers:

  1. SelfLab (ArvanCloud) - default, uses Gemma-4-31B-IT

  2. FreeTheAI - uses kai/nvidia/nemotron-3-ultra-550b-a55b:free (or override via NOORAK_MODEL_FTAI)



Set NOORAK_PROVIDER to "selflab" (default) or "freetheai" to switch.

Set NOORAK_MAX_ITERS to override the mode-specific iteration count (as before).

"""



import json, os, ssl, subprocess, sys, time, urllib.request

from pathlib import Path



SCRIPT_DIR = Path(__file__).resolve().parent



# ---------- Provider selection (interactive) ----------
def select_provider():
    """Ask the user which provider/model to use. Returns (GKEY, GBASE, MODEL)."""
    print("\n=== Provider Setup ===")
    print(" 1) SelfLab (ArvanCloud) - uses Gemma-4-31B-IT from local credentials")
    print(" 2) FreeTheAI - fast free models (e.g. kai/openrouter/free)")
    print(" 3) Custom - I'll enter base URL, API key, and model name")
    while True:
        ch = input("Select provider [1-3] (or set env NOORAK_API_KEY/NOORAK_BASE_URL/NOORAK_MODEL to skip): ").strip()
        if ch == "1":
            gk = "/workspace/selflab/gemma4/.provider_key"
            gb = "/workspace/selflab/gemma4/.provider_base"
            if not os.path.exists(gk) or not os.path.exists(gb):
                sys.exit("ERROR: SelfLab credentials not found under /workspace/selflab/gemma4/")
            GKEY = open(gk).read().strip()
            GBASE = open(gb).read().strip() or "https://api.arvancloudai.ir/v1"
            MODEL = "Gemma-4-31B-IT"
            return GKEY, GBASE, MODEL
        elif ch == "2":
            GBASE = "https://api.freetheai.xyz/v1"
            GKEY = input("Enter your FreeTheAI API key (starts with sta_...): ").strip()
            MODEL = input("Enter model ID [kai/openrouter/free]: ").strip() or "kai/openrouter/free"
            return GKEY, GBASE, MODEL
        elif ch == "3":
            GBASE = input("Enter base URL (e.g. https://api.example.com/v1): ").strip()
            GKEY = input("Enter API key: ").strip()
            MODEL = input("Enter model name: ").strip()
            return GKEY, GBASE, MODEL
        else:
            print("Invalid choice.")

# Allow env-based non-interactive override
if os.environ.get("NOORAK_API_KEY") and os.environ.get("NOORAK_BASE_URL") and os.environ.get("NOORAK_MODEL"):
    GKEY = os.environ["NOORAK_API_KEY"]
    GBASE = os.environ["NOORAK_BASE_URL"]
    MODEL = os.environ["NOORAK_MODEL"]
    print(f"[Noorak] Using provider from environment: {MODEL} @ {GBASE}")
else:
    GKEY, GBASE, MODEL = select_provider()

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



def chat(messages, tool_choice="auto", max_tokens=2500):

    payload = json.dumps({"model":MODEL,"messages":messages,"tools":TOOLS,

                          "tool_choice":tool_choice,"temperature":0.4,"max_tokens":max_tokens})

    req = urllib.request.Request(GBASE+"/chat/completions", data=payload.encode(),

                                 headers={"Authorization":"Bearer "+GKEY,"Content-Type":"application/json"})

    # Use unverified context because ArvanCloud may use self-signed in sandbox

    resp = urllib.request.urlopen(req, timeout=120,

                                  context=ssl._create_unverified_context()).read()

    data = json.loads(resp)

    return data["choices"][0]["message"]



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



def researcher_loop(query, system_extra="", max_tool_calls=4):

    """Run Gemma with tool use. Let the model call tools naturally; we only nudge

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

                                        "function":{"name":t["function"]["name"],"arguments":t["function"]["arguments"]}}

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

            # else: let the model continue naturally on the next loop

            continue

        else:

            # No tool calls this round

            if tool_count < max_tool_calls:

                messages.append({"role":"user","content":

                    f"You have not finished researching. Tool calls used: {tool_count}/{max_tool_calls}. "

                    "Continue by calling web_search or fetch_page to gather more sources."})

            else:

                # Budget reached but no save_research yet -> ask for final report

                messages.append({"role":"user","content":

                    "Tool budget reached. Call save_research now with the final Markdown report."})

                # one more chance, then fallback

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

                # Fallback: if model still didn't save, write its last text as the report

                last_text = msg2.get("content") or assistant.get("content") or ""

                if last_text.strip():

                    out_dir = SCRIPT_DIR / "output"

                    out_dir.mkdir(exist_ok=True)

                    ts = time.strftime("%Y%m%d-%H%M%S")

                    fname = out_dir / f"research_{ts}.md"

                    open(fname,"w",encoding="utf-8").write(last_text)

                    return str(fname)

                # Last resort: force save_research

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



MODES = {

    "1": {"name":"Light bobble","tool_calls":4,"extra":"","desc":"Baseline deep research (same as earlier)."},

    "2": {"name":"Light caster","tool_calls":8,"extra":"First, output a concise research plan (2-3 bullet points). Then, execute the plan in two phases: each phase should gather sources and write a substantive chunk (~100k tokens worth of content). Finally, combine the two chunks into one cohesive report, explain why the chosen sources are reliable, and end with a short summary asking if the user is satisfied. Aim for a total output size around 200k tokens.","desc":"First, output a concise research plan (2-3 bullet points). Then, execute the plan in two phases: each phase should gather sources and write a substantive chunk (~100k tokens worth of content). Finally, combine the two chunks into one cohesive report, explain why the chosen sources are reliable, and end with a short summary asking if the user is satisfied. Aim for a total output size around 200k tokens."},

    "3": {"name":"RayCaster","tool_calls":16,"extra":"First, output a detailed research plan with 4 clear parts. Then, execute each part as a separate phase, gathering sources and writing deep chunks. Combine all four parts into one extensive report, explain source reliability, and conclude with a summary asking if the user is satisfied. Aim for a total output size around 500k tokens.","desc":"First, output a detailed research plan with 4 clear parts. Then, execute each part as a separate phase, gathering sources and writing deep chunks. Combine all four parts into one extensive report, explain source reliability, and conclude with a summary asking if the user is satisfied. Aim for a total output size around 500k tokens."},

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

            # Ask what to do next

            while True:

                nxt = input("\nOptions: 1) New search  2) View last report  3) Exit  > ").strip()

                if nxt == "1":

                    break  # go back to mode selection

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


