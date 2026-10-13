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


def _safety_controls(exclude_id: str | None = None) -> list[tuple[str, str]]:
    roots = {Path.cwd()}
    try:
        import yaml
        config = yaml.safe_load((_home() / "config.yaml").read_text(encoding="utf-8")) or {}
        cwd = config.get("terminal", {}).get("cwd")
        if isinstance(cwd, str) and cwd:
            roots.add(Path(cwd).expanduser())
    except Exception:
        pass
    controls: list[tuple[str, str]] = []
    for root in roots:
        for relative in (Path("agents/rules"), Path("agents/.harness/plugins"), Path("agents/.harness/hooks")):
            directory = root / relative
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".yaml", ".yml", ".json", ".toml"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                controls.extend((str(path), line.strip()) for line in text.splitlines() if len(line.strip()) >= 35)
    try:
        approvals = (_home() / "config.yaml").read_text(encoding="utf-8")
        controls.extend((str(_home() / "config.yaml"), line.strip()) for line in approvals.splitlines()
                        if any(term in line.lower() for term in ("approval", "allowlist", "allow_list", "allowed_commands")))
    except OSError:
        pass
    proposal_path = _home() / "curate-memory" / "control-proposals.jsonl"
    try:
        proposals: dict[str, dict[str, Any]] = {}
        for line in proposal_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                proposals[row["id"]] = row
        for proposal_id, row in proposals.items():
            if (proposal_id != exclude_id
                    and row.get("status") in {"screening", "pending-human", "approved"}
                    and isinstance(row.get("text"), str)):
                controls.append((f"{proposal_path}#{proposal_id}", row["text"]))
    except OSError:
        pass
    return controls


def _safety_duplicate_candidate(text: str, controls: list[tuple[str, str]]) -> list[tuple[str, str]]:
    from difflib import SequenceMatcher
    import re

    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    candidates = []
    for source, control in controls:
        other_words = set(re.findall(r"[a-z0-9]+", control.lower()))
        overlap = len(words & other_words) / max(1, len(words | other_words))
        if overlap >= 0.2 or SequenceMatcher(None, text.lower(), control.lower()).ratio() >= 0.4:
            candidates.append((source, control))
    return candidates[:40]


