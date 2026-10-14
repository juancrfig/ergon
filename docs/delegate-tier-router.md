# Deterministic subagent delegation with a Hermes hook (tier router)

## What it does

The main agent never chooses which model does delegated work. A hook decides, in code, using three tiers:

1. **Tier 1 – `agy` pool (Gemini 3.8 Flash, medium).** Cheapest. While it has usage left, the hook **blocks** `delegate_task` and tells the agent to run the work through a command-line pool (`agy-pool`) instead.
2. **Tier 2 – Luna 6** (`openai-codex` / `gpt-6-luna`). Used when tier 1 is exhausted.
3. **Tier 3 – Haiku 5.5** (`anthropic` / `claude-haiku-5-5`). Used when Luna is also exhausted.

Why "deterministic": the choice depends only on two timestamps in a state file, not on the agent's judgment or prompt. The agent cannot skip the cheap tier. A prompt rule can be ignored; a blocked tool call cannot.

## Parts

| Part | Where | Role |
|---|---|---|
| Plugin `delegate-tier-router` | `~/.hermes/plugins/delegate-tier-router/` (`plugin.yaml` + `__init__.py`) | Two hooks: `pre_tool_call` and `transform_tool_result` |
| `agy-pool` | `~/.local/bin/agy-pool` (executable Python) | Runs `agy` workers detached, 3 in parallel, and marks tier 1 exhausted on a usage limit |
| State file | `~/.hermes/agy-pool/tiers.json` | `agy_exhausted_until`, `luna_exhausted_until` (Unix times) |
| Config | `~/.hermes/config.yaml` | `delegation:` block (provider/model) that the plugin rewrites; `plugins.enabled` lists `delegate-tier-router` |

## Flow

1. The agent calls `delegate_task`.
2. `pre_tool_call` runs. If `agy_exhausted_until` is in the past (agy still has usage), it returns `{"action": "block", "message": ...}`. The message tells the agent to write a self-contained prompt file and run `agy-pool run --name X --workdir DIR --prompt-file FILE`.
3. `agy-pool run` copies the prompt, starts a detached worker, and returns at once. The worker waits for one of 3 file locks (slots), then runs `agy -p <prompt> --model gemini-3.8-flash-medium --dangerously-skip-permissions --print-timeout 45m` in the given working directory. Output goes to `~/.hermes/agy-pool/jobs/X/out.md`, status to `meta.json`.
4. If a job exits non-zero and its last 4,000 characters match a usage-limit pattern (quota, 429, rate limit, out of credits…), the worker writes `agy_exhausted_until = now + 1h`.
5. Next `delegate_task`: agy is marked exhausted, so the hook lets the call pass. Before it passes, the hook rewrites the `delegation:` model in `config.yaml` (Hermes reads it on every delegate call): Luna if available, else Haiku.
6. `transform_tool_result` watches delegate results. If the result shows a usage-limit error while Luna is the active model, it marks Luna exhausted for 1h and switches to Haiku.
7. Marks expire after 1 hour, so the tiers recover alone. `agy-pool reset` clears them by hand.

## How to install

With theSystem: the installer copies the plugin and `agy-pool`, and enables the plugin only when the `agy` command exists. Manual steps:

1. Install the `agy` CLI and log in (this is the Google/Gemini coding agent CLI; it must accept `-p`, `--model`, `--dangerously-skip-permissions`, `--print-timeout`). Adjust the command in `agy-pool` if yours differs.
2. Copy `agy-pool` to `~/.local/bin/` and `chmod +x`.
3. Create the plugin folder with the two files below.
4. In `config.yaml`: add `delegation:` with `provider`, `model` (any starting values; the plugin rewrites them) and add `delegate-tier-router` to `plugins.enabled`.
5. Restart Hermes (hooks load at start).
6. Test: `agy-pool tiers` should print both tiers "available". Ask the agent to delegate; the call should be blocked with the pool message. Then run `agy-pool run` with a trivial prompt.

## Behaviour you should know

- The router edits `config.yaml` itself (atomic write). Do not keep hand-edits in the `delegation:` block; the plugin overwrites provider and model.
- Tier 1 detects exhaustion only **after** a job fails. One job is lost to discover the limit.
- The block is global to the `delegate_task` tool; a request to use a specific model (for example Opus) cannot be honored while tier 1 is available. To allow another model, add an exception in `_pre_tool_call` (for example, check a flag in the task arguments).
- Limit patterns are regexes; tune `LIMIT_RE` to your providers' wording.
- Direction: today the only pool member is `agy`. The plan is to grow this into a pool of harnesses, each with its own models, slots and exhaustion marks, behind the same blocking hook.

