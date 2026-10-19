"""The context gate (ADR 0010): an agent's context is fixed by the run, not by its Hermes profile.

Every run passes --ignore-rules (no SOUL, AGENTS.md, memory or preloaded skills) and one toolset, ergon's read-only
wiki tool (ADR 0016), so nothing stored in the profile reaches the model. The profile holds only what the human sets
by hand: model, credentials and the entry that starts the wiki tool. The skills an agent reads live in
profiles/<name>/skills/ in this repo.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def installed(name: str) -> Path:
    return Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes")) / "profiles" / name


TOOL = REPO / "ergon" / "wikitool.py"


def tool_entry() -> str:
    return (f"mcp_servers:\n  ergon:\n    command: python3\n    args:\n    - {TOOL}\n"
            "    - ${ERGON_RUN}\n")


def require(name: str) -> None:
    home = installed(name)
    if not home.exists():
        raise SystemExit(f"Hermes profile {name!r} does not exist. Create it and set its model by hand:\n"
                         f"  hermes profile create {name} --no-skills\n  hermes -p {name} model\n"
                         f"Then add the wiki tool to {home / 'config.yaml'}:\n\n{tool_entry()}")
    config = home / "config.yaml"
    text = config.read_text() if config.exists() else ""
    if str(TOOL) not in text or "${ERGON_RUN}" not in text:
        raise SystemExit(f"Hermes profile {name!r} does not start ergon's wiki tool. Add this to {config}"
                         f" (merge it into mcp_servers if the key exists):\n\n{tool_entry()}")
