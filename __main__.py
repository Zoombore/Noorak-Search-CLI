#!/usr/bin/env python3
"""
Noorak Search CLI — Module entry point.

Usage:
    python3 -m noorak
    python3 -m noorak "your research query"
    NOORAK_API_KEY=... NOORAK_BASE_URL=... NOORAK_MODEL=... python3 -m noorak "query"
"""
import sys

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else None
    if query:
        # Non-interactive mode with a query argument
        import os
        if not (os.environ.get("NOORAK_API_KEY") and os.environ.get("NOORAK_BASE_URL") and os.environ.get("NOORAK_MODEL")):
            print("[Noorak] ERROR: Set NOORAK_API_KEY, NOORAK_BASE_URL, NOORAK_MODEL env vars for CLI mode.")
            print("  Or run without arguments for interactive mode.")
            sys.exit(1)
        sys.path.insert(0, str(__file__).resolve().parent / "engine")
        import noorak_search as ns
        md_path = ns.researcher_loop(query, max_tool_calls=ns.MODES["1"]["tool_calls"])
        print(f"\n✅ Report saved to: {md_path}")
        sys.exit(0)
    else:
        # Interactive mode — just run the engine
        sys.path.insert(0, str(__file__).resolve().parent / "engine")
        import noorak_search as ns
        ns.main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!")
        sys.exit(0)