## Files

### `plugin.yaml`
```yaml
name: delegate-tier-router
version: "1.0.0"
description: "Routes delegate_task by tier: agy pool first, then Luna 6, then Haiku 5.5."
provides_hooks:
  - pre_tool_call
  - transform_tool_result
```

### `__init__.py`
```python
"""Tiered delegation: agy (Gemini 3.8 Flash medium) -> Luna 6 -> Haiku 5.5.

Tier 1 is enforced by blocking delegate_task while agy is not marked exhausted; the block message tells the
agent to use `agy-pool run`. agy-pool marks agy exhausted when a job dies on a usage limit. Tier 2/3 are chosen
by rewriting the delegation model in config.yaml (read on every delegate call). Luna is marked exhausted when a
delegate result shows a usage-limit error; marks expire after an hour so the tiers recover on their own.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE = HOME / "agy-pool" / "tiers.json"
CONFIG = HOME / "config.yaml"
COOLDOWN = 3600
LUNA = ("openai-codex", "gpt-6-luna")
HAIKU = ("anthropic", "claude-haiku-5-5")
LIMIT_RE = re.compile(r"usage limit|quota|rate.?limit|resource.?exhausted|too many requests|\b429\b|insufficient|out of credits|credit balance", re.I)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _mark(key: str) -> None:
    s = _state()
    s[key] = time.time() + COOLDOWN
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s))
    tmp.replace(STATE)


def _available(key: str) -> bool:
    return _state().get(key, 0) < time.time()


def _current() -> tuple[str | None, str | None]:
    text = CONFIG.read_text()
    m = re.search(r"^delegation:\n((?:[ \t]+.*\n|\n)*)", text, re.M)
    if not m:
        return None, None
    block = m.group(1)
    prov = re.search(r"^[ \t]+provider:[ \t]*(\S+)", block, re.M)
    mod = re.search(r"^[ \t]+model:[ \t]*(\S+)", block, re.M)
    return (prov.group(1) if prov else None), (mod.group(1) if mod else None)


def _set_model(target: tuple[str, str]) -> None:
    if _current() == target:
        return
    text = CONFIG.read_text()
    m = re.search(r"^delegation:\n((?:[ \t]+.*\n|\n)*)", text, re.M)
    if not m:
        return
    block = m.group(1)
    block = re.sub(r"^([ \t]+provider:[ \t]*)\S+", rf"\g<1>{target[0]}", block, flags=re.M)
    block = re.sub(r"^([ \t]+model:[ \t]*)\S+", rf"\g<1>{target[1]}", block, flags=re.M)
    tmp = CONFIG.with_suffix(".yaml.tmp")
    tmp.write_text(text[: m.start(1)] + block + text[m.end(1):])
    tmp.replace(CONFIG)


def _pre_tool_call(**kw):
    if kw.get("tool_name") != "delegate_task":
        return None
    if _available("agy_exhausted_until"):
        return {"action": "block", "message": (
            "Delegation tier 1 is agy (Gemini 3.8 Flash, medium), and agy still has usage. Do not use delegate_task. "
            "Write each task as a self-contained prompt file (include the task's rules and acceptance criteria), then run "
            "`agy-pool run --name <task-id> --workdir <git worktree> --prompt-file <file>` in the terminal. It runs detached, "
            "3 in parallel; read the result in ~/.hermes/agy-pool/jobs/<task-id>/out.md (`agy-pool status`). "
            "If agy hits its usage limit, the pool marks it exhausted and delegate_task opens automatically on Luna 6, then Haiku 5.5."
        )}
    try:
        _set_model(LUNA if _available("luna_exhausted_until") else HAIKU)
    except Exception:
        pass
    return None


def _transform_tool_result(**kw):
    if kw.get("tool_name") != "delegate_task":
        return None
    result = kw.get("result")
    if not isinstance(result, str) or not LIMIT_RE.search(result):
        return None
    try:
        if _current() == LUNA:
            _mark("luna_exhausted_until")
            _set_model(HAIKU)
    except Exception:
        pass
    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("transform_tool_result", _transform_tool_result)
```

