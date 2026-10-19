"""The context gate (ADR 0010): an agent's context is fixed by the run, not by its Hermes profile.

Every run passes --ignore-rules (no SOUL, AGENTS.md, memory or preloaded skills) and one harmless toolset (no
memory or skill tools), so nothing stored in the profile reaches the model. The profile holds only what the human
sets by hand: model and credentials. The skills an agent reads live in profiles/<name>/skills/ in this repo.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def installed(name: str) -> Path:
    return Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes")) / "profiles" / name


def require(name: str) -> None:
    if not installed(name).exists():
        raise SystemExit(f"Hermes profile {name!r} does not exist. Create it and set its model by hand:\n"
                         f"  hermes profile create {name} --no-skills\n  hermes -p {name} model")
