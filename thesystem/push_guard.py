"""Push guard: blocks a push to theSystem when its changes may reveal company data.

theSystem is a public repository. Every push from a clone runs this check through the clone's pre-push hook
(`agents/.harness/git-hooks/pre-push`).

1. System One (TypeSafe Jev) judges each changed file, and the commit messages, with one Choice question:
   "safe" or "leak". Each answer comes with a confidence.
2. A "safe" answer at or above the confidence threshold passes. A "leak" answer at or above it blocks.
3. Anything else (low confidence, or System One unavailable) goes to System Two: a fresh Hermes run with no
   tools and no workspace context, which returns a JSON verdict. A leak, an unreadable answer or an error blocks.

The guard fails closed: when it cannot reach a verdict, the push is blocked.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ZERO = "0" * 40
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
CONFIDENCE = float(os.environ.get("THESYSTEM_PUSH_GUARD_CONFIDENCE", "0.95"))
CHUNK_CHARS = 6000
SYSTEM_ONE_MODEL = "jev-1.13.0"
SYSTEM_ONE_BATCH = 16
SYSTEM_TWO_TIMEOUT = 180

DEFINITION = (
    "theSystem is a PUBLIC open-source repository: a generic framework of agent skills, rules and tools that any "
    "company installs. Its owner is Juanes Figueroa (GitHub juancrfig); his name, GitHub handle and noreply email are "
    "already public and are not a leak. Public tools and vendors (Hermes, TypeSafe, Jev, OpenAI, Anthropic, GitHub, "
    "Telegram, Tailscale, systemd and similar) are not a leak. Generic placeholders and invented examples are not "
    "a leak.\n"
    "A LEAK is text that reveals something specific about a real private company, client, customer, coworker or "
    "private person: their names, internal project or product names, internal hostnames, domains, IP addresses, "
    "emails, phone numbers, account ids, credentials or tokens, private file paths that name a company or person, "
    "business figures (prices, revenue, customer counts, contract terms), internal processes, or quotes from "
    "private conversations."
)


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()[-300:]}")
    return result.stdout


def find_workspace(repo: Path) -> Path | None:
    """The workspace holds the System One key (.env) and its Python runtime."""
    configured = git(repo, "config", "--get", "thesystem.workspace", check=False).strip() \
        or os.environ.get("THESYSTEM_WORKSPACE", "")
    if configured and Path(configured).is_dir():
        return Path(configured)
    # A project clone lives inside its workspace (<workspace>/<project>/<clone>).
    for parent in repo.resolve().parents:
        if (parent / ".thesystem" / "baseline").is_dir():
            return parent
    return None


def load_env(workspace: Path | None) -> None:
    if not workspace:
        return
    try:
        lines = (workspace / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def company_names(workspace: Path | None) -> list[str]:
    """Company command names on this machine, given to the models as context."""
    names = set()
    candidates = [workspace] if workspace else []
    for candidate in candidates:
        try:
            names.add(json.loads((candidate / ".thesystem" / "baseline" / "release.json").read_text())["company"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return sorted(name for name in names if isinstance(name, str) and name)


def pushed_ranges(repo: Path, lines: list[str]) -> list[tuple[str, str]]:
    ranges = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _, local_sha, _, remote_sha = parts
        if local_sha == ZERO:  # deleting a remote ref publishes nothing
            continue
        known = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{remote_sha}^{{commit}}"],
                               capture_output=True).returncode == 0
        if remote_sha == ZERO or not known:
            # New ref, or a remote commit we do not have: compare with what the remotes already published.
            base = git(repo, "merge-base", local_sha, "--all", *git(repo, "for-each-ref", "--format=%(objectname)",
                                                                       "refs/remotes").split(), check=False).split()
            remote_sha = base[0] if base else EMPTY_TREE
        ranges.append((remote_sha, local_sha))
    return ranges


def chunks_for(repo: Path, base: str, head: str) -> list[dict[str, str]]:
    """Added text per file, plus commit messages, split into model-sized chunks."""
    chunks: list[dict[str, str]] = []
    if base == EMPTY_TREE:
        messages = git(repo, "log", "--format=%an <%ae>%n%B", head)
    else:
        messages = git(repo, "log", "--format=%an <%ae>%n%B", f"{base}..{head}")
    # The pusher's own git identity is not company data, and the model kept flagging it: drop it before screening.
    own = f"{git(repo, 'config', 'user.name', check=False).strip()} <{git(repo, 'config', 'user.email', check=False).strip()}>"
    messages = "\n".join(line for line in messages.splitlines() if line.strip() != own)
    files = [name for name in git(repo, "diff", "--name-only", "-z", base, head).split("\0") if name]
    sources = [("commit messages", messages)]
    for name in files:
        diff = git(repo, "diff", "--unified=0", "--no-color", base, head, "--", name)
        added = "\n".join(line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        sources.append((name, added))
    for name, text in sources:
        if not text.strip():
            if name != "commit messages":
                chunks.append({"file": name, "text": "(file name only; no added text)"})
            continue
        for start in range(0, len(text), CHUNK_CHARS):
            chunks.append({"file": name, "text": text[start:start + CHUNK_CHARS]})
    return chunks


def system_one(chunks: list[dict[str, str]], companies: list[str]) -> list[dict[str, Any] | None]:
    """One Choice per chunk. None means System One gave no answer for that chunk."""
    if not os.environ.get("SYSTEM_ONE_API"):
        return [None] * len(chunks)
    try:
        from typesafe_sdk import Choice, TypeSafeClient
    except ImportError:
        return [None] * len(chunks)
    answers: list[dict[str, Any] | None] = [None] * len(chunks)
    for start in range(0, len(chunks), SYSTEM_ONE_BATCH):
        batch = list(enumerate(chunks))[start:start + SYSTEM_ONE_BATCH]
        state = {"company_names_on_this_machine": companies, "changes": [chunk for _, chunk in batch]}
        try:
            questions = {
                f"c{index}": Choice(
                    instructions={"definition": DEFINITION,
                                  "question": "Does the added text in `changes[" + str(position) + "]` contain a LEAK?"},
                    criteria={"safe": "No: everything in it is generic, public or about the repository owner.",
                              "leak": "Yes: it reveals something specific about a real private company, client or person."})
                for position, (index, _) in enumerate(batch)}
            with TypeSafeClient(api_key=os.environ["SYSTEM_ONE_API"], model=SYSTEM_ONE_MODEL) as client:
                response = client.system_one(state=state, questions=questions, model=SYSTEM_ONE_MODEL)
            for index, _ in batch:
                choice = response.choices[f"c{index}"]
                answers[index] = {"choice": str(choice.choice), "confidence": float(choice.confidence)}
        except Exception as error:  # an unavailable System One escalates; it never approves
            print(f"push guard: System One unavailable ({type(error).__name__}); using System Two", file=sys.stderr)
    return answers


def system_two(chunk: dict[str, str], companies: list[str]) -> dict[str, Any]:
    executable = shutil.which("hermes")
    if not executable:
        return {"leak": True, "evidence": "System Two unavailable: hermes CLI not found"}
    prompt = (
        "You screen a change before it is pushed to a public repository. Do not use tools, files or memory.\n"
        + DEFINITION + "\nCompany names on this machine: " + json.dumps(companies) + "\n"
        "Return ONLY a JSON object: {\"leak\": true|false, \"evidence\": \"the exact leaking text, or empty\"}.\n"
        "When unsure, answer leak true.\n\nFILE: " + chunk["file"] + "\nADDED TEXT:\n" + chunk["text"])
    command = [executable, "chat", "--oneshot", "--ignore-rules", "--toolsets", "todo", "--query-file", "-",
               "--max-turns", "2", "-Q"]
    if os.environ.get("THESYSTEM_SYSTEM_TWO_PROVIDER"):
        command += ["--provider", os.environ["THESYSTEM_SYSTEM_TWO_PROVIDER"]]
    if os.environ.get("THESYSTEM_SYSTEM_TWO_MODEL"):
        command += ["--model", os.environ["THESYSTEM_SYSTEM_TWO_MODEL"]]
    try:
        process = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=SYSTEM_TWO_TIMEOUT,
                                 check=False)
    except subprocess.TimeoutExpired:
        return {"leak": True, "evidence": "System Two timed out"}
    match = re.search(r"\{.*\}", process.stdout, re.S)
    try:
        verdict = json.loads(match.group(0)) if match else None
    except ValueError:
        verdict = None
    if process.returncode or not isinstance(verdict, dict) or not isinstance(verdict.get("leak"), bool):
        return {"leak": True, "evidence": "System Two gave no readable verdict: "
                + (process.stderr or process.stdout).strip()[-200:]}
    return {"leak": verdict["leak"], "evidence": str(verdict.get("evidence", ""))[:300]}


def screen(repo: Path, ref_lines: list[str]) -> int:
    workspace = find_workspace(repo)
    load_env(workspace)
    companies = company_names(workspace)
    chunks = [chunk for base, head in pushed_ranges(repo, ref_lines) for chunk in chunks_for(repo, base, head)]
    if not chunks:
        return 0
    first = system_one(chunks, companies)
    blocked: list[str] = []
    log: list[dict[str, Any]] = []
    for chunk, answer in zip(chunks, first):
        row: dict[str, Any] = {"file": chunk["file"], "system_one": answer}
        if answer and answer["confidence"] >= CONFIDENCE:
            row["verdict"] = answer["choice"]
            if answer["choice"] != "safe":
                blocked.append(f"{chunk['file']}: System One says leak ({answer['confidence']:.2f})")
        else:
            second = system_two(chunk, companies)
            row["system_two"] = second
            row["verdict"] = "leak" if second["leak"] else "safe"
            if second["leak"]:
                blocked.append(f"{chunk['file']}: {second['evidence'] or 'System Two says leak'}")
        log.append(row)
    if workspace:
        # The log records files and verdicts only, never the pushed text.
        path = workspace / ".agents" / "push-guard" / "log.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": str(repo),
                                     "blocked": bool(blocked), "checks": log}) + "\n")
    if blocked:
        print("push guard: PUSH BLOCKED. These changes may reveal company data:", file=sys.stderr)
        for item in blocked:
            print("  - " + item, file=sys.stderr)
        print("Remove the data, or ask the human to review the exact text.", file=sys.stderr)
        return 1
    print(f"push guard: {len(chunks)} part(s) screened, nothing found.", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screen a theSystem push for company data (pre-push hook).")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    repo = Path(git(Path(args.repo), "rev-parse", "--show-toplevel").strip())
    try:
        return screen(repo, sys.stdin.read().splitlines())
    except Exception as error:  # fail closed
        print(f"push guard: PUSH BLOCKED, the guard failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
