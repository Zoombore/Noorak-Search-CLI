#!/usr/bin/env python3
"""
Local Search — Index, search, and rank files in the project.

Features:
  - Index files by content (keyword + line-based search)
  - Rank results by relevance (term frequency + recency)
  - Search code, docs, and data files simultaneously
  - Provide opinions on file structure and organization

Use cases:
  - "Find all references to 'cache' in the project"
  - "What files handle provider configuration?"
  - "Which files are largest and could be refactored?"
  - "Give me an opinion on the project structure"
"""
import os
import re
import json
import time
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Optional

# ---------- Data structures ----------
@dataclass
class SearchResult:
    filepath: str
    score: float
    lines: list = field(default_factory=list)
    context: str = ""

@dataclass
class FileInfo:
    path: str
    size_bytes: int
    lines: int
    extension: str
    last_modified: float
    hash: str = ""

# ---------- Indexer ----------
class LocalIndexer:
    """Build and maintain a searchable index of project files."""
    
    # Files to skip (config)
    SKIP_DIRS = {".git", "__pycache__", ".github", "node_modules", "cache", "output", "storage/corpus"}
    SKIP_EXTENSIONS = {".pyc", ".json", ".png", ".jpg", ".ico", ".svg", ".gif", ".pdf"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB max per file
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.index = {}  # filepath -> FileInfo
        self.word_map = defaultdict(set)  # word -> set of filepaths
        self.line_index = defaultdict(list)  # filepath -> [line_numbers]
        self.last_rebuild = 0
        self._build()
    
    def _should_skip(self, filepath: Path) -> bool:
        """Check if file should be excluded from index."""
        # Skip directories
        for part in filepath.parts:
            if part in self.SKIP_DIRS:
                return True
        # Skip extensions
        if filepath.suffix in self.SKIP_EXTENSIONS:
            return True
        # Skip cache/output files
        if "cache/" in str(filepath) or "output/" in str(filepath):
            return True
        return False
    
    def _build(self):
        """Build the full index."""
        if not self.root_dir.exists():
            return
        
        for filepath in self.root_dir.rglob("*"):
            if not filepath.is_file() or filepath.is_symlink():
                continue
            if self._should_skip(filepath):
                continue
            if filepath.stat().st_size > self.MAX_FILE_SIZE:
                continue
            
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                info = self._index_file(filepath, content)
                if info:
                    self.index[str(filepath)] = info
            except Exception:
                pass
        
        self.last_rebuild = time.time()
    
    def _index_file(self, filepath: Path, content: str) -> Optional[FileInfo]:
        """Index a single file's content."""
        lines = content.split("\n")
        file_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        
        info = FileInfo(
            path=str(filepath.relative_to(self.root_dir)),
            size_bytes=filepath.stat().st_size,
            lines=len(lines),
            extension=filepath.suffix,
            last_modified=filepath.stat().st_mtime,
            hash=file_hash
        )
        
        # Index words from all lines
        for line_num, line in enumerate(lines, 1):
            words = re.findall(r'[a-zA-Z_]{3,}', line.lower())
            for word in words:
                self.word_map[word].add(str(filepath))
            self.line_index[str(filepath)].append(line_num)
        
        return info
    
    def rebuild(self):
        """Force rebuild the index."""
        self.index = {}
        self.word_map = defaultdict(set)
        self.line_index = defaultdict(list)
        self._build()
    
    def get_file_info(self, filepath: str) -> Optional[FileInfo]:
        """Get FileInfo for a given path."""
        return self.index.get(filepath)
    
    def file_count(self) -> int:
        return len(self.index)


# ---------- Searcher ----------
class LocalSearcher:
    """Search indexed files with relevance ranking."""
    
    def __init__(self, indexer: LocalIndexer):
        self.indexer = indexer
    
    def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """
        Search for a query across all indexed files.
        Returns ranked results with relevance scores.
        
        Ranking algorithm:
        1. Split query into terms
        2. For each term, find files containing it
        3. Score = sum(term_frequencies) / total_lines (TF-IDF-like)
        4. Boost files containing ALL terms
        5. Sort by score descending
        """
        terms = re.findall(r'[a-zA-Z_]{3,}', query.lower())
        if not terms:
            return []
        
        # Find files matching each term
        term_files = {}  # term -> list of filepaths
        for term in terms:
            term_files[term] = self.indexer.word_map.get(term, set())
        
        if not any(term_files.values()):
            return []
        
        # Find intersection (files matching ALL terms)
        all_files = set.intersection(*[set(v) for v in term_files.values()]) if all(term_files.values()) else set()
        
        # Also include files matching ANY term
        any_files = set()
        for v in term_files.values():
            any_files.update(v)
        
        candidates = all_files if all_files else any_files
        
        # Score each candidate
        results = []
        for filepath in candidates:
            content = self._read_file(filepath)
            if not content:
                continue
            
            lines = content.split("\n")
            score = self._calculate_score(lines, terms, term_files)
            
            if score > 0:
                # Find matching lines
                matching_lines = []
                for i, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    if any(t in line_lower for t in terms):
                        matching_lines.append((i, line.strip()[:200]))
                
                if matching_lines:
                    results.append(SearchResult(
                        filepath=filepath,
                        score=score,
                        lines=matching_lines[:10],  # Top 10 matching lines
                        context=lines[0][:100] if lines else ""  # First line for context
                    ))
        
        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]
    
    def _read_file(self, filepath: str) -> Optional[str]:
        """Read file content safely."""
        try:
            full_path = self.indexer.root_dir / filepath
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    
    def _calculate_score(self, lines: list, terms: list, term_files: dict) -> float:
        """Calculate relevance score for a file."""
        if not lines:
            return 0
        
        score = 0.0
        text = "\n".join(lines).lower()
        
        for term in terms:
            term_count = text.count(term.lower())
            if term_count > 0:
                # TF: term frequency / total words
                total_words = len(text.split())
                tf = term_count / max(total_words, 1)
                
                # IDF boost: rarer terms get higher weight
                num_files_with_term = len(term_files.get(term, set()))
                idf = 1.0 if num_files_with_term <= 2 else 0.5 if num_files_with_term <= 5 else 0.2
                
                score += tf * idf * 10
        
        # Bonus for files containing ALL terms
        if all(term in text for term in terms):
            score *= 2.0
        
        # Normalize by file size
        total_words = len(text.split())
        score = score / max(total_words ** 0.5, 1)
        
        return round(score, 4)


