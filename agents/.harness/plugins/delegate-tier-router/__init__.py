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
