"""What every node shares: its belt, its contracts, request checks, replies and rejection."""
import json
from pathlib import Path

from ergon import schema
from ergon.belt import Belt
from ergon.wiki import Wiki

NODES = Path(__file__).resolve().parent.parent / "nodes"


class Node:
    name = ""      # folder under nodes/ and under <project>/.ergon/
    profile = ""   # Hermes profile of the node's agent
    types = ()     # request types this node accepts; each has nodes/<name>/contracts/request.<type>.json

    def __init__(self, project: Path):
        self.project = Path(project).resolve()
        self.wiki = Wiki(self.project)
        self.belt = Belt(self.project / ".ergon" / self.name)
        self.contracts = NODES / self.name / "contracts"

    def request_problems(self, request) -> list[str]:
        if not isinstance(request, dict) or request.get("type") not in self.types:
            return [f"$.type: must be one of {list(self.types)}"]
        return schema.errors(request, schema.load(self.contracts / f"request.{request['type']}.json"))

    def submit(self, request: dict) -> str:
        problems = self.request_problems(request)
        if problems:
            raise ValueError("request rejected:\n" + "\n".join(problems))
        return self.belt.put(request)

    def reject(self, rid: str, reason: str) -> None:
        state = self.belt.state_of(rid)
        if state not in ("inbox", "waiting", "review"):
            raise ValueError(f"{rid} is {state}; only requests in inbox, waiting or review can be rejected")
        self.finish_rejected(rid, self.belt.read(rid), state, f"rejected by the human: {reason}")

    def finish_rejected(self, rid, request, state, reason) -> None:
        self.belt.reject(rid, state, reason)
        self.reply(request, rid, "rejected", reason)

    def reply(self, request, rid, status, summary, **extra) -> None:
        target = request.get("reply_to") if isinstance(request, dict) else None
        if not target:
            return
        folder = (self.project / target).resolve()
        if self.project in folder.parents and folder.is_dir():
            result = {"request_id": rid, "node": self.name, "status": status, "summary": summary, **extra}
            (folder / f"{rid}.result.json").write_text(json.dumps(result, indent=2) + "\n")

    def status(self) -> str:
        from ergon.belt import STATES
        return f"{self.name}: " + " · ".join(f"{s} {len(self.belt.ids(s))}" for s in STATES)

    def header(self, rid: str) -> str:
        request = self.belt.read(rid)
        lines = [f"{rid} · {self.name} · {request['type']} from {request['from']} · {self.belt.state_of(rid)}"]
        rejected = self.belt.run_dir(rid) / "rejected.txt"
        if rejected.exists():
            lines.append("Rejected: " + rejected.read_text())
        return "\n".join(lines)