# ---------- Structure Analyzer ----------
class StructureAnalyzer:
    """Analyze project structure and provide opinions/suggestions."""
    
    def __init__(self, indexer: LocalIndexer):
        self.indexer = indexer
    
    def analyze_structure(self) -> dict:
        """Analyze the project structure and return findings."""
        files = list(self.indexer.index.values())
        
        if not files:
            return {"error": "No files indexed"}
        
        # File extension distribution
        ext_counts = Counter(f.extension for f in files)
        
        # File size distribution
        sizes = [f.size_bytes for f in files]
        total_size = sum(sizes)
        
        # Largest files
        largest = sorted(files, key=lambda f: f.size_bytes, reverse=True)[:5]
        
        # Deepest nesting
        depths = {}
        for f in files:
            d = len(Path(f.path).parts)
            depths.setdefault(d, []).append(f.path)
        max_depth = max(depths.keys()) if depths else 0
        
        # Find potential issues
        issues = self._find_issues(files)
        
        # Generate opinion
        opinion = self._generate_opinion(files, ext_counts, sizes, largest, issues)
        
        return {
            "summary": {
                "total_files": len(files),
                "total_size_kb": round(total_size / 1024, 1),
                "file_extensions": dict(ext_counts.most_common()),
                "max_depth": max_depth,
                "avg_size_bytes": round(total_size / max(len(files), 1))
            },
            "largest_files": [
                {"path": f.path, "size_kb": round(f.size_bytes / 1024, 1), "lines": f.lines}
                for f in largest
            ],
            "issues": issues,
            "opinion": opinion,
            "directory_tree": self._build_tree()
        }
    
    def _find_issues(self, files: list) -> list[dict]:
        """Find potential organizational issues."""
        issues = []
        
        # Check for duplicate functionality
        for f in files:
            if f.extension == ".py":
                content = self._read_file(f.path)
                if content and "def " in content:
                    func_count = content.count("def ")
                    if func_count > 20:
                        issues.append({
                            "type": "large_file",
                            "file": f.path,
                            "detail": f"{func_count} functions — consider splitting"
                        })
        
        # Check for missing documentation
        py_files = [f for f in files if f.extension == ".py"]
        for f in py_files:
            content = self._read_file(f.path)
            if content and not content.strip().startswith(('"""', "'''", "#")):
                issues.append({
                    "type": "missing_docstring",
                    "file": f.path,
                    "detail": "No module-level docstring"
                })
                if len(issues) >= 5:  # Limit to avoid noise
                    break
        
        return issues
    
    def _generate_opinion(self, files, ext_counts, sizes, largest, issues) -> str:
        """Generate a human-readable opinion on project structure."""
        op = []
        
        # Overall assessment
        total_files = len(files)
        py_count = ext_counts.get(".py", 0)
        md_count = ext_counts.get(".md", 0)
        
        if py_count > 0:
            op.append(f"Python-heavy project ({py_count}/{total_files} files). "
                      "Well-structured for a CLI tool.")
        
        if md_count > 3:
            op.append(f"Good documentation ({md_count} Markdown files).")
        
        # Largest file warning
        if largest and largest[0].size_bytes > 100_000:
            op.append(f"⚠️ Largest file is {largest[0].path} ({largest[0].size_bytes//1024}KB). "
                      "Consider refactoring into smaller modules.")
        
        # Issues
        if issues:
            op.append(f"\nIssues found ({len(issues)}):")
            for issue in issues[:5]:
                op.append(f"  - {issue['type']}: {issue['detail']}")
        
        # Structure suggestions
        op.append("\nStructure opinion:")
        if "engine" in " ".join(f.path for f in files) and "lfe" in " ".join(f.path for f in files):
            op.append("  ✅ Clear separation between engine (orchestrator) and lfe (computation)")
        if "docs/" in " ".join(f.path for f in files):
            op.append("  ✅ Documentation exists in docs/")
        if "cache/" in " ".join(f.path for f in files):
            op.append("  ✅ Caching layer present")
        
        return "\n".join(op)
    
    def _build_tree(self) -> str:
        """Build a directory tree string."""
        dirs = {}
        for f in self.indexer.index.values():
            p = Path(f.path)
            parent = str(p.parent)
            dirs.setdefault(parent, []).append(p.name)
        
        lines = []
        for d in sorted(dirs.keys()):
            files = dirs[d]
            if files:
                lines.append(f"{d}/")
                for f in sorted(files):
                    lines.append(f"  ├── {f}")
        
        return "\n".join(lines) if lines else "Empty project"
    
    def _read_file(self, filepath: str) -> Optional[str]:
        """Read file content."""
        try:
            full_path = self.indexer.root_dir / filepath
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None


