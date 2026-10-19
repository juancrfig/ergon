"""A node's belt: one JSON file per request, moved between state folders.

inbox -> working -> review (waits for the human's approval) -> done, or -> rejected with a reason.
working -> waiting (waits for the human's answers) -> inbox, for nodes that ask questions.
A rename on one disk is atomic, so two runs can never claim the same request.
Every move is appended to events.jsonl: the source of every metric.
"""
import json
import os
import re
import secrets
import time
from pathlib import Path

STATES = ("inbox", "working", "waiting", "review", "done", "rejected")
PENDING = ("waiting", "review")  # states that wait for the human


class Belt:
    def __init__(self, root: Path):
        self.root = Path(root)
        for state in (*STATES, "runs", ".tmp"):
            (self.root / state).mkdir(parents=True, exist_ok=True)

    def file(self, state: str, rid: str) -> Path:
        return self.root / state / f"{rid}.json"

    def run_dir(self, rid: str) -> Path:
        path = self.root / "runs" / rid
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ids(self, state: str) -> list[str]:
        return sorted(p.stem for p in (self.root / state).glob("*.json"))

    def state_of(self, rid: str) -> str | None:
        return next((s for s in STATES if self.file(s, rid).exists()), None)

    def read(self, rid: str) -> dict:
        state = self.state_of(rid)
        if not state:
            raise KeyError(f"no request {rid}")
        return json.loads(self.file(state, rid).read_text())

    def put(self, request: dict) -> str:
        sender = re.sub(r"[^a-z0-9-]", "-", str(request.get("from", "unknown")).lower())[:40]
        rid = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{sender}-{secrets.token_hex(2)}"
        tmp = self.root / ".tmp" / f"{rid}.json"
        tmp.write_text(json.dumps(request, indent=2) + "\n")
        os.rename(tmp, self.file("inbox", rid))
        self._event(rid, None, "inbox")
        return rid

    def move(self, rid: str, src: str, dst: str) -> None:
        os.rename(self.file(src, rid), self.file(dst, rid))
        self._event(rid, src, dst)

    def _event(self, rid: str, src: str | None, dst: str) -> None:
        event = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "id": rid, "from": src, "to": dst}
        with (self.root / "events.jsonl").open("a") as log:
            log.write(json.dumps(event) + "\n")

    def reject(self, rid: str, src: str, reason: str) -> None:
        (self.run_dir(rid) / "rejected.txt").write_text(reason.rstrip() + "\n")
        self.move(rid, src, "rejected")
