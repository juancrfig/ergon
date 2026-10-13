"""Enforce labeled Hermes memory writes before native approval and storage."""
from __future__ import annotations

import copy
import fcntl
import getpass
import json
import os
import socket
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ID = "thesystem-memory-write-labels"
ALLOWED_LABELS = (
    "user-preference", "user-fact", "environment-fact", "agent-convention", "procedure",
    "project-fact:<project>", "safety-rule",
)
ROUTE_KINDS = ("procedure", "project-fact", "safety-rule")
STATE_LOCK = threading.Lock()
CALL_REPORTS: dict[str, str] = {}


def _home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()


def _identity() -> str:
    return f"{socket.gethostname()}:{getpass.getuser()}"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _alert_target() -> str | None:
    env_path = _home() / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        key, separator, value = line.partition("=")
        if separator and key.strip().removeprefix("export ").strip() == "TELEGRAM_HOME_CHANNEL":
            value = value.strip().strip("\"'")
            if value:
                return value
    return None


def _alert(message: str) -> None:
    try:
        target = _alert_target()
    except Exception as error:
        target = None
        failure = f"could not read alert target: {error}"
    else:
        failure = None
    if target:
        try:
            result = subprocess.run(
                ["hermes", "send", "--to", f"telegram:{target}", message],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if result.returncode == 0:
                return
            failure = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        except Exception as error:
            failure = str(error)
    else:
        failure = "TELEGRAM_HOME_CHANNEL is not configured"
    try:
        _append_jsonl(_home() / "curate-memory" / "alerts.jsonl", {
            "at": _now(), "instance": _identity(), "message": message, "delivery_error": failure,
        })
    except Exception:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Rows from the hook's worker thread are buffered and flushed only if the hook finishes inside its budget, so a
# timed-out call never leaves an "allowed" row next to the "blocked" row the timeout path writes.
_LOG_BUFFER = threading.local()


def _record(session: str | None, original: Any, label: str | None, decision: str,
            destination: str | None, reason: str, artifact: str | None = None) -> None:
    row = {
        "at": _now(), "instance": _identity(), "session": session,
        "original_text": original, "label": label, "decision": decision,
        "destination": destination, "reason": reason, "artifact": artifact,
    }
    buffer = getattr(_LOG_BUFFER, "rows", None)
    if buffer is not None:
        buffer.append(row)
        return
    _append_jsonl(_home() / "curate-memory" / "write-labels.jsonl", row)


def _parse_label(text: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(text, str):
        return None, None, None
    if not text.startswith("["):
        return None, None, None
    closing = text.find("] ")
    if closing < 0:
        return None, None, None
    label = text[1:closing]
    content = text[closing + 2:]
    if label in ("user-preference", "user-fact", "environment-fact", "agent-convention", "procedure", "safety-rule"):
        return label, content, None
    if label.startswith("project-fact:") and label[len("project-fact:"):].strip():
        return label, content, label[len("project-fact:"):]
    return label, content, None


def _label_help() -> str:
    return "Allowed labels: " + ", ".join(f"[{label}]" for label in ALLOWED_LABELS) + ". Use the required leading format [<label>] <one idea>."


def _refusal(original: Any, label: str | None, target: str, reason: str, correction: str,
             session: str | None) -> tuple[str, str]:
    message = f"Memory write refused: {reason}. {correction}"
    _record(session, original, label, "refused", target, reason)
    return message, "refused"


def _route(entry: str, label: str, argument: str | None, context: dict[str, Any]) -> dict[str, Any]:
    return {"decision": "refused", "destination": label, "artifact": None,
            "message": f"Memory write refused: route not yet available for [{label}]. Keep it out of memory until its route is enabled."}

def _handle_project_fact(entry: str, label: str, argument: str | None, context: dict[str, Any]) -> dict[str, Any]:
    workspace = Path.cwd().resolve()
    workspace_directories = {"agents", "docs", "tickets", "artifacts", "wiki"}
    projects = sorted(
        (path for path in workspace.iterdir() if path.is_dir() and not path.is_symlink()
         and not path.name.startswith(".") and path.name not in workspace_directories),
        key=lambda path: path.name,
    )
    project_names = [path.name for path in projects]
    requested = (argument or "").strip()
    if requested.casefold() in {"none", "none fits", "no project"}:
        from tools import write_approval as approval

        payload = {"action": "add", "target": "memory", "content": entry}
        record = approval.stage_write(
            approval.MEMORY, payload, summary=f"project-unknown: {entry[:120]}",
            origin=approval.current_origin(),
        )
        pending = _home() / "pending" / "memory" / f"{record.get('id', '')}.json"
        if not record.get("id") or not pending.is_file():
            raise RuntimeError("human review request was not persisted")
        return {
            "decision": "routed", "destination": "human review queue", "artifact": str(pending),
            "message": "No project was selected. The original fact was added to the human review queue "
                       "with reason project-unknown.",
        }

    candidate = workspace / requested
    try:
        resolved = candidate.resolve(strict=True)
        inside_workspace = resolved.parent == workspace
        project_is_real_dir = not candidate.is_symlink() and candidate.is_dir()
    except (OSError, RuntimeError):
        resolved = candidate
        inside_workspace = False
        project_is_real_dir = False
    if (not requested or Path(requested).is_absolute() or Path(requested).name != requested
            or not inside_workspace or not project_is_real_dir or resolved.name != requested
            or requested not in project_names):
        available = ", ".join(project_names) if project_names else "(none)"
        return {
            "decision": "refused", "destination": requested or "project wiki inbox", "artifact": None,
            "message": f"Unknown project {requested!r}. Existing project folders: {available}. "
                       "Retry with an existing project name, or explicitly state that none fits.",
        }

    wiki_path = resolved / "wiki"
    raw_path = wiki_path / "raw"
    if wiki_path.is_symlink() or raw_path.is_symlink():
        raise ValueError("project wiki source path must not contain symlinks")
    raw = raw_path
    import hashlib

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(entry.encode("utf-8")).hexdigest()[:8]
    base_name = f"memory-{timestamp}-{digest}"
    session = context.get("session_id")
    metadata = (
        "---\n"
        f"origin_instance: {json.dumps(_identity(), ensure_ascii=False)}\n"
        f"origin_session: {json.dumps(str(session) if session is not None else '', ensure_ascii=False)}\n"
        f"origin_time: {json.dumps(now.isoformat().replace('+00:00', 'Z'))}\n"
        f"decision_log: {json.dumps(str(_home() / 'curate-memory' / 'write-labels.jsonl'))}\n"
        "---\n"
    )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    workspace_fd = os.open(workspace, directory_flags)
    try:
        project_fd = os.open(requested, directory_flags | os.O_NOFOLLOW, dir_fd=workspace_fd)
        try:
            for component in ("wiki", "raw"):
                try:
                    os.mkdir(component, dir_fd=project_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(component, directory_flags, dir_fd=project_fd)
                os.close(project_fd)
                project_fd = next_fd
            for suffix in range(1, 21):
                filename = f"{base_name}{'' if suffix == 1 else f'-{suffix}'}.md"
                try:
                    source_fd = os.open(
                        filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o666, dir_fd=project_fd,
                    )
                except FileExistsError:
                    continue
                with os.fdopen(source_fd, "w", encoding="utf-8") as stream:
                    stream.write(entry + "\n\n" + metadata)
                destination = raw / filename
                break
            else:
                raise FileExistsError("could not allocate a unique project source filename after 20 attempts")
        finally:
            os.close(project_fd)
    finally:
        os.close(workspace_fd)
    return {
        "decision": "routed", "destination": str(raw), "artifact": str(destination),
        "message": f"Project fact routed to {requested}. Source file: {destination}. "
                   "It is pending project ingest; do not retry it as memory.",
    }


ROUTE_HANDLERS = {kind: _route for kind in ROUTE_KINDS}
ROUTE_HANDLERS["project-fact"] = _handle_project_fact


def _ensure_active(context: dict[str, Any]) -> None:
    cancelled = context.get("cancelled")
    if cancelled is not None and cancelled.is_set():
        raise TimeoutError("plugin-timeout")


def _decide(text: Any, target: str, session: str | None, context: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    _ensure_active(context)
    label, content, argument = _parse_label(text)
    if label is None or content is None:
        if isinstance(text, str) and len(text) > 300:
            message, _ = _refusal(text, None, target, "label-less content exceeds the 300-character limit",
                                  _label_help() + " Keep each idea at most 300 characters; split it into separate ideas.", session)
        else:
            message, _ = _refusal(text, None, target, "the required leading label is missing or malformed",
                                  _label_help(), session)
        return None, message, "refused"
    known = label in ("user-preference", "user-fact", "environment-fact", "agent-convention", "procedure", "safety-rule") or argument is not None
    if not known:
        message, _ = _refusal(text, label, target, f"[{label}] is not an allowed label", _label_help(), session)
        return None, message, "refused"
    if label in ("user-preference", "user-fact") and target != "user":
        message, _ = _refusal(text, label, target, f"[{label}] requires target=user, not target={target}",
                              "Set target=user and retry.", session)
        return None, message, "refused"
    if label in ("environment-fact", "agent-convention") and target != "memory":
        message, _ = _refusal(text, label, target, f"[{label}] requires target=memory, not target={target}",
                              "Set target=memory and retry.", session)
        return None, message, "refused"
    if len(content) > 300:
        message, _ = _refusal(text, label, target, "content exceeds the 300-character limit",
                              "Keep the label and split it into separate ideas of at most 300 characters.", session)
        return None, message, "refused"
    if label in ROUTE_KINDS or argument is not None:
        result = ROUTE_HANDLERS["project-fact" if argument is not None else label](content, label, argument, context)
        _ensure_active(context)
        decision = result["decision"]
        _record(session, text, label, decision, result.get("destination"), result.get("message", ""), result.get("artifact"))
        return None, result.get("message", "Memory route refused."), decision
    _ensure_active(context)
    _record(session, text, label, "allowed", target, "valid labeled memory write")
    return content, None, "allowed"


def _memory_tool_name(name: str) -> bool:
    return name in ("memory", "memory_tool")


def _write_text(item: dict[str, Any]) -> tuple[str, Any]:
    for key in ("content", "new_text"):
        if item.get(key) is not None:
            return key, item[key]
    return ("content" if "new_text" not in item else "new_text"), None


def _set_text(item: dict[str, Any], stripped: str) -> None:
    key, _ = _write_text(item)
    item[key] = stripped


def _hook(**kwargs):
    tool_name = kwargs.get("tool_name", "")
    if not _memory_tool_name(tool_name):
        return None
    args = kwargs.get("args")
    if not isinstance(args, dict):
        raise ValueError("memory tool arguments are not a mapping")
    session = kwargs.get("session_id")
    tool_call_id = kwargs.get("tool_call_id")
    context = {"session_id": session, "tool_call_id": tool_call_id, "args": args,
               "cancelled": kwargs.get("_cancelled")}
    reports: list[str] = []
    # Hermes treats an explicit null target as omitted and writes to MEMORY; mirror it so our decision matches.
    target = args.get("target")
    if target is None:
        target = "memory"
    if target not in ("user", "memory"):
        target = str(target)
    action = args.get("action")
    if isinstance(args.get("operations"), list):
        if not args["operations"]:
            reason = "operations batch is empty; include at least one add, replace, or remove operation"
            _record(session, args["operations"], None, "refused", target, reason)
            return {"action": "block", "message": f"Memory write refused: {reason}. Add at least one valid operation and retry."}
        accepted = []
        for operation in args["operations"]:
            if not isinstance(operation, dict):
                message, _ = _refusal(operation, None, target, "batch operation must be an object",
                                      "Remove the invalid operation and retry.", session)
                reports.append(message)
                continue
            op_action = operation.get("action", action)
            if op_action == "remove":
                original = operation.get("old_text")
                _record(session, original, None, "allowed", target, "valid remove operation")
                accepted.append(operation)
                continue
            if op_action not in ("add", "replace"):
                message, _ = _refusal(operation.get("content", operation.get("new_text")), None, target,
                                      f"unsupported operation action {op_action!r}", "Use add, replace, or remove.", session)
                reports.append(message)
                continue
            _, original = _write_text(operation)
            stripped, message, _ = _decide(original, target, session, context)
            if message or stripped is None:
                reports.append(message or "Memory write refused: the entry content is invalid.")
            else:
                _set_text(operation, stripped)
                accepted.append(operation)
        if accepted:
            args["operations"] = accepted
            if reports and not tool_call_id:
                _record(session, None, None, "blocked", target,
                        "batch contains rejected entries but has no tool_call_id for result reporting")
                return {"action": "block", "message": "Rejected batch entries cannot be reported safely; memory temporarily unavailable."}
            if reports:
                with STATE_LOCK:
                    CALL_REPORTS[str(tool_call_id)] = "\n".join(reports)
            return {"action": "modify", "args": args}
        return {"action": "block", "message": "\n".join(reports) or "Memory write refused: no valid operations were provided."}
    if action == "remove":
        original = args.get("old_text")
        _record(session, original, None, "allowed", target, "valid remove operation")
        return None
    if action not in ("add", "replace"):
        message, _ = _refusal(args.get("content", args.get("new_text")), None, target,
                              f"unsupported memory action {action!r}", "Use add, replace, or remove.", session)
        return {"action": "block", "message": message}
    _, original = _write_text(args)
    stripped, message, _ = _decide(original, target, session, context)
    if message or stripped is None:
        return {"action": "block", "message": message or "Memory write refused: the entry content is invalid."}
    _set_text(args, stripped)
    return {"action": "modify", "args": args}


def _fail_closed(error: Exception, session: str | None) -> dict[str, str]:
    message = "memory temporarily unavailable"
    try:
        _record(session, None, None, "blocked", None, f"plugin error: {type(error).__name__}: {error}")
    except Exception:
        pass
    try:
        _alert(f"theSystem memory-write labels plugin failed closed: {type(error).__name__}: {error}. Memory writes are temporarily unavailable.")
    except Exception:
        pass
    return {"action": "block", "message": message}


def _callback_budget() -> float:
    default = 30.0
    try:
        import yaml
        config = yaml.safe_load((_home() / "config.yaml").read_text(encoding="utf-8")) or {}
        configured = config.get("plugins", {}).get("hook_callback_timeout", default)
        timeout = float(configured)
        if timeout <= 0:
            return default * 0.5
    except Exception:
        timeout = default
    return timeout * 0.5


def _timeout_original(args: Any) -> Any:
    if not isinstance(args, dict):
        return None
    operations = args.get("operations")
    if isinstance(operations, list):
        return [
            _write_text(operation)[1] if isinstance(operation, dict) else operation
            for operation in operations
        ]
    return _write_text(args)[1]


def _plugin_timeout(kwargs: dict[str, Any]) -> dict[str, str]:
    session = kwargs.get("session_id")
    args = kwargs.get("args")
    target = (args.get("target") or "memory") if isinstance(args, dict) else None
    try:
        _record(session, _timeout_original(args), None, "blocked", target, "plugin-timeout")
    except Exception:
        pass
    message = "theSystem memory-write labels plugin exceeded its internal time budget; memory writes are temporarily unavailable."
    threading.Thread(target=_alert, args=(message,), daemon=True).start()
    return {"action": "block", "message": "memory temporarily unavailable"}


def _pre_tool_call(**kwargs):
    if not _memory_tool_name(kwargs.get("tool_name", "")):
        return None
    worker_kwargs = copy.deepcopy(kwargs)
    cancellation = threading.Event()
    worker_kwargs["_cancelled"] = cancellation
    result: dict[str, Any] = {}

    rows: list[dict[str, Any]] = []

    def run_hook() -> None:
        _LOG_BUFFER.rows = rows
        try:
            result["value"] = _hook(**worker_kwargs)
        except Exception as error:
            result["error"] = error

    worker = threading.Thread(target=run_hook, daemon=True)
    worker.start()
    worker.join(_callback_budget())
    if worker.is_alive():
        cancellation.set()
        return _plugin_timeout(kwargs)
    try:
        for row in rows:
            _append_jsonl(_home() / "curate-memory" / "write-labels.jsonl", row)
    except Exception as error:
        # An unlogged decision is untraceable, so treat it like any other plugin failure: block and alert.
        return _fail_closed(error, kwargs.get("session_id"))
    if "error" in result:
        return _fail_closed(result["error"], kwargs.get("session_id"))
    return result.get("value")


def _transform_tool_result(**kwargs):
    tool_call_id = kwargs.get("tool_call_id")
    if not tool_call_id:
        return None
    with STATE_LOCK:
        report = CALL_REPORTS.pop(str(tool_call_id), None)
    if report:
        return f"{kwargs.get('result', '')}\n\nMemory write decisions:\n{report}"
    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("transform_tool_result", _transform_tool_result)
    ctx.register_system_prompt_section(
        PLUGIN_ID,
        "Memory writes must contain one idea and begin with exactly one allowed label followed by a space: "
        "[user-preference], [user-fact], [environment-fact], [agent-convention], [procedure], "
        "[project-fact:<project>], or [safety-rule]. Content after the label is limited to 300 characters. "
        "USER labels (user-preference, user-fact) use target=user; MEMORY labels "
        "(environment-fact, agent-convention) use target=memory. Routes for procedure, project-fact, and "
        "safety-rule may be unavailable; do not store them as ordinary memory.",
        position="after_memory", max_chars=1000,
    )
