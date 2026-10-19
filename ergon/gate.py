"""The context gate (ADR 0010): an agent's context is fixed by the run, not by its Hermes profile.

Every run passes --ignore-rules (no SOUL, AGENTS.md, memory or preloaded skills) and one toolset, ergon's read-only
wiki tool (ADR 0016), so nothing stored in the profile reaches the model. The profile holds only what the human sets
by hand: model, credentials, the entry that starts the wiki tool and the settings that trim Hermes' own system prompt. The skills an agent reads live in
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


# Hermes' own system prompt sections that do not fit a read-only agent answering in JSON: coding-agent posture
# (edit files, run tests, commit), "finish the job", tool-use pushes, the workspace snapshot, and a terminal hint
# replaced by one line. Without them Hermes adds about 2,900 characters instead of 8,800 (ADR 0017).
PROMPT_SETTINGS = """agent:
  coding_context: 'off'
  task_completion_guidance: false
  parallel_tool_call_guidance: false
  tool_use_enforcement: false
  execution_guidance: false
  environment_probe: false
  bot_mode_protocol: false
platform_hints:
  cli:
    replace: Code reads your final answer, not a person.
"""


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
    missing = [l.strip() for l in PROMPT_SETTINGS.splitlines() if ":" in l and not l.rstrip().endswith(":")
               and l.strip() not in {t.strip() for t in text.splitlines()}]
    if missing:
        raise SystemExit(f"Hermes profile {name!r} lets Hermes add coding-agent instructions. Merge this into {config}"
                         f" (missing: {', '.join(missing)}):\n\n{PROMPT_SETTINGS}")