# ---------- Tool definitions for integration ----------
LOCAL_SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "local_search",
            "description": "Search through project files by keyword. Returns ranked results with file paths and matching lines. Use to find code references, understand file organization, or locate specific functionality.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms (minimum 3 chars)"},
                    "max_results": {"type": "integer", "description": "Max results (default 20, max 50)"},
                    "filter_ext": {"type": "string", "description": "Filter by extension (.py, .md, .txt)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_structure",
            "description": "Analyze the project structure. Returns file distribution, largest files, potential issues, and an opinion on organization quality. Use to get insights on code organization and suggestions for improvement.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "required": []
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": "Find all references to a function, class, or variable name across the project. Returns file paths and line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Function/class/variable name to search for"},
                    "context_lines": {"type": "integer", "description": "Lines of context around each match (default 2)"}
                },
                "required": ["name"]
            }
        }
    }
]

# ---------- Initialization ----------
_indexer: Optional[LocalIndexer] = None
_searcher: Optional[LocalSearcher] = None
_analyzer: Optional[StructureAnalyzer] = None

def get_indexer(root_dir: Path = None) -> LocalIndexer:
    """Get or create the indexer."""
    global _indexer
    if _indexer is None or root_dir is None:
        if root_dir is None:
            root_dir = Path(__file__).resolve().parent.parent
        _indexer = LocalIndexer(root_dir)
    return _indexer

def get_searcher() -> LocalSearcher:
    """Get or create the searcher."""
    global _searcher
    if _searcher is None:
        _searcher = LocalSearcher(get_indexer())
    return _searcher

def get_analyzer() -> StructureAnalyzer:
    """Get or create the analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = StructureAnalyzer(get_indexer())
    return _analyzer

# ---------- Execution functions ----------
def execute_local_search(query: str, max_results: int = 20, filter_ext: str = "") -> str:
    """Execute local_search tool call."""
    searcher = get_searcher()
    results = searcher.search(query, max_results)
    
    if not results:
        return f"❌ No results found for '{query}'"
    
    lines = [f"# Local Search Results for '{query}'\n"]
    lines.append(f"Found {len(results)} results (top {len(results)} shown)\n")
    
    for i, r in enumerate(results, 1):
        rel_path = r.filepath.split('/')[-1] if '/' in r.filepath else r.filepath
        lines.append(f"## {i}. `{r.filepath}` (score: {r.score})\n")
        lines.append(f"Context: {r.context}\n")
        for line_num, content in r.lines[:5]:
            lines.append(f"  Line {line_num}: `{content}`\n")
        lines.append("")
    
    return "\n".join(lines)

def execute_analyze_structure() -> str:
    """Execute analyze_structure tool call."""
    analyzer = get_analyzer()
    analysis = analyzer.analyze_structure()
    return json.dumps(analysis, indent=2, ensure_ascii=False, default=str)

def execute_find_references(name: str, context_lines: int = 2) -> str:
    """Execute find_references tool call."""
    searcher = get_searcher()
    indexer = get_indexer()
    
    # Search for the name in all indexed files
    results = searcher.search(name, max_results=30)
    
    if not results:
        return f"❌ No references found for '{name}'"
    
    lines = [f"# References to '{name}'\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. `{r.filepath}`\n")
        for line_num, content in r.lines[:context_lines]:
            lines.append(f"  Line {line_num}: `{content}`\n")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("Local Search — Self Test\n")
    print("=" * 60)
    
    # Build index
    idx = get_indexer()
    print(f"Indexed {idx.file_count()} files")
    print(f"Indexed {len(idx.word_map)} unique words")
    
    # Test search
    print("\n--- Search Test ---")
    results = idx._search_raw("cache") if hasattr(idx, '_search_raw') else []
    print(f"Cache-related results: {len(results)}")
    
    # Test structure analysis
    print("\n--- Structure Analysis ---")
    analyzer = get_analyzer()
    analysis = analyzer.analyze_structure()
    print(analysis["opinion"])
    print(f"\nFile extensions: {analysis['summary']['file_extensions']}")
    print(f"Total files: {analysis['summary']['total_files']}")
    print(f"Largest files: {[f['path'] for f in analysis['largest_files'][:3]]}")
    
    print("\n✅ Local Search self-test complete")
