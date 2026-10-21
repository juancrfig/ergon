"""The builder's proof that a task is done, replayed by code (ADR 0033).

Each source clone has a verification skill in VERIFY: SKILL.md (how to start, drive, inspect and stop the app) and
FEATURES.md (the feature map). For every criterion it covers, the builder answers with the steps it ran. Code replays
them in a clean copy of the task's repos, holding exactly what would be committed, so a proof the builder did not
really run, or one that only held because of files it left lying around, fails like any other check.
"""
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

VERIFY = ".agents/skills/verify"
FILES = ("SKILL.md", "FEATURES.md")
STEP_SECONDS = 120


def missing(roots: dict) -> list[str]:
    """Verification files absent from the given source clones, as <repo>/<path>."""
    return [f"{name}/{VERIFY}/{f}" for name, root in roots.items() for f in FILES if not (root / VERIFY / f).exists()]


def skill_text(name: str, root: Path) -> str:
    return "\n\n".join(f"# {name}/{VERIFY}/{f}\n\n{(root / VERIFY / f).read_text().strip()}" for f in FILES)


def _copy(roots: dict, into: Path) -> None:
    """Every file git would commit now (tracked and new, not ignored), and nothing else."""
    for name, root in roots.items():
        listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard"],
                                capture_output=True, text=True, check=True).stdout.split("\0")
        for rel in filter(None, listed):
            source, target = root / rel, into / name / rel
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)


def _run(step: dict, project: Path) -> tuple[int | None, str]:
    """Run one step in its own process group, so a timeout also ends any server it started."""
    proc = subprocess.Popen(step["run"], shell=True, cwd=project / step["repo"], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=STEP_SECONDS)
        return proc.returncode, output
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        output, _ = proc.communicate()
        return None, output


def replay(reports: list, roots: dict) -> tuple[list[str], list[dict]]:
    """Replay every criterion's steps, each criterion in its own clean copy. Returns the problems and the record."""
    problems, record = [], []
    for report in reports:
        criterion = report["criterion"]
        with tempfile.TemporaryDirectory(prefix="ergon-proof-") as tmp:
            project = Path(tmp)
            _copy(roots, project)
            for n, step in enumerate(report["proof"], 1):
                where = f"proof of {criterion}, step {n} (`{step['run']}` in {step['repo']})"
                if step["repo"] not in roots:
                    problems.append(f"{where}: {step['repo']} is not one of this task's repos")
                    break
                code, output = _run(step, project)
                absent = [line for line in step["contains"] if line not in output]
                record.append({"criterion": criterion, "step": n, **step, "exit_code": code,
                               "missing": absent, "output": output[-4000:]})
                if code is None:
                    problems.append(f"{where}: still running after {STEP_SECONDS} s; stop what it starts")
                elif code != step["exit"]:
                    problems.append(f"{where}: exited {code}, the proof expects {step['exit']}. Output, end:\n"
                                    + output[-800:])
                elif absent:
                    problems.append(f"{where}: the output lacks " + "; ".join(repr(l) for l in absent)
                                    + ". Output, end:\n" + output[-800:])
                if problems and problems[-1].startswith(where):
                    break   # later steps depend on this one
    return problems, record
