"""A ticket's progress, derived from the belts every time it is asked for (ADR 0032).

Only a plan request names its ticket. A split request points at its plan and a build request at its split, so
following those links finds every request of a ticket. No ticket record is stored: the belts and run folders are
the only record, so this view cannot disagree with them.
"""
import json
from pathlib import Path

from ergon.build import Build
from ergon.plan import Plan
from ergon.split import Split


def _cost(folder: Path) -> str:
    """Minutes, tokens and attempts of the agent calls in a run folder. Cached input is shown apart: the provider
    charges it far less. A resumed call is the same attempt."""
    seconds = tokens = cached = attempts = 0
    log = folder / "calls.jsonl"
    for line in log.read_text().splitlines() if log.exists() else []:
        call = json.loads(line)
        seconds += call.get("seconds") or 0
        tokens += (call.get("input_tokens") or 0) + (call.get("output_tokens") or 0)
        cached += call.get("cache_read_tokens") or 0
        attempts += not str(call.get("label", "")).endswith("-resume")
    return (f"{seconds / 60:.0f} min, {tokens / 1000:.0f}k tokens ({cached / 1000:.0f}k cached), "
            f"{attempts} attempt{'s' * (attempts != 1)}")


def _reason(belt, rid: str) -> str:
    """Why a request was rejected, short: a stop's question when there is one, else the first line."""
    path = belt.run_dir(rid) / "rejected.txt"
    if not path.exists():
        return "no reason recorded"
    lines = path.read_text().strip().splitlines()
    line = next((l for l in lines if l.startswith("Question: ")), lines[0])
    for prefix in ("Question: ", "stopped: ", "failed: "):
        line = line.removeprefix(prefix)
    return line if len(line) <= 200 else line[:199] + "…"


class Tickets:
    def __init__(self, project: Path):
        self.plan, self.split, self.build = Plan(project), Split(project), Build(project)

    def ids(self) -> list[str]:
        return list(dict.fromkeys(r.get("ticket") for _, _, r in self.plan.belt.requests() if r.get("ticket")))

    def _chain(self, ticket: str):
        """The ticket's plans, oldest first, each with its splits and each split with its builds."""
        plans = [(rid, s) for rid, s, r in self.plan.belt.requests() if r.get("ticket") == ticket]
        splits, builds = self.split.belt.requests(), self.build.belt.requests()
        return [(pid, ps, [(sid, ss, [(bid, bs) for bid, bs, b in builds if b.get("split") == sid])
                           for sid, ss, s in splits if s.get("plan") == pid]) for pid, ps in plans]

    def status(self, ticket: str) -> str:
        chain = self._chain(ticket)
        if not chain:
            raise ValueError(f"no plan request names ticket {ticket}")
        pid, ps, splits = chain[-1]   # the newest plan replaces the ones before it (ADR 0021)
        if ps != "done":
            return {"inbox": "planning", "working": "planning", "waiting": "waiting for your answers",
                    "review": "waiting for your approval", "rejected": "plan rejected"}[ps]
        if not splits:
            return "plan approved, nothing split yet"
        sid, ss, builds = splits[-1]
        if ss == "rejected":
            return "split stopped: " + _reason(self.split.belt, sid)
        if ss != "done":
            return "splitting"
        tasks, built = self._tasks(sid, builds)
        if builds and builds[-1][1] == "rejected":
            return f"build failed after {len(built)} of {len(tasks)} tasks: " + _reason(self.build.belt, builds[-1][0])
        if builds and builds[-1][1] == "done":
            return f"done, {len(tasks)} tasks"
        return f"building, {len(built)} of {len(tasks)} tasks done"

    def _tasks(self, sid: str, builds: list) -> tuple[list, dict]:
        tasks = json.loads((self.split.belt.run_dir(sid) / "tasks.json").read_text())["tasks"]
        built = {}
        if builds:
            path = self.build.belt.run_dir(builds[-1][0]) / "built.json"
            built = {b["task"]: b for b in json.loads(path.read_text())} if path.exists() else {}
        return tasks, built

    def show(self, ticket: str) -> str:
        lines = [f"{ticket} · {self.status(ticket)}"]
        chain = self._chain(ticket)
        for n, (pid, ps, splits) in enumerate(chain, 1):
            rounds = len(list(self.plan.belt.run_dir(pid).glob("round-*.json")))
            state = "replaced" if n < len(chain) and ps == "rejected" else ps
            lines.append(f"Plan {n} ({pid}): {state}, {rounds} round{'s' * (rounds != 1)}")
            for sid, ss, builds in splits:
                lines.append(f"  Split ({sid}): {ss}" + (": " + _reason(self.split.belt, sid) if ss == "rejected" else ""))
                if ss != "done":
                    continue
                tasks, built = self._tasks(sid, builds)
                bdir = self.build.belt.run_dir(builds[-1][0]) if builds else None
                current = next((t["id"] for t in tasks if t["id"] not in built), None)   # tasks run in order
                for i, task in enumerate(tasks, 1):
                    folder = bdir / f"{i:02d}-{task['id']}" if bdir else None
                    if task["id"] in built:
                        state = built[task["id"]]["outcome"]
                    elif task["id"] == current and folder and folder.exists():
                        state = {"rejected": "failed", "working": "building"}.get(builds[-1][1], "waiting")
                    else:
                        state = "waiting"
                    cost = ", " + _cost(folder) if folder and folder.exists() else ""
                    lines.append(f"  - Task {i} {task['id']}: {state}{cost}")
        return "\n".join(lines)