### `agy-pool`
```python
#!/usr/bin/env python3
"""agy worker pool: Gemini 3.8 Flash (medium) workers, N in parallel, detached.

  agy-pool run --name NAME --workdir DIR --prompt-file FILE   start (queues if pool full), returns at once
  agy-pool status [NAME]                                      list jobs / show one
  agy-pool tiers                                              show which delegation tier is active
  agy-pool reset [agy|luna|all]                               clear exhausted marks
Results: ~/.hermes/agy-pool/jobs/NAME/{prompt.md,out.md,meta.json}
"""
import argparse, fcntl, json, os, re, subprocess, sys, time
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
ROOT = HOME / "agy-pool"
JOBS = ROOT / "jobs"
STATE = ROOT / "tiers.json"
MODEL = "gemini-3.8-flash-medium"
SLOTS = 3
TIMEOUT = "45m"
LIMIT_RE = re.compile(r"usage limit|quota|rate.?limit|resource.?exhausted|too many requests|\b429\b|exceeded|out of (credits|usage)", re.I)
COOLDOWN = 3600


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(s):
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s))
    tmp.replace(STATE)


def mark(key, seconds=COOLDOWN):
    s = load_state()
    s[key] = time.time() + seconds
    save_state(s)


def write_meta(d, **kw):
    p = d / "meta.json"
    m = json.loads(p.read_text()) if p.exists() else {}
    m.update(kw)
    p.write_text(json.dumps(m, indent=1))


def worker(name):
    d = JOBS / name
    meta = json.loads((d / "meta.json").read_text())
    ROOT.mkdir(parents=True, exist_ok=True)
    # wait for a free slot
    while True:
        for i in range(SLOTS):
            f = open(ROOT / f"slot{i}.lock", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                f.close()
        else:
            time.sleep(5)
            continue
        break
    write_meta(d, status="running", started=time.time())
    prompt = (d / "prompt.md").read_text()
    try:
        p = subprocess.run(
            ["agy", "-p", prompt, "--model", MODEL, "--dangerously-skip-permissions", "--print-timeout", TIMEOUT],
            cwd=meta["workdir"], capture_output=True, text=True,
        )
        out = (p.stdout or "") + ("\n[stderr]\n" + p.stderr if p.stderr.strip() else "")
        code = p.returncode
    except Exception as e:
        out, code = f"launcher error: {e}", 1
    (d / "out.md").write_text(out)
    limited = code != 0 and bool(LIMIT_RE.search(out[-4000:]))
    if limited:
        mark("agy_exhausted_until")
    write_meta(d, status="limit" if limited else ("done" if code == 0 else "failed"), exit=code, ended=time.time())


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--name", required=True); r.add_argument("--workdir", required=True); r.add_argument("--prompt-file", required=True)
    w = sub.add_parser("_worker"); w.add_argument("name")
    s = sub.add_parser("status"); s.add_argument("name", nargs="?")
    sub.add_parser("tiers")
    z = sub.add_parser("reset"); z.add_argument("which", nargs="?", default="all")
    a = ap.parse_args()
    if a.cmd == "run":
        d = JOBS / a.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "prompt.md").write_text(Path(a.prompt_file).read_text())
        write_meta(d, status="queued", workdir=str(Path(a.workdir).resolve()), model=MODEL, created=time.time())
        subprocess.Popen([sys.executable, __file__, "_worker", a.name], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print(f"queued {a.name} -> {d}/out.md (status: agy-pool status {a.name})")
    elif a.cmd == "_worker":
        worker(a.name)
    elif a.cmd == "status":
        names = [a.name] if a.name else sorted(p.name for p in JOBS.glob("*")) if JOBS.exists() else []
        for n in names:
            m = json.loads((JOBS / n / "meta.json").read_text())
            print(n, m.get("status"), f"exit={m.get('exit')}", m.get("workdir"))
    elif a.cmd == "tiers":
        s = load_state(); now = time.time()
        for k in ("agy_exhausted_until", "luna_exhausted_until"):
            print(k, "available" if s.get(k, 0) < now else f"exhausted for {int(s[k]-now)}s")
    elif a.cmd == "reset":
        s = load_state()
        for k in ("agy_exhausted_until", "luna_exhausted_until"):
            if a.which in ("all", k.split("_")[0]):
                s.pop(k, None)
        save_state(s)


main()
```
