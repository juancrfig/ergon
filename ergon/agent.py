"""Runs a node's agent: one Hermes profile, a context assembled by code, a JSON answer checked by code.

The agent gets no skills, memory, SOUL or AGENTS.md from Hermes (--ignore-rules) and one toolset: ergon's read-only
wiki tool (ADR 0016), scoped by code to one wiki. Every token it is given is in the prompt file saved in the run
folder; every page it reads is in the tool's call log.
"""
import json
import os
import re
import subprocess
from pathlib import Path

from ergon import schema


TOOLSET = "ergon"   # the MCP server name each profile gives ergon/wikitool.py
MAX_TURNS = 10      # a ceiling, not a target: a search and one read_pages call are the normal case


class AgentError(Exception):
    pass


def scope(run_dir: Path, pages_dir: Path, log: str = "tool-calls.jsonl") -> None:
    """Fix what the wiki tool may read in this run: one wiki's pages. The call log starts empty."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / log).write_text("")
    doc = {"pages": str(pages_dir.resolve()), "log": log}
    (run_dir / "tool-scope.json").write_text(json.dumps(doc, indent=2) + "\n")


def _call(profile: str, prompt: str, run_dir: Path, label: str) -> str:
    prompt_file = run_dir / f"{label}.prompt.md"
    prompt_file.write_text(prompt)
    cmd = ["hermes", "-p", profile, "chat", "-Q", "--oneshot", "--ignore-rules", "-t", TOOLSET,
           "--source", "tool", "--max-turns", str(MAX_TURNS), "--query-file", str(prompt_file)]
    env = {**os.environ, "ERGON_RUN": str(run_dir.resolve())}  # the wiki tool finds its scope through this
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=env)
    (run_dir / f"{label}.output.txt").write_text(result.stdout + ("\n--- stderr ---\n" + result.stderr if result.stderr else ""))
    if result.returncode != 0:
        raise AgentError(f"hermes exited {result.returncode}; see {run_dir / (label + '.output.txt')}")
    return result.stdout


def _extract(text: str):
    fenced = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
    raw = fenced[-1] if fenced else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def ask(profile: str, prompt: str, contract: Path, run_dir: Path, name: str, extra_check=None, retries: int = 2):
    """Ask until the answer satisfies the contract and extra_check, at most retries+1 times."""
    contract_schema = schema.load(contract)
    contract_text = json.dumps(contract_schema, indent=2)
    base = (f"{prompt}\n\n# Answer contract\nReturn exactly one JSON object, in one ```json block, that satisfies "
            f"this JSON Schema. Code checks it; anything else is rejected.\n\n```json\n{contract_text}\n```\n")
    current, errs = base, []
    for attempt in range(1, retries + 2):
        output = _call(profile, current, run_dir, f"{name}-{attempt}")
        try:
            data = _extract(output)
        except ValueError as exc:
            errs = [f"the answer is not one parseable JSON object: {exc}"]
        else:
            errs = schema.errors(data, contract_schema) or (extra_check(data) if extra_check else [])
        if not errs:
            (run_dir / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
            return data
        current = (base + "\n# Your previous answer was rejected\n" + "\n".join(f"- {e}" for e in errs)
                   + "\n\nPrevious answer:\n\n" + output[-20000:] + "\n\nReturn the corrected JSON only.\n")
    raise AgentError(f"{name}: no valid answer after {retries + 1} attempts: " + "; ".join(errs[:10]))
