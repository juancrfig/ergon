"""Runs a node's agent: one Hermes profile (or agy, ADR 0029), a context assembled by code, a JSON answer checked
by code.

The agent gets no skills, memory, SOUL or AGENTS.md from Hermes (--ignore-rules) and only the toolsets its node
names: ergon's read-only tool (ADR 0016), scoped by code per run, plus Hermes' terminal and file tools for Build
(ADR 0023). The run folder keeps the evidence: the prompt code wrote; from Hermes' session export, the system prompt
Hermes added and the whole conversation, compression summaries included; the tool's call log of every page or file
read; and calls.jsonl, one line per agent call, written whatever the call's outcome: its time, tokens, and why code
rejected it.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ergon import profiles, schema


TOOLSET = "ergon"   # the MCP server name ergon/hermes.yaml gives ergon/wikitool.py
MAX_TURNS = 10      # a ceiling, not a target: a search and one read_pages call are the normal case
MAX_SECONDS = 1800  # 30 minutes per agent call (ADR 0018)
CALLS = "calls.jsonl"
USAGE = ("input_tokens", "output_tokens", "cache_read_tokens", "reasoning_tokens", "api_call_count", "tool_call_count")
# A call the connection dropped resumes its own conversation once, as <label>-resume, so the work done before the
# drop is kept (ADR 0031). Each backend implements it: Hermes with --resume, agy with --conversation. A new backend
# must implement it too, or a dropped call starts over.
RESUME_PROMPT = ("The connection to the model dropped before you finished. Continue the same task from where you "
                 "stopped: your earlier steps and their results are above. End with the answer the task asks for.")
# Hermes' last words when its own retries ran out on a provider error (agent/turn_failure_copy.py).
HERMES_TRANSIENT = ("temporarily unavailable",)


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
          cwd: Path | None = None, yolo: bool = False, resume: tuple | None = None) -> tuple[str, dict]:
    """Run one agent call. Returns its output and its record for calls.jsonl; a call that fails or times out is
    logged here, before the error, so its time and tokens are never lost. resume: (session id, the dropped call's
    record), to continue that session; its record then holds only what the resumed part used."""
    prompt_file = run_dir / f"{label}.prompt.md"
    prompt_file.write_text(RESUME_PROMPT if resume else prompt)
    if profiles.backend() == "agy":
        return _call_agy(profile, prompt, run_dir, label, tools, cwd)
    cmd = ["hermes", "-p", profile, "chat", "-Q", "--oneshot", "--ignore-rules", "-t", ",".join((TOOLSET, *tools)),
           "--source", "tool", "--max-turns", str(turns), "--run-budget", str(MAX_SECONDS),
           "--query-file", str(prompt_file.resolve())] + (["--yolo"] if yolo else []) + \
          (["--resume", resume[0]] if resume else [])
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
        if resume:   # the export counts the whole session
            record.update(_minus(record, resume[1]))
    except AgentError as exc:   # a failed call often has no session; its time is still logged
        error = error or str(exc)
    if error:
        log_call(run_dir, record, "failed", [error])
        if not resume and record.get("session") and any(sign in stdout for sign in HERMES_TRANSIENT):
            return _call(profile, prompt, run_dir, label + "-resume", tools, turns, cwd, yolo,
                         resume=(record["session"], record))
        raise AgentError(f"{error}; see {run_dir / (label + '.output.txt')}")
    return stdout, record


def _minus(record: dict, earlier: dict, keys: tuple = USAGE) -> dict:
    """The usage of a resumed call alone: its backend reports the whole conversation's."""
    return {key: max((record.get(key) or 0) - (earlier.get(key) or 0), 0) for key in keys if key in record}


# agy's names for what Hermes' terminal and file toolsets give Build. Without them an agy agent has only the ergon
# tool (and agy's task list); agy has no turn limit, so MAX_SECONDS is the only ceiling.
AGY_TOOLS = ("run_command", "read_file", "view_file", "write_file", "edit_file", "grep_search", "list_dir",
             "find_by_name")
AGY_HOME = Path.home() / ".gemini" / "antigravity-cli"


def _agy_home(run_dir: Path, workspace: Path, tools: tuple) -> Path:
    """A throwaway HOME for one agy call: the user's login, the ergon tool scoped to this run, the one agent Ergon
    defines, and nothing else of the user's agy setup (no other MCP servers, rules or agents)."""
    home = Path(tempfile.mkdtemp(prefix="ergon-agy-"))
    cli, config = home / ".gemini" / "antigravity-cli", home / ".gemini" / "config"
    (config / "agents" / "ergon").mkdir(parents=True)
    cli.mkdir(parents=True)
    for name in ("antigravity-oauth-token", "installation_id"):
        if (AGY_HOME / name).exists():
            (cli / name).symlink_to(AGY_HOME / name)
    (cli / "settings.json").write_text(json.dumps({"trustedWorkspaces": [str(workspace)]}))
    rg = shutil.which("rg")
    if rg:   # agy's own ripgrep needs a loader only Google machines have, so its search fell back to grep. A file
        # where agy unpacks it stops the unpacking; agy then takes the rg in ~/.local/bin.
        (home / ".cache" / "antigravity").mkdir(parents=True)
        (home / ".cache" / "antigravity" / "bin").write_text("")
        (home / ".local" / "bin").mkdir(parents=True)
        (home / ".local" / "bin" / "rg").symlink_to(rg)
    (config / "mcp_config.json").write_text(json.dumps({"mcpServers": {TOOLSET: {
        "command": "python3", "args": [str(profiles.TOOL), str(run_dir.resolve())],
        "env": {"ERGON_RUN": str(run_dir.resolve())}}}}))
    allowed = list(AGY_TOOLS) if tools else []
    (config / "agents" / "ergon" / "agent.md").write_text(
        f"---\nname: ergon\ndescription: An Ergon node agent\nmainAgent: true\ninheritMcp: true\n"
        f"tools: {json.dumps(allowed)}\n---\n# Ergon node agent\nThe prompt is your whole task. Code reads your final "
        f"answer, not a person.\n")
    return home


