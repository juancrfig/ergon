"""What every node shares: its belt, its contracts, request checks, the run loop, hand-offs and rejection."""
from pathlib import Path

from ergon import agent, profiles, schema
from ergon.belt import STATES, Belt
from ergon.wiki import Wiki

NODES = Path(__file__).resolve().parent.parent / "nodes"


def repos(project: Path) -> dict[str, Path]:
    """The project's repos: every git clone directly inside the project folder (ADR 0025)."""
    return {p.name: p for p in sorted(Path(project).iterdir()) if p.is_dir() and (p / ".git").exists()}


class Node:
    name = ""      # folder under nodes/ and under <project>/.ergon/
    profile = ""   # Hermes profile of the node's agent; run() refuses to start without it (ADR 0010)
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

    def run(self, log=print) -> None:
        """Take every request in the inbox through handle(); a malformed or failed one is rejected with its reason."""
        profiles.require(self.profile)
        for rid in self.belt.ids("inbox"):
            self.belt.move(rid, "inbox", "working")
            try:
                request = self.belt.read(rid)
            except ValueError as exc:   # the file is not JSON
                self.belt.reject(rid, "working", f"malformed request: not valid JSON ({exc})")
                log(f"{rid}: rejected (malformed)")
                continue
            problems = self.request_problems(request)
            if problems:
                self.belt.reject(rid, "working", "malformed request:\n" + "\n".join(problems))
                log(f"{rid}: rejected (malformed)")
                continue
            try:
                outcome = self.handle(rid, request)
            except Exception as exc:   # whatever fails, the request leaves "working" with its reason
                if self.belt.state_of(rid) == "working":
                    self.belt.reject(rid, "working", f"failed: {type(exc).__name__}: {exc}")
                outcome = f"rejected: {exc}"
            log(f"{rid}: {outcome}")

    def handle(self, rid: str, request: dict) -> str:
        raise NotImplementedError

    def submit(self, request: dict) -> str:
        problems = self.request_problems(request)
        if problems:
            raise ValueError("request rejected:\n" + "\n".join(problems))
        return self.belt.put(request)

    def hand_off(self, node: str, request: dict) -> str:
        """Put a request on the next node's belt. Code builds it; that node checks it when it runs (ADR 0026)."""
        return Belt(self.project / ".ergon" / node).put(request)

    def reject(self, rid: str, reason: str) -> None:
        state = self.belt.state_of(rid)
        if state not in ("inbox", "waiting", "review"):
            raise ValueError(f"{rid} is {state}; only requests in inbox, waiting or review can be rejected")
        self.belt.reject(rid, state, f"rejected by the human: {reason}")

    def status(self) -> str:
        return f"{self.name}: " + " · ".join(f"{s} {len(self.belt.ids(s))}" for s in STATES)

    def header(self, rid: str) -> str:
        request = self.belt.read(rid)
        lines = [f"{rid} · {self.name} · {request['type']} from {request['from']} · {self.belt.state_of(rid)}"]
        rejected = self.belt.run_dir(rid) / "rejected.txt"
        if rejected.exists():
            lines.append("Rejected: " + rejected.read_text())
        return "\n".join(lines)
