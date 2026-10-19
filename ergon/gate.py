"""The context gate (ADR 0006): an installed profile must match its definition in the ergon repo.

A profile is profiles/<name>/: config.yaml (copied verbatim into the Hermes profile) and skills/*.md (read by the
runner from this repo and placed in the prompt). The installed Hermes profile must hold no skills and no memory.
"""
import difflib
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def definition(name: str) -> Path:
    path = REPO / "profiles" / name
    if not (path / "config.yaml").exists():
        raise SystemExit(f"no profile definition at {path}")
    return path


def installed(name: str) -> Path:
    return Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes")) / "profiles" / name


def drift(name: str) -> list[str]:
    want, home = definition(name), installed(name)
    if not home.exists():
        return [f"profile {name!r} is not installed; run: ergon profile install {name}"]
    out = []
    expected, actual = (want / "config.yaml").read_text(), (home / "config.yaml")
    actual = actual.read_text() if actual.exists() else ""
    if expected != actual:
        diff = difflib.unified_diff(expected.splitlines(), actual.splitlines(), "ergon", "installed", lineterm="")
        out.append("config.yaml differs:\n" + "\n".join(diff))
    skills = sorted(str(p.relative_to(home)) for p in (home / "skills").rglob("SKILL.md")) if (home / "skills").exists() else []
    if skills:
        out.append(f"installed profile holds {len(skills)} skills; it must hold none: {', '.join(skills[:5])}")
    memories = [p.name for p in (home / "memories").glob("*") if p.is_file() and p.read_text().strip()] if (home / "memories").exists() else []
    if memories:
        out.append(f"installed profile holds memory: {', '.join(memories)}")
    return out


def require(name: str) -> None:
    problems = drift(name)
    if problems:
        raise SystemExit(f"context gate: profile {name!r} drifted from the ergon repo; the run did not start.\n\n"
                         + "\n\n".join(problems))


def install(name: str) -> None:
    """Create the Hermes profile (credentials cloned from the active profile), then make it match the repo."""
    want, home = definition(name), installed(name)
    if not home.exists():
        subprocess.run(["hermes", "profile", "create", name, "--clone", "--no-alias"], check=True)
    shutil.copyfile(want / "config.yaml", home / "config.yaml")
    for sub in ("skills", "memories"):
        if (home / sub).exists():
            shutil.rmtree(home / sub)
        (home / sub).mkdir()
    remaining = drift(name)
    if remaining:
        raise SystemExit("installed, but the gate still fails:\n" + "\n".join(remaining))
