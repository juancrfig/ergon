"""Runs a node's agent: one Hermes profile, a context assembled by code, a JSON answer checked by code.

The agent gets no skills, memory, SOUL or AGENTS.md from Hermes (--ignore-rules) and only the toolsets its node
names: ergon's read-only tool (ADR 0016), scoped by code per run, plus Hermes' terminal and file tools for Build
(ADR 0023). The run folder keeps the evidence: the prompt code wrote; from Hermes' session export, the system prompt Hermes
added and the whole conversation, compression summaries included; the tool's call log of every page or file read; and
calls.jsonl, one line per agent call, written whatever the call's outcome: its time, tokens, and why code rejected it.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

from ergon import profiles, schema


TOOLSET = "ergon"   # the MCP server name ergon/hermes.yaml gives ergon/wikitool.py
MAX_TURNS = 10      # a ceiling, not a target: a search and one read_pages call are the normal case
MAX_SECONDS = 1800  # 30 minutes per agent call (ADR 0018)
CALLS = "calls.jsonl"
USAGE = ("input_tokens", "output_tokens", "cache_read_tokens", "reasoning_tokens", "api_call_count", "tool_call_count")


class AgentError(Exception):
    pass


def scope(run_dir: Path, pages_dir: Path, log: str = "tool-calls.jsonl", repos: dict | None = None) -> None:
    """Fix what the tool may read in this run: one wiki's pages, and the given repos if any. The call log starts
    empty."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / log).write_text("")
    doc = {"pages": str(pages_dir.resolve()), "log": log}
    if repos:
        doc["repos"] = {name: str(path.resolve()) for name, path in repos.items()}
    (run_dir / "tool-scope.json").write_text(json.dumps(doc, indent=2) + "\n")


def _call(profile: str, prompt: str, run_dir: Path, label: str, tools: tuple = (), turns: int = MAX_TURNS,
          cwd: Path | None = None, yolo: bool = False) -> tuple[str, dict]:
    """Run one agent call. Returns its output and its record for calls.jsonl; a call that fails or times out is
    logged here, before the error, so its time and tokens are never lost."""
    prompt_file = run_dir / f"{label}.prompt.md"
    prompt_file.write_text(prompt)
    cmd = ["hermes", "-p", profile, "chat", "-Q", "--oneshot", "--ignore-rules", "-t", ",".join((TOOLSET, *tools)),
           "--source", "tool", "--max-turns", str(turns), "--run-budget", str(MAX_SECONDS),
           "--query-file", str(prompt_file.resolve())] + (["--yolo"] if yolo else [])
    env = {**os.environ, "ERGON_RUN": str(run_dir.resolve()),  # the wiki tool finds its scope through this
           "ERGON_TOOL": str(profiles.TOOL)}
    if cwd:
        env["TERMINAL_CWD"] = str(Path(cwd).resolve())   # where Hermes' terminal tool starts
    record = {"label": label, "profile": profile, "started": _now()}
    clock = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_SECONDS + 120, env=env, cwd=cwd)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:   # Hermes ignored its own run budget
        stdout, stderr, code = _text(exc.stdout), _text(exc.stderr), None
    record.update(ended=_now(), seconds=round(time.monotonic() - clock, 3), exit=code)
    (run_dir / f"{label}.output.txt").write_text(stdout + ("\n--- stderr ---\n" + stderr if stderr else ""))
    error = None
    if code is None:
        error = f"hermes ran past {MAX_SECONDS + 120} seconds and was stopped"
    elif code != 0:
        error = f"hermes exited {code}"
    try:
        record.update(_save_session(profile, stdout + stderr, run_dir, label))
    except AgentError as exc:   # a failed call often has no session; its time is still logged
        error = error or str(exc)
    if error:
        log_call(run_dir, record, "failed", [error])
        raise AgentError(f"{error}; see {run_dir / (label + '.output.txt')}")
    return stdout, record


def log_call(run_dir: Path, record: dict, outcome: str, reasons: list[str] = ()) -> None:
    """Append one call to calls.jsonl. outcome: accepted, rejected (code found problems in the answer) or failed."""
    with (run_dir / CALLS).open("a") as log:
        log.write(json.dumps({**record, "outcome": outcome, "reasons": list(reasons)}) + "\n")


def _now() -> str:
    now = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)) + f".{int(now * 1000) % 1000:03d}Z"


def _text(out) -> str:
    return out.decode(errors="replace") if isinstance(out, bytes) else (out or "")


def _export(profile: str, sid: str) -> dict:
    result = subprocess.run(["hermes", "-p", profile, "sessions", "export", "--session-id", sid, "--format", "jsonl",
                             "-"], capture_output=True, text=True)
    try:
        return json.loads(result.stdout.splitlines()[0])
    except (IndexError, ValueError):
        raise AgentError(f"hermes exported no session {sid}: {result.stderr.strip()}") from None


def _save_session(profile: str, output: str, run_dir: Path, label: str) -> dict:
    """Save what the model saw: the system prompt Hermes sent, and the whole conversation, including any summary
    compression wrote. A compressed session continues in a child session, so the export follows the parents back
    to the first one; <label>.session.jsonl holds one session per line, oldest first."""
    found = re.findall(r"session_id:\s*(\S+)", output)
    if not found:
        raise AgentError("hermes printed no session_id; cannot record the session")
    sessions = [_export(profile, found[-1])]
    while sessions[0].get("parent_session_id"):
        sessions.insert(0, _export(profile, sessions[0]["parent_session_id"]))
    if not sessions[-1].get("system_prompt"):
        raise AgentError(f"hermes exported no system prompt for session {found[-1]}")
    (run_dir / f"{label}.system-prompt.md").write_text(sessions[-1]["system_prompt"])
    (run_dir / f"{label}.session.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sessions))
    usage = {key: sum(s.get(key) or 0 for s in sessions) for key in USAGE}
    return {"session": found[-1], "model": sessions[-1].get("model"), **usage}


def _extract(text: str):
    fenced = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
    raw = fenced[-1] if fenced else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def ask(profile: str, prompt: str, contract: Path, run_dir: Path, name: str, extra_check=None, retries: int = 2,
        **call):
    """Ask until the answer satisfies the contract and extra_check, at most retries+1 times."""
    contract_schema = schema.load(contract)
    contract_text = json.dumps(contract_schema, indent=2)
    base = (f"{prompt}\n\n# Answer contract\nReturn exactly one JSON object, in one ```json block, that satisfies "
            f"this JSON Schema. Code checks it; anything else is rejected.\n\n```json\n{contract_text}\n```\n")
    current, errs = base, []
    for attempt in range(1, retries + 2):
        output, record = _call(profile, current, run_dir, f"{name}-{attempt}", **call)
        try:
            data = _extract(output)
        except ValueError as exc:
            errs = [f"the answer is not one parseable JSON object: {exc}"]
        else:
            errs = schema.errors(data, contract_schema) or (extra_check(data) if extra_check else [])
        log_call(run_dir, record, "rejected" if errs else "accepted", errs)
        if not errs:
            (run_dir / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
            return data
        current = (base + "\n# Your previous answer was rejected\n" + "\n".join(f"- {e}" for e in errs)
                   + "\n\nPrevious answer:\n\n" + output[-20000:] + "\n\nReturn the corrected JSON only.\n")
    raise AgentError(f"{name}: no valid answer after {retries + 1} attempts: " + "; ".join(errs[:10]))
