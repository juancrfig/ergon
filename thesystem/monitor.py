"""Human approval and installation of Monitor health-check contracts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from thesystem.errors import CodedError

FEATURE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEVERITIES = {"normal", "security", "data-loss"}
EVENTS = {"hermes-update", "thesystem-update"}
# The scheduler ticks every 5 minutes, so intervals are at least 5m, or whole hours or days.
INTERVAL = re.compile(r"^(?:[1-9][0-9]*[hd]|(?:[5-9]|[1-9][0-9]+)m)$")


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise CodedError("INVALID_CONTRACT", message)


def validate_contract(contract: Any) -> dict[str, Any]:
    _require(isinstance(contract, dict), "contract must be a JSON object")
    name = contract.get("feature")
    _require(isinstance(name, str) and FEATURE_NAME.fullmatch(name) is not None,
             "feature must be a lowercase hyphenated name")
    checks = contract.get("checks")
    _require(isinstance(checks, list) and checks, "checks must be a non-empty array")
    ids: set[str] = set()
    for check in checks:
        _require(isinstance(check, dict), "each check must be an object")
        check_id = check.get("id")
        _require(isinstance(check_id, str) and check_id and check_id not in ids,
                 "check ids must be non-empty and unique")
        ids.add(check_id)
        _require(isinstance(check.get("command"), str) and check["command"].strip(),
                 f"check {check_id} needs a command")
        schedule = check.get("schedule")
        _require(isinstance(schedule, dict), f"check {check_id} needs a schedule object")
        interval = schedule.get("interval")
        event = schedule.get("event")
        _require(len(schedule) == 1 and ((isinstance(interval, str) and INTERVAL.fullmatch(interval) is not None)
                                         or isinstance(event, str) and event in EVENTS),
                 f"check {check_id} schedule must have an interval like 15m, 6h or 1d, or an allowed event tag")
        severity = check.get("severity")
        _require(isinstance(severity, str) and severity in SEVERITIES,
                 f"check {check_id} severity must be normal, security, or data-loss")
    safe_state = contract.get("safe_state")
    _require(isinstance(safe_state, dict) and len(safe_state) == 2
             and (isinstance(safe_state.get("command"), str) and safe_state["command"].strip()
                  or isinstance(safe_state.get("switch"), str) and safe_state["switch"].strip())
             and isinstance(safe_state.get("description"), str) and safe_state["description"].strip(),
             "safe_state must have exactly one command or switch and a description")
    fixes = contract.get("approved_fixes")
    _require(isinstance(fixes, list) and all(isinstance(fix, str) and fix.strip() for fix in fixes),
             "approved_fixes must be an array of non-empty strings")
    sampling = contract.get("sampling")
    _require(isinstance(sampling, dict)
             and isinstance(sampling.get("what"), str) and sampling["what"].strip()
             and isinstance(sampling.get("sample_size"), int) and not isinstance(sampling["sample_size"], bool)
             and sampling["sample_size"] > 0
             and isinstance(sampling.get("working_well"), str) and sampling["working_well"].strip(),
             "sampling needs what, a positive integer sample_size, and working_well")
    return contract


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def approve(source: Path, hermes_home: Path) -> dict:
    try:
        raw = source.expanduser().read_bytes()
    except OSError as error:
        raise CodedError("CONTRACT_READ_FAILED", str(error)) from error
    try:
        contract = validate_contract(json.loads(raw.decode("utf-8")))
    except UnicodeDecodeError as error:
        raise CodedError("INVALID_CONTRACT", f"contract is not UTF-8: {error}") from error
    except json.JSONDecodeError as error:
        raise CodedError("INVALID_CONTRACT", f"invalid JSON: {error}") from error
    digest = hashlib.sha256(raw).hexdigest()
    feature = contract["feature"]
    monitor_dir = hermes_home / "monitor"
    contracts_dir = monitor_dir / "contracts"
    destination = contracts_dir / f"{feature}.json"
    try:
        existing = json.loads((monitor_dir / "approvals.json").read_text(encoding="utf-8")) \
            if (monitor_dir / "approvals.json").is_file() else {"contracts": {}}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CodedError("INVALID_APPROVALS", f"approvals.json is unreadable: {error}") from error
    _require(isinstance(existing, dict) and isinstance(existing.get("contracts"), dict),
             "approvals.json must contain a contracts object")
    contracts = existing["contracts"]
    contracts[feature] = {"sha256": digest}
    contracts_dir.mkdir(parents=True, exist_ok=True)
    temporary = contracts_dir / f".{feature}.json.tmp"
    temporary.write_bytes(raw)
    os.replace(temporary, destination)
    _atomic_json(monitor_dir / "approvals.json", {"contracts": contracts})
    return {"status": "ok", "feature": feature, "sha256": digest,
            "contract": str(destination), "approvals": str(monitor_dir / "approvals.json")}
