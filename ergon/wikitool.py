"""The only tools a node agent has: read-only access to one project's wiki and to one request's source (ADR 0016).

Hermes starts this as an MCP server over stdio, one process per agent run. The run folder comes as the only argument
(the profile passes ${ERGON_RUN}, which the runner sets). The scope is fixed by code in <run>/tool-scope.json:
  {"pages": "<abs path to wiki/pages>", "source": "<abs path to the source text>" or null}
  plus "log", the call log's file name in <run>. Every call is appended to it, so code can check what the agent read
  before accepting its answer.

Standalone on purpose: Hermes runs this file directly, so it imports nothing from ergon. Standard library only.
"""
import json
import re
import sys
import time
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CHUNK = 20_000      # characters per read_source call
MAX_HITS = 20       # pages returned by one search

TOOLS = [
    {"name": "read_page", "description": "Read one wiki page, front matter included, by its slug (the name in [[slug]]).",
     "inputSchema": {"type": "object", "properties": {"slug": {"type": "string"}}, "required": ["slug"]}},
    {"name": "search_wiki", "description": "Find the wiki pages whose title or text contain a phrase (case-insensitive). "
                                           "Returns each page's slug and up to 3 matching lines.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "read_source", "description": f"Read the request's source, {CHUNK} characters at a time, from a character "
                                           "offset (start at 0). Each answer says where the next part starts.",
     "inputSchema": {"type": "object", "properties": {"offset": {"type": "integer", "minimum": 0}}}},
]


class Scope:
    def __init__(self, run: Path):
        self.run = run
        scope = json.loads((run / "tool-scope.json").read_text())
        self.pages = Path(scope["pages"])
        self.source = Path(scope["source"]) if scope.get("source") else None
        self.log_path = run / scope.get("log", "tool-calls.jsonl")

    def log(self, entry: dict) -> None:
        with self.log_path.open("a") as f:
            f.write(json.dumps({"at": time.time(), **entry}) + "\n")

    def read_page(self, slug: str) -> str:
        path = self.pages / f"{slug}.md"
        if not SLUG.match(slug or "") or not path.is_file():
            self.log({"tool": "read_page", "slug": slug, "found": False})
            return f"No wiki page {slug!r}. Slugs are the names in the index, like [[refund-policy]]."
        self.log({"tool": "read_page", "slug": slug, "found": True})
        return path.read_text()

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

    def read_source(self, offset: int) -> str:
        if self.source is None:
            return "This request has no source."
        text = self.source.read_text()
        start = max(0, min(int(offset or 0), len(text)))
        end = min(start + CHUNK, len(text))
        self.log({"tool": "read_source", "start": start, "end": end, "total": len(text)})
        tail = f"next offset: {end}" if end < len(text) else "end of source"
        return f"[characters {start}-{end} of {len(text)}; {tail}]\n\n{text[start:end]}"

    def call(self, name: str, args: dict) -> str:
        if name == "read_page":
            return self.read_page(args.get("slug", ""))
        if name == "search_wiki":
            return self.search_wiki(args.get("query", ""))
        if name == "read_source":
            return self.read_source(args.get("offset", 0))
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
            result = {"tools": TOOLS}
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
