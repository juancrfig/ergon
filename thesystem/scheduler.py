"""Deterministic five-minute Monitor scheduler."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTERVAL = re.compile(r"^([1-9][0-9]*)([mhd])$")
ENV_KEY = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
COMMAND_TIMEOUT = 60
HTTP_TIMEOUT = 15


def timestamp(now: float | None = None) -> str:
    return datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).isoformat()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False) + "\n")
        output.flush()
        os.fsync(output.fileno())


def read_dotenv(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ENV_KEY.match(line.strip())
        if match and match.group(1) in {"TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL"}:
            raw = match.group(2).strip()
            try:
                parsed = shlex.split(raw, comments=True, posix=True)
                values[match.group(1)] = parsed[0] if parsed else ""
            except ValueError:
                values[match.group(1)] = ""
    return values


def deliver_alert(home: Path, text: str, diagnostic_path: Path) -> bool:
    env = read_dotenv(home / ".env")
    token, chat = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_HOME_CHANNEL", "")
    if not token or not chat:
        append_jsonl(diagnostic_path, {"timestamp": timestamp(), "status": "failed",
                                       "reason": "Telegram credentials are missing"})
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat, "text": text}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            if response.status < 200 or response.status >= 300 or result.get("ok") is not True:
                raise ValueError("Telegram rejected the alert")
    except Exception as error:
        # URL-bearing urllib errors may contain the bot token; only the exception class is safe to persist.
        append_jsonl(diagnostic_path, {"timestamp": timestamp(), "status": "failed",
                                       "reason": type(error).__name__})
        return False
    append_jsonl(diagnostic_path, {"timestamp": timestamp(), "status": "sent"})
    return True


def git_revision(path: Path) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                                timeout=COMMAND_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def hermes_version(home: Path) -> str | None:
    revision = git_revision(home / "hermes-agent")
    if revision:
        return revision
    try:
        result = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=COMMAND_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if result.returncode == 0 and output else None


def interval_seconds(value: str) -> int:
    match = INTERVAL.fullmatch(value)
    if not match:
        raise ValueError("invalid interval")
    amount, unit = int(match.group(1)), match.group(2)
    return amount * {"m": 60, "h": 3600, "d": 86400}[unit]


def approvals_for(path: Path) -> dict[str, Any]:
    payload = load_json(path, {"contracts": {}})
    if not isinstance(payload, dict) or not isinstance(payload.get("contracts"), dict):
        raise ValueError("approval record must contain a contracts object")
    return payload["contracts"]


def run_check(check: dict[str, Any]) -> tuple[bool, str]:
    try:
        result = subprocess.run(check["command"], shell=True, executable="/bin/bash", capture_output=True, text=True,
                                timeout=COMMAND_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {COMMAND_TIMEOUT}s"
    except OSError as error:
        return False, f"could not start check ({type(error).__name__})"
    if result.returncode:
        return False, f"command exited with status {result.returncode}"
    return True, ""


def run(home: Path, thesystem_clone: Path) -> int:
    monitor = home / "monitor"
    contracts_dir = monitor / "contracts"
    versions_path = monitor / "versions.json"
    runs_path = monitor / "runs.json"
    approvals_path = monitor / "approvals.json"
    green_path = monitor / "green.jsonl"
    diagnostic_path = monitor / "alerts.jsonl"
    sent_path = monitor / "sent-alerts.json"
    now = time.time()
    instant = timestamp(now)
    errors = []

    previous_versions = load_json(versions_path, {})
    current_versions = {
        "hermes": hermes_version(home),
        "thesystem": git_revision(thesystem_clone),
    }
    version_state = {}
    events = set(previous_versions.get("pending_events", [])) if isinstance(previous_versions, dict) else set()
    for product, identifier in current_versions.items():
        previous = previous_versions.get(product, {}) if isinstance(previous_versions, dict) else {}
        old_identifier = previous.get("identifier") if isinstance(previous, dict) else None
        if identifier is None:
            errors.append(f"Could not detect {product} version")
            version_state[product] = previous if isinstance(previous, dict) else {"identifier": None}
        else:
            if old_identifier and old_identifier != identifier:
                events.add(f"{product}-update")
            version_state[product] = {"identifier": identifier, "detected_at": instant}
    version_state["pending_events"] = sorted(events)
    atomic_json(versions_path, version_state)

    approvals_readable = True
    try:
        approvals = approvals_for(approvals_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        approvals = {}
        approvals_readable = False
        errors.append(f"Cannot read Monitor approvals ({type(error).__name__})")

    contracts_readable = approvals_readable and contracts_dir.is_dir()
    contracts_valid = True
    event_checks = {event: set() for event in events}
    completed_event_checks = {event: set() for event in events}

    runs = load_json(runs_path, {})
    if not isinstance(runs, dict):
        runs = {}
        errors.append("Monitor run state is not a JSON object")
    sent_alerts = load_json(sent_path, {})
    if not isinstance(sent_alerts, dict):
        sent_alerts = {}

    if contracts_dir.is_dir():
        for contract_path in sorted(contracts_dir.glob("*.json")):
            try:
                raw = contract_path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                contract = json.loads(raw.decode("utf-8"))
                feature = contract["feature"]
                if not isinstance(feature, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", feature):
                    raise ValueError("invalid feature identifier")
                if contract_path.name != f"{feature}.json":
                    raise ValueError("contract filename does not match its feature")
                approval = approvals.get(feature)
                if not isinstance(approval, dict) or approval.get("sha256") != digest:
                    alert_key = f"contract:{feature}:{digest}"
                    if alert_key not in sent_alerts and deliver_alert(
                            home, f"Monitor approval mismatch: {feature}; checks skipped until re-approval.", diagnostic_path):
                        sent_alerts[alert_key] = instant
                    continue
                if not isinstance(contract.get("checks"), list) or not contract["checks"]:
                    raise ValueError("contract has no checks")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                contracts_valid = False
                errors.append(f"Invalid or unapproved Monitor contract ({type(error).__name__})")
                continue
            for check in contract["checks"]:
                try:
                    check_id = check["id"]
                    schedule = check["schedule"]
                    key = f"{feature}/{check_id}"
                    interval = schedule.get("interval")
                    event = schedule.get("event")
                    if event in event_checks:
                        event_checks[event].add(key)
                    last_run = runs.get(key)
                    due = bool(interval and (not isinstance(last_run, dict) or
                                              now - float(last_run.get("timestamp", 0)) >= interval_seconds(interval)))
                    triggered = bool(event and event in events)
                    if not (due or triggered):
                        continue
                    green, detail = run_check(check)
                    if event in completed_event_checks:
                        completed_event_checks[event].add(key)
                    runs[key] = {"timestamp": now, "status": "green" if green else "red"}
                    if green:
                        append_jsonl(green_path, {"timestamp": instant, "feature": feature, "check": check_id,
                                                  "status": "green"})
                    elif check.get("severity") in {"security", "data-loss"}:
                        alert_key = f"check:{key}:{hashlib.sha256(detail.encode()).hexdigest()}"
                        if alert_key not in sent_alerts and deliver_alert(
                                home, f"Monitor urgent check failure: {key} ({check['severity']}); {detail}",
                                diagnostic_path):
                            sent_alerts[alert_key] = instant
                except (KeyError, TypeError, ValueError) as error:
                    contracts_valid = False
                    errors.append(f"Invalid check in {feature} ({type(error).__name__})")

    if contracts_readable and contracts_valid:
        events = {event for event in events if event_checks[event] != completed_event_checks[event]}
    version_state["pending_events"] = sorted(events)
    atomic_json(versions_path, version_state)
    atomic_json(runs_path, runs)
    atomic_json(sent_path, sent_alerts)
    if errors:
        message = "Monitor scheduler error: " + "; ".join(errors[:10])
        error_key = "scheduler:" + hashlib.sha256(message.encode()).hexdigest()
        if error_key not in sent_alerts and deliver_alert(home, message, diagnostic_path):
            sent_alerts[error_key] = instant
            atomic_json(sent_path, sent_alerts)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()
    clone = Path(os.environ.get("THESYSTEM_CLONE") or Path.home() / "theSystem").expanduser()
    try:
        return run(home, clone)
    except Exception as error:
        safe_message = f"Monitor scheduler fatal error ({type(error).__name__})"
        monitor = home / "monitor"
        try:
            deliver_alert(home, safe_message, monitor / "alerts.jsonl")
        except Exception:
            pass
        print(safe_message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
