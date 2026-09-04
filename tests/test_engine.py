#!/usr/bin/env python3
"""
Unit tests for engine/noorak_search.py — tests all core functions WITHOUT API calls.
Run: python3 tests/test_engine.py
"""
import os, sys, json, time
from pathlib import Path

# Ensure engine is importable
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR / "engine"))
sys.path.insert(0, str(SCRIPT_DIR / "lfe"))

import noorak_search as ns

passed = 0
failed = 0

def assert_eq(actual, expected, msg=""):
    global passed, failed
    if actual != expected:
        print(f"  ❌ FAIL: {msg} — Expected {expected!r}, got {actual!r}")
        failed += 1
    else:
        print(f"  ✅ PASS: {msg}")
        passed += 1

def assert_true(cond, msg=""):
    global passed, failed
    if not cond:
        print(f"  ❌ FAIL: {msg}")
        failed += 1
    else:
        print(f"  ✅ PASS: {msg}")
        passed += 1

def assert_in(sub, full, msg=""):
    global passed, failed
    if sub not in full:
        print(f"  ❌ FAIL: {msg} — '{sub}' not found in {full[:100]}")
        failed += 1
    else:
        print(f"  ✅ PASS: {msg}")
        passed += 1

# ---------- Cache tests ----------
class TestCache:
    def test_cache_set_and_get(self):
        key = f"test_cache_{time.time()}"
        ns.cache_set("test", key, "test_value_123")
        got = ns.cache_get("test", key)
        assert_eq(got, "test_value_123", f"cache_set/get roundtrip")

    def test_cache_disabled(self):
        original = ns.CACHE_TTL_HOURS
        ns.CACHE_TTL_HOURS = 0
        key = f"test_disabled_{time.time()}"
        ns.cache_set("test", key, "should_not_cache")
        got = ns.cache_get("test", key)
        assert_eq(got, None, "cache disabled returns None")
        ns.CACHE_TTL_HOURS = original

    def test_cache_different_kinds_dont_collide(self):
        key = f"collision_test_{time.time()}"
        ns.cache_set("search", key, "search_result")
        ns.cache_set("page", key, "page_result")
        got_search = ns.cache_get("search", key)
        got_page = ns.cache_get("page", key)
        assert_eq(got_search, "search_result", "search cache not collided")
        assert_eq(got_page, "page_result", "page cache not collided")

    def test_cache_key_uniqueness(self):
        key1 = f"key_{time.time()}_1"
        key2 = f"key_{time.time()}_2"
        ns.cache_set("test", key1, "a")
        ns.cache_set("test", key2, "b")
        assert_eq(ns.cache_get("test", key1), "a", "key1 distinct")
        assert_eq(ns.cache_get("test", key2), "b", "key2 distinct")

# ---------- EvidenceLog tests ----------
class TestEvidenceLog:
    def test_add_and_render(self):
        ev = ns.EvidenceLog()
        ev.add("web_search", {"query": "test"}, "search_result_here")
        ev.add("fetch_page", {"url": "https://example.com"}, "page_content")
        md = ev.render_markdown("test query")
        assert_in("test query", md, "query in rendered markdown")
        assert_in("web_search", md, "web_search in rendered markdown")
        assert_in("fetch_page", md, "fetch_page in rendered markdown")
        assert_in("search_result_here", md, "search result in rendered markdown")
        assert_in("page_content", md, "page content in rendered markdown")

    def test_auto_save(self):
        ev = ns.EvidenceLog()
        ev.add("web_search", {"query": "test"}, "result")
        path = ns.auto_save_report("test auto-save", ev)
        assert_true(Path(path).exists(), f"auto-save file created: {path}")
        content = Path(path).read_text(encoding="utf-8")
        assert_in("test auto-save", content, "query in auto-saved file")
        assert_in("Evidence", content, "Evidence section in auto-save")

# ---------- PDNA tool tests ----------
class TestPdnATool:
    def test_pdna_base(self):
        result = ns._pdna_tool({"action": "base", "y": 0.5, "z": 0.5, "x": 0.5})
        data = json.loads(result)
        assert_eq(data["action"], "base", "pdna base action")
        assert_true("result" in data, "pdna base has result field")

    def test_pdna_changer(self):
        result = ns._pdna_tool({"action": "changer", "y": 0.5, "z": 0.5, "x": 0.5})
        data = json.loads(result)
        assert_eq(data["action"], "changer", "pdna changer action")
        assert_true("results" in data, "pdna changer has results field")

    def test_pdna_iterate(self):
        result = ns._pdna_tool({"action": "iterate", "y": 0.5, "z": 0.5, "x": 0.5, "n": 3})
        data = json.loads(result)
        assert_eq(data["action"], "iterate", "pdna iterate action")
        assert_true("results" in data, "pdna iterate has results field")

    def test_pdna_sphere(self):
        result = ns._pdna_tool({"action": "sphere", "resolution": 3})
        data = json.loads(result)
        assert_eq(data["action"], "sphere", "pdna sphere action")
        assert_true("results" in data, "pdna sphere has results field")

    def test_pdna_summary(self):
        states = [{"y": 0.5, "z": 0.5, "x": 0.5}]
        result = ns._pdna_tool({"action": "summary", "states": states})
        data = json.loads(result)
        assert_eq(data["action"], "summary", "pdna summary action")
        assert_true("result" in data, "pdna summary has result field")

# ---------- TOOLS definition test ----------
class TestTools:
    def test_tools_list_not_empty(self):
        assert_true(len(ns.TOOLS) > 0, "TOOLS list is not empty")
        tool_names = [t["function"]["name"] for t in ns.TOOLS]
        assert_in("web_search", tool_names, "web_search in TOOLS")
        assert_in("fetch_page", tool_names, "fetch_page in TOOLS")
        assert_in("save_research", tool_names, "save_research in TOOLS")
        assert_in("pdna", tool_names, "pdna in TOOLS")
        print(f"  ✅ PASS: TOOLS contains {len(ns.TOOLS)} tools: {', '.join(tool_names)}")

# ---------- Dynamic paths test ----------
class TestPaths:
    def test_engine_path(self):
        assert_true(Path("engine/noorak_search.py").exists(), "engine/noorak_search.py exists")

    def test_lfe_path(self):
        assert_true(Path("lfe/deepsearch.py").exists(), "lfe/deepsearch.py exists")
        assert_true(Path("lfe/noor_pdna.py").exists(), "lfe/noor_pdna.py exists")

# ---------- Main runner ----------
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Noorak Engine Unit Tests")
    print("=" * 60 + "\n")

    test_classes = [TestCache, TestEvidenceLog, TestPdnATool, TestTools, TestPaths]

    for cls in test_classes:
        print(f"\n--- {cls.__name__} ---")
        instance = cls()
        for method_name in sorted(dir(instance)):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                except Exception as e:
                    print(f"  ❌ FAIL: {method_name} — {e}")
                    failed += 1

    print(f"\n{'=' * 60}")
    if failed == 0:
        print(f"✅ ALL {passed} tests passed!")
    else:
        print(f"❌ {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    sys.exit(1 if failed > 0 else 0)