# agy errors that come from the connection, not the model's work: the call resumes or runs once more (ADR 0029, 0031).
AGY_TRANSIENT = ("API error", "stream idle timeout", "Eligibility check failed", "EOF", "connection reset",
                 "no result", "invalid model selection", "stream was interrupted")


def _call_agy(profile: str, prompt: str, run_dir: Path, label: str, tools: tuple, cwd,
              retry: bool = True, resume: tuple | None = None) -> tuple[str, dict]:
    """The same call through agy. Its stream of steps is the session record; the conversation database is kept
    too. A connection error is logged as a failed call; the call then resumes its conversation once, as
    <label>-resume, in the same throwaway HOME, or, when agy never started one, runs once more as <label>-retry.
    agy shows no system prompt, so <label>.system-prompt.md holds the agent definition Ergon gave it.
    resume: (HOME, conversation id, the dropped call's record)."""
    workspace = Path(cwd or run_dir).resolve()
    home = resume[0] if resume else _agy_home(run_dir, workspace, tools)
    if resume:
        (run_dir / f"{label}.prompt.md").write_text(RESUME_PROMPT)
    cmd = ["agy", "--agent", "ergon", "--model", profiles.AGY_MODEL, "--input-format", "stream-json",
           "--output-format", "stream-json", "--dangerously-skip-permissions", "--print="] + \
          (["--conversation", resume[1]] if resume else [])
    env = {**os.environ, "HOME": str(home), "ERGON_RUN": str(run_dir.resolve())}
    record = {"label": label, "profile": profile, "backend": "agy", "started": _now()}
    clock = time.monotonic()
    message = json.dumps({"event": "user", "message": {"content": RESUME_PROMPT if resume else prompt}}) + "\n"
    try:
        result = subprocess.run(cmd, input=message, capture_output=True, text=True, timeout=MAX_SECONDS + 120,
                                env=env, cwd=workspace)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = _text(exc.stdout), _text(exc.stderr), None
    record.update(ended=_now(), seconds=round(time.monotonic() - clock, 3), exit=code)
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    (run_dir / f"{label}.session.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (run_dir / f"{label}.system-prompt.md").write_text(
        (home / ".gemini" / "config" / "agents" / "ergon" / "agent.md").read_text())
    final = next((e["result"] for e in reversed(events) if e.get("event") == "result"), {})
    conversation = final.get("conversation_id")
    if conversation and (home / ".gemini/antigravity-cli/conversations" / f"{conversation}.db").exists():
        shutil.copy(home / ".gemini/antigravity-cli/conversations" / f"{conversation}.db",
                    run_dir / f"{label}.conversation.db")
    logs = sorted((home / ".gemini/antigravity-cli/log").glob("cli-*.log"))
    if logs:   # agy's own log: its model requests and errors, for slow or failed calls
        shutil.copy(logs[-1], run_dir / f"{label}.agy.log")
    response = final.get("response") or ""
    (run_dir / f"{label}.output.txt").write_text(response + "\n--- stderr ---\n" + stderr if stderr else response)
    usage = final.get("usage") or {}
    record.update(session=conversation, model=profiles.AGY_MODEL, input_tokens=usage.get("input_tokens", 0),
                  output_tokens=usage.get("output_tokens", 0), cache_read_tokens=usage.get("cache_read_tokens", 0),
                  reasoning_tokens=usage.get("thinking_tokens", 0), api_call_count=final.get("num_turns", 0),
                  tool_call_count=sum(1 for e in events if e.get("event") == "step_update"
                                      and e["step_update"].get("step_type") == "tool"
                                      and e["step_update"].get("state") == "DONE"))
    if resume:   # agy's totals cover the whole conversation; its stream of steps, only this part
        record.update(_minus(record, resume[2], tuple(k for k in USAGE if k != "tool_call_count")))
    error = None
    if code is None:
        error = f"agy ran past {MAX_SECONDS + 120} seconds and was stopped"
    elif not final:
        error = f"agy exited {code} with no result"
    elif final.get("status") != "SUCCESS":
        error = f"agy: {final.get('status')}: {final.get('error')}"
    if error:
        log_call(run_dir, record, "failed", [error])
        if retry and not resume and any(sign in error for sign in AGY_TRANSIENT):
            if conversation:
                return _call_agy(profile, prompt, run_dir, label + "-resume", tools, cwd, retry=False,
                                 resume=(home, conversation, record))
            shutil.rmtree(home, ignore_errors=True)
            return _call_agy(profile, prompt, run_dir, label + "-retry", tools, cwd, retry=False)
        shutil.rmtree(home, ignore_errors=True)
        raise AgentError(f"{error}; see {run_dir / (label + '.output.txt')}")
    shutil.rmtree(home, ignore_errors=True)
    return response, record


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
        retry_note: str = "Return the corrected JSON only.", **call):
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
                   + "\n\nPrevious answer:\n\n" + output[-20000:] + f"\n\n{retry_note}\n")
    raise AgentError(f"{name}: no valid answer after {retries + 1} attempts: " + "; ".join(errs[:10]))
