"""What a trial's records show: time and effort per node, contracts re-checked, and claims compared with actions.

Everything here reads files a trial left; nothing calls an agent. Sources:
- calls.jsonl in every run folder: each agent call's time, tokens and verdict (ergon/agent.py).
- events.jsonl on every belt: each request's moves, so time working and time waiting for the human.
- the saved requests and answers, re-checked against their contracts.
- the wiki tool's call logs and Hermes' session exports: what each agent really read and ran.
"""
import calendar
import json
import re
import statistics
import time
from pathlib import Path

from ergon import schema
from ergon.node import NODES as CONTRACTS

NODES = ("intake", "plan", "split", "build")
TOKENS = ("input_tokens", "output_tokens", "cache_read_tokens", "reasoning_tokens")
# answer files each node saves, and the contract each must still satisfy
ANSWERS = {"intake": [(r"proposal\.json", "proposal.json"), (r"health-report\.json", "health-report.json")],
           "plan": [(r"round-\d+\.json", "round.json")],   # answers-N.json is Plan's record, not the contract's
           "split": [(r"tasks\.json", "tasks.json")],
           "build": [(r"result\.json", "result.json")]}


def trial(project: Path, client_dir: Path, spec: dict, start: str = "intake") -> dict:
    """A trial from a snapshot counts only the nodes it ran: the earlier ones' records came with the copy."""
    ergon = project / ".ergon"
    nodes = {n: _calls(ergon / n / "runs") for n in NODES[NODES.index(start):]}
    nodes["client"] = _calls(client_dir)
    for n in NODES[NODES.index(start):]:
        nodes[n].update(_belt_time(ergon / n / "events.jsonl"))
    return {"nodes": nodes, "contract_problems": _contracts(ergon), "behavior": _behavior(ergon, spec)}


# --- time and effort --------------------------------------------------------------------------------------------


def _calls(folder: Path) -> dict:
    rows = [json.loads(line) for f in sorted(folder.rglob("calls.jsonl")) for line in f.read_text().splitlines()
            if line.strip()] if folder.exists() else []
    out: dict = {"calls": len(rows), "agent_seconds": round(sum(r.get("seconds") or 0 for r in rows), 1)}
    for outcome in ("accepted", "rejected", "failed"):
        out[outcome] = sum(r["outcome"] == outcome for r in rows)
    out["tokens"] = {k: sum(r.get(k) or 0 for r in rows) for k in TOKENS}
    out["reasons"] = [f"{r['label']}: {reason}" for r in rows if r["outcome"] != "accepted" for reason in r["reasons"]]
    return out


def _belt_time(events: Path) -> dict:
    """Seconds requests spent working (code and agents) and waiting for the human (here the client and the automatic
    approvals), from the belt's moves. Events are to the second."""
    out = {"working_seconds": 0, "waiting_seconds": 0}
    if not events.exists():
        return out
    since = {}
    for line in events.read_text().splitlines():
        e = json.loads(line)
        t = _seconds(e["time"])
        if e["id"] in since and e["from"] in ("working", "waiting", "review"):
            key = "working_seconds" if e["from"] == "working" else "waiting_seconds"
            out[key] += t - since[e["id"]]
        since[e["id"]] = t
    return out


def _seconds(stamp: str) -> int:
    return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))


# --- contracts --------------------------------------------------------------------------------------------------


def _contracts(ergon: Path) -> list:
    """Every saved request and answer, checked again against its contract: a file code accepted and later changed,
    or a contract that changed under a saved answer, shows here."""
    out = []
    for node in NODES:
        contracts = CONTRACTS / node / "contracts"
        for state in ("inbox", "working", "waiting", "review", "done", "rejected"):
            for f in sorted((ergon / node / state).glob("*.json")):
                doc = json.loads(f.read_text())
                path = contracts / f"request.{doc.get('type')}.json"
                errs = schema.errors(doc, schema.load(path)) if path.exists() else [f"no contract for {doc.get('type')}"]
                out += [f"{node}/{f.stem}: {e}" for e in errs]
        for f in sorted((ergon / node / "runs").rglob("*.json")):
            for pattern, contract in ANSWERS[node]:
                if re.fullmatch(pattern, f.name):
                    errs = schema.errors(json.loads(f.read_text()), schema.load(contracts / contract))
                    out += [f"{node}/{f.relative_to(ergon / node / 'runs')}: {e}" for e in errs]
    return out


# --- claims against actions -------------------------------------------------------------------------------------