def _judge_safety_duplicate(text: str, candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    if not candidates:
        return None
    prompt = (
        "Determine whether the proposed control is already fully stated by one listed control. "
        "A duplicate must be a clear semantic duplicate, not merely related or overlapping. "
        "Return only JSON: {\"duplicate\":true|false,\"quote\": exact contiguous quote from one candidate or null,"
        "\"source\": exact candidate source string or null}. If uncertain, return false.\n" +
        json.dumps({"proposal": text, "candidates": [{"source": source, "text": control}
                                                      for source, control in candidates]}, ensure_ascii=False)
    )
    try:
        result = subprocess.run(
            ["hermes", "chat", "--oneshot", "--ignore-rules", "-t", "none", "--query-file", "-",
             "--run-budget", "55", "--max-turns", "3", "-Q", "--model", "gpt-6-luna"],
            input=prompt, capture_output=True, text=True, timeout=65, check=False,
        )
        if result.returncode:
            return None
        output = result.stdout.strip()
        if output.startswith("```"):
            output = output.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        decision = json.loads(output)
        if not isinstance(decision, dict) or decision.get("duplicate") is not True:
            return None
        quote, source = decision.get("quote"), decision.get("source")
        if not isinstance(quote, str) or not isinstance(source, str):
            return None
        if not any(source == item_source and quote and quote in control
                   for item_source, control in candidates):
            return None
        return quote, source
    except Exception:
        return None


def _update_control_proposal(path: Path, proposal_id: str, updates: dict[str, Any]) -> None:
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0)
        current = None
        for line in stream:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # corrupt rows are skipped per record; the resume path alerts on them
            if isinstance(row, dict) and row.get("id") == proposal_id:
                current = row
        if current is None:
            raise FileNotFoundError(f"Control proposal {proposal_id} disappeared")
        current.update(updates)
        current["updated_at"] = _now()
        stream.seek(0, os.SEEK_END)
        stream.write(json.dumps(current, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


_SCREENING_LOCK = threading.Lock()
_SCREENING_IDS: set[str] = set()


def _screen_safety_proposal(proposal_id: str) -> None:
    path = _home() / "curate-memory" / "control-proposals.jsonl"
    try:
        proposals: dict[str, dict[str, Any]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # corrupt rows are skipped per record; the resume path alerts on them
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                proposals[row["id"]] = row
        proposal = proposals.get(proposal_id)
        if not proposal or proposal.get("status") != "screening":
            return
        text = proposal.get("text")
        if not isinstance(text, str):
            raise ValueError("proposal text is missing")
        candidates = _safety_duplicate_candidate(text, _safety_controls(proposal_id))
        duplicate = _judge_safety_duplicate(text, candidates)
        if duplicate:
            _update_control_proposal(path, proposal_id, {
                "status": "duplicate", "duplicate_of": {"quote": duplicate[0], "source": duplicate[1]},
                "decision_reason": "System Two cited an exact existing control.", "decided_at": _now(),
            })
            return
        _update_control_proposal(path, proposal_id, {
            "status": "pending-human", "decision_reason": "No exact duplicate was established; human review required.",
            "decided_at": _now(),
        })
        _alert(f"Safety control proposal {proposal_id} is awaiting human review: {text}")
    except Exception as error:
        try:
            _update_control_proposal(path, proposal_id, {
                "status": "pending-human", "decision_reason": f"Duplicate review failed; human review required ({type(error).__name__}).",
                "decided_at": _now(),
            })
        except Exception:
            pass
        _alert(f"Safety control proposal {proposal_id} duplicate review failed; it remains for human review: {type(error).__name__}: {error}")
    finally:
        with _SCREENING_LOCK:
            _SCREENING_IDS.discard(proposal_id)


def _start_safety_screening(proposal_id: str) -> None:
    with _SCREENING_LOCK:
        if proposal_id in _SCREENING_IDS:
            return
        _SCREENING_IDS.add(proposal_id)
    try:
        threading.Thread(target=_screen_safety_proposal, args=(proposal_id,), daemon=True).start()
    except Exception:
        with _SCREENING_LOCK:
            _SCREENING_IDS.discard(proposal_id)
        raise


def _resume_safety_screening() -> None:
    path = _home() / "curate-memory" / "control-proposals.jsonl"
    try:
        proposals: dict[str, dict[str, Any]] = {}
        corrupt = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # One corrupt row must not strand every other proposal in `screening`.
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                corrupt.append(number)
                continue
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                proposals[row["id"]] = row
            else:
                corrupt.append(number)
        if corrupt:
            _alert(f"Skipped corrupt control proposal rows at {path} lines {corrupt}; the other proposals were resumed.")
    except FileNotFoundError:
        return
    except Exception as error:
        _alert(f"Could not resume safety control proposal screening: {type(error).__name__}: {error}")
        return
    for proposal_id, row in proposals.items():
        if row.get("status") == "screening":
            _start_safety_screening(proposal_id)


def _handle_safety_rule(entry: str, label: str, argument: str | None,
                        context: dict[str, Any]) -> dict[str, Any]:
    proposal_id = os.urandom(4).hex()
    path = _home() / "curate-memory" / "control-proposals.jsonl"
    row: dict[str, Any] = {
        "id": proposal_id, "at": _now(), "instance": _identity(),
        "session": context.get("session_id"), "text": entry, "status": "screening",
        "duplicate_of": None, "decision_reason": "", "decided_at": None,
    }
    _append_jsonl(path, row)
    try:
        _start_safety_screening(proposal_id)
    except Exception as error:
        _update_control_proposal(path, proposal_id, {
            "status": "pending-human", "decision_reason": f"Duplicate review could not be started; human review required ({type(error).__name__}).",
            "decided_at": _now(),
        })
        _alert(f"Safety control proposal {proposal_id} duplicate review could not be started; it is awaiting human review: {type(error).__name__}: {error}")
    return {"decision": "routed", "destination": str(path), "artifact": proposal_id,
            "message": f"Not saved to memory: sent to the control review queue as {proposal_id}."}


ROUTE_HANDLERS = {kind: _route for kind in ROUTE_KINDS}
ROUTE_HANDLERS["safety-rule"] = _handle_safety_rule


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
    _resume_safety_screening()
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
