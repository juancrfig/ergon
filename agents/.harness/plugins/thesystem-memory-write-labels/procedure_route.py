"""Durable, serialized skill updates requested through labeled procedures."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import socket
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


LOCAL_LOCKS: dict[str, threading.Lock] = {}
LOCAL_LOCKS_GUARD = threading.Lock()


def _home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()


def _queue() -> Path:
    return _home() / "curate-memory" / "skill-requests.jsonl"


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _events() -> list[dict]:
    try:
        lines = _queue().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def _latest() -> dict[str, dict]:
    return {row["request_id"]: row for row in _events() if row.get("request_id")}


def _event(request: dict, status: str, **fields) -> dict:
    row = {**request, **fields, "status": status, "updated_at": datetime.now().astimezone().isoformat()}
    _append(_queue(), row)
    return row


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    ignored = {"a", "an", "the", "to", "for", "of", "and", "or", "in", "on", "with", "how", "when", "use", "using", "should", "must"}
    selected = [word for word in words if word not in ignored][:4]
    return "-".join(selected)[:64].strip("-") or "requested-procedure"


def _skill_dir(request: dict) -> Path:
    workspace_value = os.environ.get("THESYSTEM_WORKSPACE")
    workspace_skills = (Path(workspace_value).expanduser() if workspace_value else Path.cwd()) / "agents" / "skills"
    home_skills = _home() / "skills"
    for root in (workspace_skills, home_skills):
        proposed = root / request["skill_key"]
        if proposed.is_dir():
            return proposed.resolve()
        if not root.is_dir():
            continue
        terms = set(request["skill_key"].split("-"))
        ranked = []
        for folder in root.iterdir():
            if not folder.is_dir():
                continue
            name_terms = set(re.findall(r"[a-z0-9]+", folder.name.lower()))
            overlap = len(terms & name_terms)
            if overlap:
                ranked.append((-overlap, folder.name, folder.resolve()))
        if ranked:
            return sorted(ranked)[0][2]
    return (home_skills / request["skill_key"]).resolve()


def _lock_for(path: Path):
    key = str(path)
    with LOCAL_LOCKS_GUARD:
        return LOCAL_LOCKS.setdefault(key, threading.Lock())


def _snapshot(path: Path) -> dict[str, bytes]:
    if not path.exists():
        return {}
    return {item.relative_to(path).as_posix(): item.read_bytes() for item in path.rglob("*") if item.is_file()}


def _changes(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


def _write_learning(request: dict, changed: list[str], output: str) -> None:
    description = output.strip()[-4000:] or "Skill update completed; see changed files."
    _append(_home() / "curate-memory" / "skill-learning.jsonl", {
        "at": datetime.now().astimezone().isoformat(), "request_id": request["request_id"],
        "run_id": request["run_id"], "skill": request["skill_key"],
        "skill_directory": request["skill_directory"], "changed_files": changed,
        "description": description,
    })


def _baseline_proposal(request: dict, changed: list[str]) -> list[dict]:
    workspace_value = os.environ.get("THESYSTEM_WORKSPACE")
    workspace = Path(workspace_value).expanduser() if workspace_value else Path.cwd()
    candidates_script = workspace / "agents" / "skills" / "propose-default" / "scripts" / "candidates.py"
    if not candidates_script.is_file():
        return []
    try:
        result = subprocess.run(["python3", str(candidates_script), "--workspace", str(workspace), "list"],
                                capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            return []
        candidates = json.loads(result.stdout).get("candidates", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    skill_directory = Path(request["skill_directory"])
    local = {(skill_directory / name).resolve() for name in changed}
    eligible = []
    for candidate in candidates:
        path = workspace / candidate["path"]
        if str(path.resolve()) in local and candidate["path"].startswith("agents/"):
            eligible.append(candidate)
    return eligible


def _alert(message: str) -> None:
    env_file = _home() / ".env"
    target = None
    try:
        for line in reversed(env_file.read_text(encoding="utf-8").splitlines()):
            key, sep, value = line.partition("=")
            if sep and key.strip().removeprefix("export ").strip() == "TELEGRAM_HOME_CHANNEL":
                target = value.strip().strip("\"'") or None
                break
    except OSError:
        pass
    error = "TELEGRAM_HOME_CHANNEL is not configured"
    if target:
        try:
            result = subprocess.run(["hermes", "send", "--to", f"telegram:{target}", message],
                                    capture_output=True, text=True, timeout=15, check=False)
            if result.returncode == 0:
                return
            error = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        except Exception as caught:
            error = str(caught)
    _append(_home() / "curate-memory" / "alerts.jsonl", {
        "at": datetime.now().astimezone().isoformat(), "instance": f"{socket.gethostname()}:{os.getenv('USER', 'unknown')}",
        "message": message, "delivery_error": error,
    })


def _daily_count() -> tuple[str, int]:
    today = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
    runs = set()
    for row in _events():
        if not row.get("run_id") or row.get("status") not in ("queued", "running", "done", "failed"):
            continue
        try:
            created = datetime.fromisoformat(row["created_at"]).astimezone(ZoneInfo("America/Bogota")).date().isoformat()
        except (KeyError, ValueError):
            continue
        if created == today:
            runs.add(row["run_id"])
    return today, len(runs)


def _run(request: dict) -> None:
    skill_directory = Path(request["skill_directory"])
    lock_path = _home() / "curate-memory" / "skill-locks" / (hashlib.sha256(str(skill_directory).encode()).hexdigest() + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _lock_for(skill_directory), lock_path.open("a", encoding="utf-8") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        latest = _latest().get(request["request_id"], {})
        if latest.get("status") in ("done", "failed"):
            return
        request = _event(request, "running", started_at=datetime.now().astimezone().isoformat())
        skill_directory.mkdir(parents=True, exist_ok=True)
        before = _snapshot(skill_directory)
        prompt = (
            "Update or create the matching skill in this instance's LOCAL skills directory only. "
            "Do not edit workspace defaults or any shared source file. Create SKILL.md with a name/description "
            "frontmatter if needed. Make the requested improvement directly without asking for per-edit approval. "
            "Use relevant existing files in the skill directory as context. At the end, summarize every edit and "
            "changed file. If you cannot apply a meaningful edit, explain why and exit unsuccessfully.\n\n"
            f"Skill key: {request['skill_key']}\nSkill directory: {skill_directory}\n"
            f"Request: {request['request_text']}"
        )
        command = ["hermes", "chat", "--oneshot", "--provider", "openai-codex", "--model", "gpt-6-luna", prompt]
        try:
            result = subprocess.run(command, cwd=str(skill_directory), capture_output=True, text=True, check=False)
            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            changed = _changes(before, _snapshot(skill_directory))
            if changed:
                _write_learning(request, changed, output)
            if result.returncode != 0 or not changed:
                reason = f"command exit={result.returncode}; applied_files={changed}; output={output[-3000:]}"
                _event(request, "failed", error=reason, changed_files=changed)
                threading.Thread(target=_alert, args=(f"Skill update failed for request {request['request_id']} (run {request['run_id']}); status is recorded in skill-requests.jsonl.",), daemon=True).start()
                return
            proposals = _baseline_proposal(request, changed)
            proposal = None
            if proposals:
                proposal = {
                    "title": f"Improve {request['skill_key']} skill",
                    "label": "skills",
                    "files": [candidate["path"] for candidate in proposals],
                    "description": output.strip()[-4000:] or f"Updated {request['skill_key']} based on a procedure request.",
                    "status": "awaiting-human-approval",
                }
            _event(request, "done", changed_files=changed, proposal=proposal,
                   proposal_status="prepared-not-opened" if proposal else None)
        except Exception as error:
            _event(request, "failed", error=f"{type(error).__name__}: {error}")
            threading.Thread(target=_alert, args=(f"Skill update failed for request {request['request_id']} (run {request['run_id']}); status is recorded in skill-requests.jsonl.",), daemon=True).start()
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def _schedule(request: dict) -> None:
    thread = threading.Thread(target=_run, args=(request,), name=f"skill-update-{request['request_id']}", daemon=True)
    thread.start()


def recover() -> None:
    try:
        latest = _latest()
    except (OSError, ValueError, KeyError):
        return
    for request in latest.values():
        if request.get("status") in ("queued", "running"):
            _schedule(request)


def handle(entry_text: str, label: str, argument: str | None, context: dict) -> dict:
    home = _home()
    skill_key = _slug(entry_text)
    skill_directory = _skill_dir({"skill_key": skill_key})
    request_id = uuid.uuid4().hex
    run_id = uuid.uuid4().hex
    created_at = datetime.now().astimezone().isoformat()
    request = {
        "request_id": request_id, "run_id": run_id, "created_at": created_at,
        "session": context.get("session_id"), "label": label, "request_text": entry_text,
        "skill_key": skill_key, "skill_directory": str(skill_directory),
    }
    _event(request, "queued")
    today, count = _daily_count()
    if count > 150:
        alert_marker = home / "curate-memory" / "skill-run-alerts" / f"{today}.alerted"
        alert_marker.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(alert_marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
            threading.Thread(target=_alert, args=(f"Skill update run count exceeded 150 for {today} (America/Bogota): {count} runs. New runs continue without throttling.",), daemon=True).start()
    _schedule(request)
    return {
        "decision": "routed", "destination": str(skill_directory), "artifact": request_id,
        "message": f"Procedure queued for skill {skill_key}. Request {request_id}; run {run_id}; status queued.",
    }
