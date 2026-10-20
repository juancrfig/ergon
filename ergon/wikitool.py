"""Ergon's own tools for node agents: read-only access to one project's wiki (ADR 0016), and to its repos when the
node reads code (ADR 0025). Every agent has them; Build's agent also has Hermes' terminal and file tools (ADR 0023).

Hermes starts this as an MCP server over stdio, one process per agent run. The run folder comes as the only argument
(the profile passes ${ERGON_RUN}, which the runner sets). The scope is fixed by code in <run>/tool-scope.json:
  {"pages": "<abs path to wiki/pages>", "log": "<call log file name in run>", "repos": {"<name>": "<abs path>"}}
"repos" is optional; without it the code tools are not offered.
Every call is appended to the log, so the run records what the agent read.

Standalone on purpose: Hermes runs this file directly, so it imports nothing from ergon. Standard library only.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_HITS = 20       # pages or files returned by one search
MAX_FILE = 200_000  # bytes of one file read_files returns

TOOLS = [
    {"name": "read_pages", "description": "Read wiki pages, front matter included, by their slugs (the names in "
                                          "[[slug]]). Ask for every page you need in one call.",
     "inputSchema": {"type": "object", "properties": {"slugs": {"type": "array", "items": {"type": "string"}}},
                     "required": ["slugs"]}},
    {"name": "search_wiki", "description": "Find the wiki pages whose title or text contain a phrase (case-insensitive). "
                                           "Returns each page's slug and up to 3 matching lines.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]

CODE_TOOLS = [
    {"name": "read_files", "description": "Read repo files by path, written <repo>/<path inside the repo>, as the repo "
                                          "listings show them. Ask for every file you need in one call.",
     "inputSchema": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
                     "required": ["paths"]}},
    {"name": "search_code", "description": "Find the repo files that contain a phrase (case-insensitive). Returns each "
                                           "file's path and up to 3 matching lines with their line numbers.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]


def repo_files(root: Path) -> list[str]:
    """The files of a repo that git knows or would add: tracked, plus untracked files not ignored."""
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
                            capture_output=True, text=True)
    return sorted(set(result.stdout.splitlines())) if result.returncode == 0 else []


class Scope:
    def __init__(self, run: Path):
        scope = json.loads((run / "tool-scope.json").read_text())
        self.pages = Path(scope["pages"])
        self.log_path = run / scope.get("log", "tool-calls.jsonl")
        self.repos = {name: Path(path) for name, path in (scope.get("repos") or {}).items()}

    def tools(self) -> list:
        return TOOLS + (CODE_TOOLS if self.repos else [])

    def _file(self, path: str) -> Path | None:
        """The file a <repo>/<path> names, or None if it is outside the repo, ignored, or not a file."""
        name, _, rel = (path or "").partition("/")
        root = self.repos.get(name)
        if not root or not rel:
            return None
        target = (root / rel).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file() or rel not in repo_files(root):
            return None
        return target

    def read_files(self, paths: list) -> str:
        found, out = [], []
        for path in dict.fromkeys(p for p in paths if isinstance(p, str)):
            target = self._file(path)
            if target is None:
                out.append(f"# No file {path}. Paths are <repo>/<path>, as the repo listings show them.")
                continue
            data = target.read_bytes()
            if b"\0" in data[:8000]:
                out.append(f"# File {path} is binary; not shown.")
                continue
            found.append(path)
            text = data[:MAX_FILE].decode("utf-8", "replace")
            cut = f"\n(cut at {MAX_FILE} bytes of {len(data)})" if len(data) > MAX_FILE else ""
            out.append(f"# File {path}\n\n{text}{cut}")
        self.log({"tool": "read_files", "asked": list(paths), "found": found})
        return "\n\n".join(out) or "Ask for at least one path."

    def search_code(self, query: str) -> str:
        needle = (query or "").strip().lower()
        hits = []
        for name, root in self.repos.items() if needle else []:
            for rel in repo_files(root):
                target = root / rel
                try:
                    data = target.read_bytes()
                except OSError:
                    continue
                if b"\0" in data[:8000] or len(data) > MAX_FILE:
                    continue
                lines = [(n, line.strip()) for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1)
                         if needle in line.lower()]
                if lines:
                    hits.append(f"{name}/{rel}\n" + "\n".join(f"  {n}: {line[:200]}" for n, line in lines[:3]))
        self.log({"tool": "search_code", "query": query, "hits": len(hits)})
        if not hits:
            return f"No file contains {query!r}."
        more = f"\n\n({len(hits) - MAX_HITS} more files match; search a narrower phrase)" if len(hits) > MAX_HITS else ""
        return "\n\n".join(hits[:MAX_HITS]) + more

    def log(self, entry: dict) -> None:
        with self.log_path.open("a") as f:
            f.write(json.dumps({"at": time.time(), **entry}) + "\n")

    def read_pages(self, slugs: list) -> str:
        found, out = [], []
        for slug in dict.fromkeys(s for s in slugs if isinstance(s, str)):
            path = self.pages / f"{slug}.md"
            if SLUG.match(slug) and path.is_file():
                found.append(slug)
                out.append(f"# Page [[{slug}]]\n\n{path.read_text()}")
            else:
                out.append(f"# No wiki page [[{slug}]]. Slugs are the names in the index.")
        self.log({"tool": "read_pages", "asked": list(slugs), "found": found})
        return "\n\n".join(out) or "Ask for at least one slug."

    def search_wiki(self, query: str) -> str:
        needle = (query or "").strip().lower()
        hits = []
        for path in sorted(self.pages.glob("*.md")) if needle else []:
            lines = [line.strip() for line in path.read_text().splitlines() if needle in line.lower()]
            if lines:
                hits.append(f"[[{path.stem}]]\n" + "\n".join(f"  {line[:200]}" for line in lines[:3]))
        self.log({"tool": "search_wiki", "query": query, "hits": len(hits)})
        if not hits:
            return f"No page contains {query!r}."
        more = f"\n\n({len(hits) - MAX_HITS} more pages match; search a narrower phrase)" if len(hits) > MAX_HITS else ""
        return "\n\n".join(hits[:MAX_HITS]) + more

    def call(self, name: str, args: dict) -> str:
        if name == "read_pages":
            return self.read_pages(args.get("slugs") or [])
        if name == "search_wiki":
            return self.search_wiki(args.get("query", ""))
        if name == "read_files" and self.repos:
            return self.read_files(args.get("paths") or [])
        if name == "search_code" and self.repos:
            return self.search_code(args.get("query", ""))
        raise KeyError(name)


def serve(scope: Scope) -> None:
    def send(message):
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if "id" not in msg:
            continue  # notifications need no answer
        mid, method, params = msg["id"], msg.get("method"), msg.get("params") or {}
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "ergon", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": scope.tools()}
        elif method == "tools/call":
            try:
                text, error = scope.call(params.get("name", ""), params.get("arguments") or {}), False
            except KeyError:
                text, error = f"unknown tool {params.get('name')!r}", True
            result = {"content": [{"type": "text", "text": text}], "isError": error}
        elif method == "ping":
            result = {}
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})
            continue
        send({"jsonrpc": "2.0", "id": mid, "result": result})


if __name__ == "__main__":
    serve(Scope(Path(sys.argv[1]).resolve()))
