"""The Intake node. Input: requests on its belt. Output: approved wiki changes, or health reports.

Code does every step with one right answer; the wiki-maintainer only drafts and classifies (ADR 0007).
"""
import json

from ergon import agent, profiles
from ergon.node import Node
from ergon.wiki import today


class Intake(Node):
    name, profile, types = "intake", "wiki-maintainer", ("ingest", "health-check")

    def handle(self, rid: str, request: dict) -> str:
        return self._ingest(rid, request) if request["type"] == "ingest" else self._health_check(rid, request)

    def _ingest(self, rid: str, request: dict) -> str:
        path = (self.project / request["source"]).resolve()
        if self.project not in path.parents or not path.is_file():
            raise ValueError(f"source {request['source']!r} is not a file inside the project")
        text = path.read_bytes().decode("utf-8", "replace")
        run_dir = self.belt.run_dir(rid)
        agent.scope(run_dir, self.wiki.pages_dir)
        proposal = agent.ask(self.profile, self._context("wiki-maintenance.md", request, (request["source"], text)),
                             self.contracts / "proposal.json", run_dir, "proposal", self.wiki.proposal_problems)
        (run_dir / "meta.json").write_text(json.dumps({"wiki_fingerprint": self.wiki.fingerprint()}, indent=2) + "\n")
        self.belt.move(rid, "working", "review")
        return f"proposal waits for approval: {proposal['summary']}"

    def _health_check(self, rid: str, request: dict) -> str:
        run_dir = self.belt.run_dir(rid)
        mechanical = self.wiki.mechanical_findings()
        known = set(self.wiki.pages())
        semantic = []
        if len(known) > 1:
            agent.scope(run_dir, self.wiki.pages_dir)
            prompt = self._context("health-check.md", request, None)
            check = lambda r: [f"findings[{i}]: unknown page {f['page']!r}" for i, f in enumerate(r["findings"])
                               if f["page"] not in known or f.get("other_page", f["page"]) not in known]
            semantic = agent.ask(self.profile, prompt, self.contracts / "health-report.json", run_dir, "health-report", check)["findings"]
        report = {"date": today(), "mechanical": mechanical, "semantic": semantic}
        (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        self.belt.move(rid, "working", "done")
        return f"health report: {len(mechanical)} mechanical, {len(semantic)} semantic findings"

    def _context(self, skill: str, request: dict, source) -> str:
        """Everything the agent is given. The rest it reads through the wiki tool, and the log records it."""
        conv = self.wiki.conventions
        parts = [(profiles.SKILLS / skill).read_text().strip(), "# Wiki conventions",
                 f"Allowed tags: {', '.join(conv['tags']) or 'any'}. Page limit: {conv['max_page_lines']} lines.",
                 conv["notes"] or "", "# Wiki index", self.wiki.index_text(), "# Request", json.dumps(request, indent=2)]
        if source:
            label, text = source
            parts += [f"# Source: {label}", text]  # whole, never cut: a source too big for the model fails the run
        return "\n\n".join(p for p in parts if p) + "\n"

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
        commit = self.wiki.apply(proposal, rid)
        self.belt.move(rid, "review", "done")
        return f"applied: {proposal['summary']}" + (f" (commit {commit})" if commit else "")


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