def _behavior(ergon: Path, spec: dict) -> dict:
    out = {}
    items = [i for f in sorted((ergon / "intake" / "runs").rglob("proposal.json"))
             for i in json.loads(f.read_text())["items"]]
    flagged = [i["text"] for i in items if i["kind"] == "contradiction" or i["status"] == "contradiction"]
    caught = {c["id"]: any(_matches(text, c["match"]) for text in flagged) for c in spec.get("contradictions", [])}
    out["contradictions"] = {"planted": caught, "flagged": len(flagged),
                             "unplanted": [t for t in flagged
                                           if not any(_matches(t, c["match"]) for c in spec.get("contradictions", []))]}
    # Plan: every page a story cites must be a page the planner read.
    read = set()
    for f in (ergon / "plan" / "runs").rglob("tool-calls-round-*.jsonl"):
        for line in f.read_text().splitlines():
            entry = json.loads(line)
            if entry.get("tool") == "read_pages":
                read.update(entry.get("found") or entry.get("asked") or [])
    cited = {p for f in (ergon / "plan" / "runs").rglob("stories.json") for s in json.loads(f.read_text())["stories"]
             for p in s["sources"]}
    out["plan_cited_unread"] = sorted(cited - read)
    # Every call: the tools it used, from its session; a builder task that ran no command checked nothing.
    tools = {}
    for f in sorted(ergon.rglob("*.session.jsonl")):
        tools[str(f.relative_to(ergon)).removesuffix(".session.jsonl")] = _tool_names(f)
    out["tools"] = tools
    out["build_tasks_without_commands"] = sorted(
        str(f.parent.relative_to(ergon / "build" / "runs")) for f in (ergon / "build" / "runs").rglob("result.json")
        if not any(n == "terminal" for label, names in tools.items()
                   if label.startswith(str(f.parent.relative_to(ergon))) for n in names))
    return out


def _matches(text: str, groups: list) -> bool:
    """A contradiction matches when the text holds a word from every group."""
    low = text.lower()
    return all(any(word in low for word in group) for group in groups)


def _tool_names(session_file: Path) -> list:
    """Every tool call in a Hermes session export or an agy step stream, in order. agy's run_command counts as
    terminal. The export's shape is Hermes', so search it loosely."""
    names = []

    def walk(node):
        if isinstance(node, dict):
            step = node.get("step_update")   # agy's stream: one DONE step per tool call
            if isinstance(step, dict) and step.get("step_type") == "tool" and step.get("state") == "DONE":
                name = step.get("tool_name") or "?"
                names.append("terminal" if name == "run_command" else name)
            for call in node.get("tool_calls") or []:
                if isinstance(call, dict):
                    names.append((call.get("function") or {}).get("name") or call.get("name") or "?")
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for line in session_file.read_text().splitlines():
        if line.strip():
            walk(json.loads(line))
    return names


# --- the report -------------------------------------------------------------------------------------------------


def report(records: list) -> str:
    lines = ["# Eval report", ""]
    for case in sorted({r["case"] for r in records}):
        mine = [r for r in records if r["case"] == case]
        passed = sum(r["passed"] for r in mine)
        lines += [f"## {case}", f"- **Trials:** {len(mine)} · passed {passed} · pass^{len(mine)} "
                                f"{'yes' if passed == len(mine) else 'no'}"]
        tags = {}
        for r in mine:
            for tag, s in r.get("tests", {}).items():
                tags.setdefault(tag, [0, 0])
                tags[tag][0] += s["passed"]
                tags[tag][1] += s["total"]
        lines.append("- **Hidden tests:** " + (" · ".join(f"{t} {p}/{n}" for t, (p, n) in tags.items()) or "none ran"))
        stops = [f"{r['stopped_at']}" for r in mine if r["stopped_at"]]
        if stops:
            lines.append("- **Stopped at:** " + ", ".join(stops))
        lines.append(f"- **Wall time:** median {statistics.median(r['seconds'] for r in mine):.0f}s")
        for node in (*NODES, "client"):
            n = [r["nodes"][node] for r in mine if node in r["nodes"]]
            if not n or not sum(x["calls"] for x in n):
                continue
            tokens = sum(x["tokens"]["input_tokens"] + x["tokens"]["output_tokens"] for x in n)
            lines.append(f"- **{node}:** {sum(x['calls'] for x in n)} calls ({sum(x['rejected'] for x in n)} rejected, "
                         f"{sum(x['failed'] for x in n)} failed) · agent {sum(x['agent_seconds'] for x in n):.0f}s"
                         + (f" · waiting {sum(x['waiting_seconds'] for x in n)}s" if node != "client" else "")
                         + f" · {tokens} tokens")
        planted = [ok for r in mine for ok in r["behavior"]["contradictions"]["planted"].values()]
        if planted:
            lines.append(f"- **Contradictions caught:** {sum(planted)}/{len(planted)}")
        unplanted = sum(len(r["behavior"]["contradictions"]["unplanted"]) for r in mine)
        if unplanted:
            lines.append(f"- **Contradictions flagged but not planted:** {unplanted}")
        problems = [p for r in mine for p in r["contract_problems"]]
        lines.append(f"- **Contract re-check:** {len(problems)} problems" + "".join(f"\n  - {p}" for p in problems[:10]))
        unread = sorted({p for r in mine for p in r["behavior"]["plan_cited_unread"]})
        if unread:
            lines.append("- **Plan cites pages it never read:** " + ", ".join(unread))
        blind = [t for r in mine for t in r["behavior"]["build_tasks_without_commands"]]
        if blind:
            lines.append(f"- **Build tasks that ran no command:** {len(blind)}")
        lines.append("- **Trials:** " + ", ".join(r["trial"] for r in mine))
        lines.append("")
    return "\n".join(lines)
