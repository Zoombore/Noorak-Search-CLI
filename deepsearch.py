#!/usr/bin/env python3
"""
DeepSearch — multi-engine web search + page fetch + corpus builder.
Pure Python stdlib (urllib, html.parser, xml.etree). No pip needed.

Usage:
  deepsearch.py "query"                                # search all engines, print ranked results
  deepsearch.py "query" --engines ddg,bing,gh,arxiv    # pick engines
  deepsearch.py "query" --fetch 6 --name <slug>        # search + fetch top-N pages -> corpus/<slug>/
  deepsearch.py --url <URL> --name <slug> --id 03      # fetch one specific URL into corpus/<slug>/
  deepsearch.py "query" --top 30                       # show N raw rows (default 12)

Engines:
  ddg    DuckDuckGo (html endpoint)
  bing   Bing RSS feed
  gh     GitHub repository search (uses GH_TOKEN env or /workspace/.github_token)
  arxiv  arXiv API (papers)
"""
import argparse, html, io, os, re, ssl, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Mozilla-DS/1.0 research-bot"}

def _ctx():
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()

def http_get(url, timeout=15, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")

# ---------------- HTML -> text ----------------
class _TextExtract(HTMLParser):
    BLOCK = {"p","div","br","li","ul","ol","h1","h2","h3","h4","h5","h6","tr","table","section","article","blockquote","pre","header","footer"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip += 1
        if self.skip == 0 and tag in self.BLOCK:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script","style","noscript","svg") and self.skip > 0:
            self.skip -= 1
        if self.skip == 0 and tag in self.BLOCK:
            self.parts.append("\n")
    def handle_data(self, data):
        if self.skip == 0:
            self.parts.append(data)

def html_to_text(raw):
    p = _TextExtract()
    try:
        p.feed(raw)
    except Exception:
        pass
    t = "".join(p.parts)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()

# ---------------- Engines ----------------
def eng_ddg(q):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    raw = http_get(url)
    out, pat_a = [], re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    pat_s = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.S)
    links = pat_a.findall(raw); snips = pat_s.findall(raw)
    def clean(x): return re.sub(r"<[^>]+>", "", x).strip()
    for i, (href, title) in enumerate(links):
        m = re.search(r"uddg=([^&]+)", href)
        if m: href = urllib.parse.unquote(m.group(1))
        sn = clean(snips[i]) if i < len(snips) else ""
        out.append((title := clean(title), href, sn))
    return out

def eng_bing(q):
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&format=rss&count=20"
    raw = http_get(url)
    root = ET.fromstring(raw)
    out = []
    for item in root.iter("item"):
        t = item.findtext("title", "")
        l = item.findtext("link", "")
        d = item.findtext("description", "")
        d = re.sub(r"<[^>]+>", "", d or "")
        out.append((t, l, d.strip()))
    return out

def eng_gh(q):
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        for p in ("/workspace/.github_token", os.path.expanduser("~/.github_token")):
            if os.path.exists(p):
                token = open(p).read().strip(); break
    url = "https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=10"
    h = dict(UA); h["Accept"] = "application/vnd.github+json"
    if token: h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
        j = json_load(r.read().decode("utf-8", "replace"))
    out = []
    for it in j.get("items", []):
        out.append((it.get("full_name",""), it.get("html_url",""), f"★{it.get('stargazers_count','')} {it.get('description') or ''} {it.get('language') or ''}"))
    return out

def eng_arxiv(q):
    url = "http://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(q) + "&start=0&max_results=8&sortBy=relevance"
    raw = http_get(url, timeout=25)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(raw)
    def _txt(el, tag):
        n = el.find("a:" + tag, ns)
        return " ".join((n.text or "").split()) if n is not None else ""
    out = []
    for e in root.findall("a:entry", ns):
        _id = e.findtext("a:id", None, ns) or ""
        out.append((_txt(e, "title"), _id.strip(), _txt(e, "summary")[:300]))
    return out

def json_load(s):
    import json
    return json.loads(s)

ENGINES = {"ddg": eng_ddg, "bing": eng_bing, "gh": eng_gh, "arxiv": eng_arxiv}

def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        key = urllib.parse.urlparse(r[1]).netloc + urllib.parse.urlparse(r[1]).path
        if key in seen: continue
        seen.add(key); out.append(r)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--engines", default="ddg,bing,gh,arxiv")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--fetch", type=int, default=0, help="fetch top-N pages into corpus/<name>/")
    ap.add_argument("--name", default="run")
    ap.add_argument("--url", help="fetch a single URL instead of searching")
    ap.add_argument("--id", default="01", help="file id prefix for --url")
    a = ap.parse_args()

    if a.url:
        os.makedirs(f"corpus/{a.name}", exist_ok=True)
        raw = http_get(a.url, timeout=20)
        text = html_to_text(raw)[:25000]
        m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
        title = html.unescape(m.group(1)).strip() if m else a.url
        host = urllib.parse.urlparse(a.url).netloc.replace(".", "_")
        fn = f"corpus/{a.name}/{a.id}-{host}.txt"
        with open(fn, "w") as f:
            f.write(f"URL: {a.url}\nTITLE: {title}\nFETCHED: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{text}\n")
        print(f"saved -> {fn} ({len(text)} chars)")
        return

    if not a.query:
        ap.error("query required")
    q = a.query
    rows = []
    for name in [x for x in a.engines.split(",") if x in ENGINES]:
        try:
            for r in ENGINES[name](q):
                rows.append((name, r[0], r[1], r[2]))
        except Exception as e:
            print(f"[engine {name}] failed: {e}", file=sys.stderr)
        time.sleep(0.6)

    # rank: prefer github + arxiv for technical depth; simple interleave by engine order then score
    seen = set(); uniq = []
    for e, t, u, s in rows:
        k = urllib.parse.urlparse(u).netloc + urllib.parse.urlparse(u).path
        if k in seen: continue
        seen.add(k); uniq.append((e, t, u, s))

    print(f"# DeepSearch: {q}  ({len(uniq)} unique results from {a.engines})\n")
    for i, (e, t, u, s) in enumerate(uniq[:a.top], 1):
        print(f"[{i}] ({e}) {t}\n    {u}\n    {s[:160]}\n")

    if a.fetch:
        os.makedirs(f"corpus/{a.name}", exist_ok=True)
        done = 0
        for e, t, u, s in uniq[: a.fetch * 3]:  # try more, skip heavy domains
            if done >= a.fetch: break
            host = urllib.parse.urlparse(u).netloc
            if any(x in host for x in ("youtube.com", "facebook.com", "reddit.com", "linkedin.com", "x.com", "twitter.com", "instagram.com")):
                continue
            try:
                raw = http_get(u, timeout=15)
                text = html_to_text(raw)[:20000]
                fn = f"corpus/{a.name}/{done+1:02d}-{host.replace('.', '_')}.txt"
                with open(fn, "w") as f:
                    f.write(f"URL: {u}\nTITLE: {t}\nSOURCE: {u}\nFETCHED: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{text}\n")
                print(f"saved -> {fn} ({len(text)} chars)")
                done += 1
            except Exception as ex:
                print(f"fetch fail: {u} ({ex})", file=sys.stderr)
        print(f"\nfetched {done} pages into corpus/{a.name}/")

if __name__ == "__main__":
    main()
