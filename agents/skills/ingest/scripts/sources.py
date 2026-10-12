#!/usr/bin/env python3
"""List and mark processed wiki/raw source files without changing their contents."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
import sys

LEDGER_NAME = ".ingested.jsonl"


def raw_dir(project: Path) -> Path:
    if not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    raw = project / "wiki" / "raw"
    if not raw.is_dir():
        raise ValueError(f"Raw source directory does not exist: {raw}")
    return raw


def read_ledger(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid ledger JSON at {path}:{number}: {exc}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
            raise ValueError(f"Invalid ledger entry at {path}:{number}")
        rows.append(row)
    return rows


def pending(project: Path) -> list[str]:
    raw = raw_dir(project)
    recorded_hashes = {str(row["sha256"]) for row in read_ledger(raw / LEDGER_NAME)}
    files = sorted(path for path in raw.rglob("*") if path.is_file() and path.name != LEDGER_NAME)
    return [path.relative_to(raw).as_posix() for path in files
            if hashlib.sha256(path.read_bytes()).hexdigest() not in recorded_hashes]


def mark(project: Path, files: list[str], commit: str) -> None:
    raw = raw_dir(project)
    ledger = raw / LEDGER_NAME
    # Validate the existing ledger before appending to avoid extending corrupt state.
    read_ledger(ledger)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in files:
        source = Path(name)
        if source.is_absolute():
            try:
                source = source.resolve().relative_to(raw.resolve())
            except ValueError as exc:
                raise ValueError(f"Source is outside raw/: {name}") from exc
        path = (raw / source).resolve()
        try:
            relative = path.relative_to(raw.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError(f"Source is outside raw/: {name}") from exc
        if relative == LEDGER_NAME or not path.is_file():
            raise ValueError(f"Raw source does not exist or is the ledger: {name}")
        if relative in seen:
            continue
        seen.add(relative)
        rows.append({
            "file": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ingested": date.today().isoformat(),
            "commit": commit,
        })
    with ledger.open("a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pending_parser = commands.add_parser("pending", help="list raw sources whose content hash is unrecorded")
    pending_parser.add_argument("project_dir", type=Path)
    mark_parser = commands.add_parser("mark", help="record ingested sources after the wiki commit")
    mark_parser.add_argument("project_dir", type=Path)
    mark_parser.add_argument("files", nargs="+")
    mark_parser.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "pending":
            for name in pending(args.project_dir):
                print(name)
        else:
            mark(args.project_dir, args.files, args.commit)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
