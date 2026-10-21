"""The builder's proof that a task is done, checked by code against its own session log (ADR 0033).

Each source clone has a verification skill in VERIFY: SKILL.md (how to launch, drive, inspect and clean up the app)
and features/README.md, the feature map's index; one file per feature sits next to it, opened by the builder. For every criterion it covers, the builder answers with the commands it ran and the
lines their output showed. Code finds each one in the session logs of the task's calls: the same command, run after
the builder's last file edit, whose recorded output holds every line. So a proof the builder never ran, or ran
before a later edit, fails like any other check, and nothing is run again. A proof that held only because of a file
outside the change is not caught; replaying in a clean copy would catch it, at the cost of running everything twice.
"""
import json
from pathlib import Path

VERIFY = ".agents/skills/verify"
FILES = ("SKILL.md", "features/README.md")   # required, and put in the builder's prompt
MAP = "features/"   # any task may change the map
# The file tools that change files, in Hermes and agy. An edit made through a shell command is not seen.
EDITS = {"patch", "write_file", "edit_file", "write_to_file", "replace_file_content", "multi_replace_file_content",
         "sed_file", "notebook_edit"}
SHELLS = {"terminal", "run_command"}


def missing(roots: dict) -> list[str]:
    """Verification files absent from the given source clones, as <repo>/<path>."""
    return [f"{name}/{VERIFY}/{f}" for name, root in roots.items() for f in FILES if not (root / VERIFY / f).exists()]


def skill_text(name: str, root: Path) -> str:
    return "\n\n".join(f"# {name}/{VERIFY}/{f}\n\n{(root / VERIFY / f).read_text().strip()}" for f in FILES)


def _same(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def _hermes(session: dict) -> list:
    """(tool, command, output) per tool call of one Hermes session export, in order."""
    calls, results = [], {}
    for m in session.get("messages") or []:
        if m.get("role") == "tool":
            results[m.get("tool_call_id")] = m.get("content") or ""
        for c in m.get("tool_calls") or []:
            fn = c.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            calls.append((c.get("id"), fn.get("name"), args.get("command", "")))
    out = []
    for cid, name, command in calls:
        text = results.get(cid, "")
        try:   # the terminal tool answers {"output", "exit_code", "error"}
            doc = json.loads(text)
            if isinstance(doc, dict):
                text = f"{doc.get('output', '')}\n{doc.get('error') or ''}"
        except ValueError:
            pass
        out.append((name, command, text))
    return out


def _agy(step: dict) -> tuple:
    info = step.get("tool_info") or {}
    return step.get("tool_name"), (info.get("parameters") or {}).get("CommandLine", ""), info.get("output") or ""


def calls(task_dir: Path) -> list:
    """Every tool call of the task's agent calls, oldest call first: (tool, command, output)."""
    out = []
    for f in sorted(task_dir.glob("*.session.jsonl"), key=lambda p: p.stat().st_mtime):
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            doc = json.loads(line)
            step = doc.get("step_update")
            if isinstance(step, dict):
                if step.get("step_type") == "tool" and step.get("state") == "DONE":
                    out.append(_agy(step))
            elif "messages" in doc:
                out += _hermes(doc)
    return [(name, command, output.replace("\r\n", "\n")) for name, command, output in out]


def check(reports: list, task_dir: Path) -> tuple[list[str], list[dict]]:
    """Every proof step, found in the session logs after the last edit. Returns the problems and the record."""
    log = calls(task_dir)
    last_edit = max((i for i, (name, _, _) in enumerate(log) if name in EDITS), default=-1)
    after = [(c, o) for name, c, o in log[last_edit + 1:] if name in SHELLS]
    before = [c for name, c, _ in log[:last_edit + 1] if name in SHELLS]
    problems, record = [], []
    for report in reports:
        for n, step in enumerate(report["proof"], 1):
            where = f"proof of {report['criterion']}, step {n} (`{step['run']}`)"
            runs = [o for c, o in after if _same(c, step["run"])]
            found = next((o for o in reversed(runs) if all(l in o for l in step["contains"])), None)
            record.append({"criterion": report["criterion"], "step": n, **step, "found": found is not None})
            if found is not None:
                continue
            if runs:
                absent = [l for l in step["contains"] if l not in runs[-1]]
                problems.append(f"{where}: its last run printed none of " + "; ".join(repr(l) for l in absent)
                                + ". Output, end:\n" + runs[-1][-800:])
            elif any(_same(c, step["run"]) for c in before):
                problems.append(f"{where}: ran before your last edit; run it again so it proves the final code")
            else:
                problems.append(f"{where}: not in your session log; a proof is a command you ran, as you ran it")
    return problems, record
