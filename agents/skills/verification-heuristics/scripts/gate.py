#!/usr/bin/env python3
"""Run a project's verification gate and report every error in full, for an agent to act on.

The project declares its gate in `gate.json` (in its verification guide, `verify-<project>/gate.json`):

    {"setup": [{"name": "install", "cwd": "app", "run": "pnpm install --frozen-lockfile"}],
     "steps": [{"name": "typecheck-server", "cwd": "app", "run": "pnpm exec tsc --noEmit -p tsconfig.json"}]}

`cwd` is relative to --root (the worktree). Setup must pass before any step runs; every step then runs even when an
earlier one fails, so the agent sees all errors in one round. Exit code: 0 green, 1 red, 2 setup or config failure.

Usage:
    gate.py GATE_JSON --root WORKTREE [--log DIR] [--save-errors FILE] [--baseline FILE] [--max-chars N]

--save-errors writes the error signatures of this run (the orchestrator runs it on the base commit).
--baseline reads such a file and marks each error line as [new] (caused by the change) or [old] (already there).
"""
import argparse, json, re, subprocess, sys, time
from collections import Counter
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
ERROR = re.compile(r"\berror\b|\bError:|^E\s|SyntaxError|TypeError", re.I)
LOCATION = re.compile(r"([\w./@-]+\.(?:[cm]?[jt]sx?|py|vue|svelte|css|json))(?:[(:]\d+(?:[,:]\d+)?\)?)?")
STEP_TIMEOUT = 300


def clean(text: str) -> str:
    return ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "\n")


def signature(step: str, line: str, root: str) -> str:
    # Line and column move when unrelated code changes above; the file, code and message identify the error.
    line = line.replace(root, "").strip()
    line = re.sub(r"[(:]\d+(?:[,:]\d+)?\)?", "", line)
    return f"{step}|{re.sub(r'\s+', ' ', line)}"


def run(step: dict, root: Path) -> dict:
    start = time.monotonic()
    try:
        proc = subprocess.run(step["run"], shell=True, cwd=root / step.get("cwd", "."), capture_output=True,
                              text=True, timeout=step.get("timeout", STEP_TIMEOUT))
        output, code = clean(proc.stdout + proc.stderr), proc.returncode
    except subprocess.TimeoutExpired as exc:
        output = clean((exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        output += f"\n[gate] step timed out after {exc.timeout}s"
        code = 124
    return {"name": step["name"], "run": step["run"], "cwd": step.get("cwd", "."), "code": code,
            "seconds": round(time.monotonic() - start, 1), "output": output}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gate_json"); ap.add_argument("--root", required=True)
    ap.add_argument("--log"); ap.add_argument("--save-errors"); ap.add_argument("--baseline")
    ap.add_argument("--max-chars", type=int, default=20000)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        gate = json.loads(Path(args.gate_json).read_text())
    except (OSError, ValueError) as exc:
        print(f"GATE CONFIG ERROR: cannot read {args.gate_json}: {exc}")
        return 2
    log_dir = Path(args.log) if args.log else root / ".gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    for step in gate.get("setup", []):
        result = run(step, root)
        if result["code"]:
            (log_dir / "gate-full.log").write_text(result["output"])
            print(f"GATE SETUP FAILED: {result['name']} (`{result['run']}` in {result['cwd']}, exit {result['code']})")
            print("This is an environment problem, not a code error. Output (tail):\n")
            print(result["output"][-args.max_chars:])
            return 2

    results = [run(step, root) for step in gate["steps"]]
    baseline = Counter(json.loads(Path(args.baseline).read_text())) if args.baseline else None
    signatures, remaining = [], Counter(baseline or {})
    for result in results:
        errors, files, marked = 0, set(), []
        for line in result["output"].split("\n"):
            if ERROR.search(line):
                errors += 1
                files.update(m.group(1) for m in LOCATION.finditer(line.replace(str(root) + "/", "")))
                sig = signature(result["name"], line, str(root) + "/")
                signatures.append(sig)
                if baseline is not None:
                    old = remaining[sig] > 0
                    remaining[sig] -= old
                    result.setdefault("new", 0)
                    result["new"] += not old
                    line = ("[old] " if old else "[new] ") + line
            marked.append(line)
        result["output"], result["errors"], result["files"] = "\n".join(marked), errors, sorted(files)

    full = "\n\n".join(f"===== {r['name']} | `{r['run']}` in {r['cwd']} | exit {r['code']} | {r['seconds']}s =====\n"
                       f"{r['output']}" for r in results)
    full_path = log_dir / "gate-full.log"
    full_path.write_text(full)
    if args.save_errors:
        Path(args.save_errors).write_text(json.dumps(signatures))

    red = [r for r in results if r["code"]]
    print(f"GATE {'RED' if red else 'GREEN'}: {len(red)} of {len(results)} steps failed.")
    for r in results:
        state = "FAIL" if r["code"] else "ok"
        extra = ""
        if r["code"]:
            extra = f", {r['errors']} error lines"
            if baseline is not None:
                extra += f" ({r.get('new', 0)} new, {r['errors'] - r.get('new', 0)} already on the base commit)"
            if r["files"]:
                extra += f", files: {', '.join(r['files'][:15])}" + (" ..." if len(r["files"]) > 15 else "")
        print(f"  {state:4} {r['name']} (exit {r['code']}, {r['seconds']}s{extra})")
    if not red:
        return 0
    print(f"\nRe-run: gate.py {args.gate_json} --root {root}")
    print(f"Full output: {full_path}\n")
    budget = args.max_chars
    for r in red:
        block = f"===== {r['name']} | `{r['run']}` in {r['cwd']} | exit {r['code']} =====\n{r['output'].strip()}\n"
        if len(block) > budget:
            block = block[:max(budget, 0)] + f"\n[gate] output cut here; the rest is in {full_path}\n"
        print(block)
        budget -= len(block)
        if budget <= 0:
            print(f"[gate] remaining failed steps are only in {full_path}")
            break
    return 1


if __name__ == "__main__":
    sys.exit(main())
