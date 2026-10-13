#!/usr/bin/env python3
"""Classify existing Hermes USER and MEMORY entries once, without moving them."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROUTE_LABELS = {"procedure", "project-fact", "safety-rule"}
MODEL = "gpt-6-luna"
PROVIDER = "openai-codex"


class BackfillError(RuntimeError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entries(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [part.strip("\r\n") for part in re.split(r"(?m)^§[ \t]*$", text) if part.strip()]


def read_document(path: Path, target: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "items": []}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackfillError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("items"), list):
        raise BackfillError(f"Invalid {target} metadata: expected version 1 and an items list in {path}")
    return value


def save_document(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def ask(entry: str, target: str) -> dict[str, Any]:
    prompt = (
        "Classify exactly one saved memory entry. Return only one JSON object with string fields "
        '"kind" and "reason", and boolean "uncertain". Use exactly one kind from: '
        "user-preference, user-fact, environment-fact, agent-convention, procedure, "
        "project-fact:<project>, safety-rule. A project-fact must name its project after the colon. "
        f"The entry currently resides in {target}; classify its meaning, not location. "
        "Set uncertain=true if evidence is insufficient or multiple kinds reasonably fit. "
        "A procedure, project-fact, or safety-rule is a route kind that must remain in place pending approval. "
        "Include a brief one-line reason.\nENTRY (literal):\n" + entry
    )
    try:
        completed = subprocess.run(
            ["hermes", "chat", "--oneshot", "--provider", PROVIDER, "--model", MODEL],
            input=prompt, text=True, capture_output=True, timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackfillError(f"Classifier invocation failed: {exc}") from exc
    if completed.returncode:
        raise BackfillError((completed.stderr or completed.stdout).strip() or f"Classifier exited {completed.returncode}")
    output = completed.stdout.strip()
    if output.startswith("```"):
        output = re.sub(r"^```(?:json)?\s*|\s*```$", "", output).strip()
    try:
        answer = json.loads(output)
    except json.JSONDecodeError as exc:
        raise BackfillError("Classifier returned invalid JSON") from exc
    kind, reason, uncertain = (answer.get("kind"), answer.get("reason"), answer.get("uncertain")) if isinstance(answer, dict) else (None, None, None)
    valid_kind = isinstance(kind, str) and (
        kind in {"user-preference", "user-fact", "environment-fact", "agent-convention", "procedure", "safety-rule"}
        or (kind.startswith("project-fact:") and bool(kind.split(":", 1)[1].strip()))
    )
    if not valid_kind or not isinstance(reason, str) or not reason.strip() or not isinstance(uncertain, bool):
        raise BackfillError("Classifier response must contain a canonical kind, one-line reason, and boolean uncertain")
    return {"kind": kind, "reason": " ".join(reason.split()), "uncertain": uncertain}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def send_summary(home: Path, summary: str) -> None:
    target = None
    try:
        for line in reversed((home / ".env").read_text(encoding="utf-8").splitlines()):
            key, separator, value = line.partition("=")
            if separator and key.strip().removeprefix("export ").strip() == "TELEGRAM_HOME_CHANNEL":
                target = value.strip().strip("\"'") or None
                break
    except OSError:
        pass
    if target:
        try:
            sent = subprocess.run(["hermes", "send", "--to", f"telegram:{target}", summary],
                                  text=True, capture_output=True, timeout=20, check=False)
            if sent.returncode == 0:
                return
            failure = sent.stderr.strip() or sent.stdout.strip() or f"exit status {sent.returncode}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            failure = str(exc)
    else:
        failure = "TELEGRAM_HOME_CHANNEL is not configured"
    try:
        append_jsonl(home / "curate-memory" / "alerts.jsonl", {
            "at": timestamp(), "instance": f"{socket.gethostname()}:{getpass_user()}",
            "message": summary, "delivery_error": failure,
        })
    except OSError:
        pass


def getpass_user() -> str:
    import getpass
    return getpass.getuser()


def classify(text: str, target: str) -> tuple[dict[str, Any], bool]:
    first, second = ask(text, target), ask(text, target)
    doubtful = first["uncertain"] or second["uncertain"] or first["kind"] != second["kind"]
    return first, doubtful


def backfill(home: Path, force: bool = False) -> dict[str, Any]:
    root = home / "memories"
    output: dict[str, Any] = {"status": "ok", "classified": {"USER": 0, "MEMORY": 0}, "doubtful": 0}
    doubtful_cases: list[str] = []
    for target in ("USER", "MEMORY"):
        metadata_path = root / f"{target}.json"
        document = read_document(metadata_path, target)
        if document.get("backfill_done") and not force:
            continue
        items = document["items"]
        indexed = {item.get("key"): item for item in items if isinstance(item, dict) and isinstance(item.get("key"), str)}
        for text in entries(root / f"{target}.md"):
            key = sha256_text(text)
            existing = indexed.get(key)
            if existing is not None and "kind" in existing:
                continue
            if existing is not None and isinstance(existing.get("text"), str) and existing["text"] != text:
                raise BackfillError(f"SHA-256 identity collision in {metadata_path}")
            choice, doubtful = classify(text, target)
            row = existing if existing is not None else {"key": key, "text": text}
            if not doubtful:
                row["kind"] = choice["kind"]
            else:
                row.pop("kind", None)
                row["proposed_kind"] = choice["kind"]
            row["classification_reason"] = choice["reason"]
            if not doubtful and choice["kind"].split(":", 1)[0] in ROUTE_LABELS:
                row["routing"] = "PROPOSED"
            if doubtful:
                row["classification_status"] = "doubtful"
                doubtful_cases.append(f"{target} ({key[:12]}): {text}\n  {choice['kind']}: {choice['reason']}")
            else:
                row.pop("classification_status", None)
            if existing is None:
                items.append(row)
                indexed[key] = row
            output["classified"][target] += 1
        document["items"] = items
        document["backfill_done"] = timestamp()
        save_document(metadata_path, document)
    output["doubtful"] = len(doubtful_cases)
    if doubtful_cases:
        summary = "Existing memory classification needs human review (no entries were moved):\n\n" + "\n\n".join(doubtful_cases)
        output["summary"] = summary
        send_summary(home, summary)
    else:
        output["summary"] = "No doubtful classifications."
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
    parser.add_argument("--force", action="store_true", help="classify entries lacking kind metadata again")
    args = parser.parse_args(argv)
    try:
        result = backfill(args.hermes_home.expanduser(), args.force)
    except BackfillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
