"""The Intake node. Input: requests on its belt. Output: approved wiki changes, or health reports.

Code does every step with one right answer; the wiki-maintainer only drafts and classifies (ADR 0007).
"""
import hashlib
import json
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from ergon import agent, gate
from ergon.node import Node
from ergon.wiki import today

CONTRACTS = Path(__file__).resolve().parent.parent / "nodes" / "intake" / "contracts"
PROFILE = "wiki-maintainer"
SKILLS = gate.REPO / "profiles" / PROFILE / "skills"


class Intake(Node):
    name, profile, types = "intake", PROFILE, ("ingest", "correct", "health-check")

    # --- the run loop -----------------------------------------------------------------------------------------

    def run(self, log=print) -> None:
        gate.require(PROFILE)
        for rid in self.belt.ids("inbox"):
            self.belt.move(rid, "inbox", "working")
            request = self.belt.read(rid)
            problems = self.request_problems(request)
            if problems:
                self.finish_rejected(rid, request, "working", "malformed request:\n" + "\n".join(problems))
                log(f"{rid}: rejected (malformed)")
                continue
            try:
                outcome = getattr(self, "_" + request["type"].replace("-", "_"))(rid, request)
            except (agent.AgentError, OSError, ValueError) as exc:
                self.finish_rejected(rid, request, "working", f"failed: {exc}")
                outcome = f"rejected: {exc}"
            log(f"{rid}: {outcome}")

    def _ingest(self, rid: str, request: dict) -> str:
        text, fingerprint, label = self._fetch(request["source"])
        ledger = self._ledger()
        if fingerprint in ledger:
            self.finish_rejected(rid, request, "working", f"duplicate: this source was ingested by {ledger[fingerprint]}")
            return "rejected (duplicate source)"
        return self._propose(rid, request, label, text, fingerprint, must_read=[])

    def _correct(self, rid: str, request: dict) -> str:
        if request["page"] not in self.wiki.pages():
            self.finish_rejected(rid, request, "working", f"page {request['page']!r} does not exist")
            return "rejected (unknown page)"
        evidence = request["evidence"]
        text, fingerprint, label = (evidence["text"], None, "evidence from the sender") if "text" in evidence \
            else self._fetch(evidence)
        return self._propose(rid, request, label, text, fingerprint, must_read=[request["page"]])

    def _health_check(self, rid: str, request: dict) -> str:
        run_dir = self.belt.run_dir(rid)
        mechanical = self.wiki.mechanical_findings()
        known = set(self.wiki.pages())
        semantic = []
        if len(known) > 1:
            log = agent.scope(run_dir, self.wiki.pages_dir, None)
            prompt = self._context("health-check", request, None)

            def check(r):
                out = [f"findings[{i}]: unknown page {f['page']!r}" for i, f in enumerate(r["findings"])
                       if f["page"] not in known or f.get("other_page", f["page"]) not in known]
                unread = sorted(known - agent.reads(log)[0])
                if unread:  # contradictions can sit between any two pages, so every page must be read
                    out.append(f"you did not read {len(unread)} pages; read each with read_page: "
                               + ", ".join(f"[[{s}]]" for s in unread[:30]))
                return out
            semantic = agent.ask(PROFILE, prompt, CONTRACTS / "health-report.json", run_dir, "health-report", check)["findings"]
        report = {"date": today(), "mechanical": mechanical, "semantic": semantic}
        (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        self.belt.move(rid, "working", "done")
        self.reply(request, rid, "done", f"{len(mechanical)} mechanical and {len(semantic)} semantic findings")
        return f"health report: {len(mechanical)} mechanical, {len(semantic)} semantic findings"

    # --- drafting ---------------------------------------------------------------------------------------------

    def _propose(self, rid, request, label, text, fingerprint, must_read) -> str:
        run_dir = self.belt.run_dir(rid)
        source = run_dir / "source.txt"
        source.write_text(text)
        log = agent.scope(run_dir, self.wiki.pages_dir, source)
        check = lambda r: self.wiki.proposal_problems(r) + _read_problems(r, log, set(self.wiki.pages()))
        proposal = agent.ask(PROFILE, self._context("propose", request, (label, len(text)), must_read),
                             CONTRACTS / "proposal.json", run_dir, "proposal", check)
        meta = {"wiki_fingerprint": self.wiki.fingerprint(), "source_fingerprint": fingerprint}
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        self.belt.move(rid, "working", "review")
        return f"proposal waits for approval: {proposal['summary']}"

    def _context(self, purpose: str, request: dict, source, must_read=()) -> str:
        """Everything the agent is given. The rest it reads through the wiki tool, and the log records it."""
        skill = "health-check.md" if purpose == "health-check" else "wiki-maintenance.md"
        conv = self.wiki.conventions
        parts = [(SKILLS / skill).read_text().strip(), "# Wiki conventions",
                 f"Allowed tags: {', '.join(conv['tags']) or 'any'}. Page limit: {conv['max_page_lines']} lines.",
                 conv["notes"] or "", "# Wiki index", self.wiki.index_text(), "# Request", json.dumps(request, indent=2)]
        if must_read:
            parts.append("Read these pages before anything else: " + ", ".join(f"[[{s}]]" for s in must_read) + ".")
        if source:
            label, length = source
            parts += [f"# Source: {label}", f"{length} characters. Read all of it with read_source, starting at offset 0. "
                      "Code rejects an answer given before the whole source was read."]
        return "\n\n".join(p for p in parts if p) + "\n"

    def _fetch(self, source: dict) -> tuple[str, str, str]:
        """Return (text, fingerprint, label). URLs are saved into wiki/raw/ so the source outlives the link."""
        if "url" in source:
            req = urllib.request.Request(source["url"], headers={"User-Agent": "ergon-intake"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data, html = resp.read(), "html" in resp.headers.get("Content-Type", "")
            fingerprint = hashlib.sha256(data).hexdigest()
            text = _html_text(data.decode("utf-8", "replace")) if html else data.decode("utf-8", "replace")
            raw = self.wiki.dir / "raw"
            raw.mkdir(parents=True, exist_ok=True)
            (raw / f"{today()}-{fingerprint[:8]}.txt").write_text(f"Source: {source['url']}\nFetched: {today()}\n\n{text}")
            return text, fingerprint, source["url"]
        path = (self.project / source["file"]).resolve()
        if self.project not in path.parents or not path.is_file():
            raise ValueError(f"source file {source['file']!r} is not a file inside the project")
        data = path.read_bytes()
        return data.decode("utf-8", "replace"), hashlib.sha256(data).hexdigest(), source["file"]

    # --- the human's decision ---------------------------------------------------------------------------------

    def show(self, rid: str) -> str:
        run_dir, lines = self.belt.run_dir(rid), [self.header(rid)]
        for name in ("proposal.json", "report.json"):
            if (run_dir / name).exists():
                lines.append(_describe(json.loads((run_dir / name).read_text())))
        return "\n".join(lines)

    def approve(self, rid: str) -> str:
        if self.belt.state_of(rid) != "review":
            raise ValueError(f"{rid} is not waiting for approval")
        run_dir = self.belt.run_dir(rid)
        proposal = json.loads((run_dir / "proposal.json").read_text())
        meta = json.loads((run_dir / "meta.json").read_text())
        if meta["wiki_fingerprint"] != self.wiki.fingerprint():
            raise ValueError("the wiki changed since this proposal was drafted; reject it and submit the request again")
        request = self.belt.read(rid)
        commit = self.wiki.apply(proposal, rid, request["type"])
        if meta.get("source_fingerprint"):
            ledger = self._ledger()
            ledger[meta["source_fingerprint"]] = rid
            (self.belt.root / "ledger.json").write_text(json.dumps(ledger, indent=2) + "\n")
        self.belt.move(rid, "review", "done")
        self.reply(request, rid, "done", proposal["summary"])
        return f"applied: {proposal['summary']}" + (f" (commit {commit})" if commit else "")

    def _ledger(self) -> dict:
        path = self.belt.root / "ledger.json"
        return json.loads(path.read_text()) if path.exists() else {}


def _read_problems(proposal: dict, log: Path, existing: set) -> list[str]:
    """What the agent must have read before its proposal counts: all of the source, and every existing page it
    edits or classifies the source against."""
    pages, covered, total = agent.reads(log)
    out = []
    if covered < total:
        out.append(f"you read {covered} of the source's {total} characters; read the rest with read_source")
    for i, edit in enumerate(proposal["edits"]):
        if edit["op"] in ("replace", "delete") and edit["page"] not in pages:
            out.append(f"edits[{i}]: you {edit['op']} [[{edit['page']}]] without reading it; read it with read_page")
    for i, item in enumerate(proposal["items"]):
        if item["status"] != "new" and item.get("page") in existing and item["page"] not in pages:
            out.append(f"items[{i}]: you classify against [[{item['page']}]] without reading it; read it with read_page")
    return out


def _describe(doc: dict) -> str:
    if "edits" in doc:
        out = [f"Summary: {doc['summary']}", "Edits:"]
        out += [f"  {e['op']} [[{e['page']}]]" + (f" {e['title']}" if e.get("title") else "") for e in doc["edits"]]
        out.append("Items:")
        out += [f"  [{i['status']}] {i['kind']}: {i['text']} ({i['citation']})" for i in doc["items"]]
        return "\n".join(out)
    out = ["Mechanical findings:"] + [f"  {f['page']} · {f['kind']}: {f['text']}" for f in doc["mechanical"]]
    out += ["Semantic findings:"] + [f"  {f['page']} · {f['kind']}: {f['text']}" for f in doc["semantic"]]
    return "\n".join(out)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in ("script", "style", "noscript")

    def handle_endtag(self, tag):
        self.skip -= tag in ("script", "style", "noscript") and self.skip > 0
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "section", "article"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _html_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    lines = (line.strip() for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)
