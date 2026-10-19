"""The context gate (ADR 0010): an agent's context is fixed by the run, not by its Hermes profile.

Every run passes --ignore-rules (no SOUL, AGENTS.md, memory or preloaded skills) and one toolset, ergon's read-only
wiki tool (ADR 0016), so nothing stored in the profile reaches the model. Before each run, code applies
profiles/hermes.yaml to the profile (ADR 0019); the human sets only the model and credentials. The skills an agent
reads live in profiles/<name>/skills/ in this repo.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "profiles" / "hermes.yaml"
TOOL = REPO / "ergon" / "wikitool.py"   # agent.py passes it to the profile as ${ERGON_TOOL}
PLACEHOLDER = "SET-BY-HAND"  # where a profile's model goes until the human picks one (ADR 0011)


def installed(name: str) -> Path:
    return Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes")) / "profiles" / name


def _blocks(text: str) -> list:
    """Split YAML into (top-level key, lines) blocks. Comments and blank lines stay with the block above them."""
    blocks = [(None, [])]
    for line in text.splitlines(keepends=True):
        if line[:1] not in ("", " ", "#", "\n", "\t") and ":" in line:
            blocks.append((line.split(":", 1)[0].strip(), []))
        blocks[-1][1].append(line)
    return blocks


def apply(name: str) -> Path:
    """Replace each top-level key of the profile's config that profiles/hermes.yaml sets; keep every other key."""
    config = installed(name) / "config.yaml"
    canonical = CANONICAL.read_text()
    keys = {k for k, _ in _blocks(canonical) if k}
    kept = "".join("".join(lines) for k, lines in _blocks(config.read_text() if config.exists() else "")
                   if k not in keys and k is not None)
    config.write_text(kept.rstrip("\n") + "\n" + "".join("".join(l) for k, l in _blocks(canonical) if k))
    return config


def require(name: str) -> None:
    """Apply the canonical config, then refuse the run while the model is not set."""
    home = installed(name)
    if not home.exists():
        raise SystemExit(f"Hermes profile {name!r} does not exist. Create it and set its model by hand:\n"
                         f"  hermes profile create {name} --no-skills --no-alias\n  hermes -p {name} model")
    config = apply(name)
    text = config.read_text()
    if PLACEHOLDER in text or "model:" not in text:
        raise SystemExit(f"Hermes profile {name!r} has no model yet ({config}). Set the model and its credentials"
                         f" by hand: hermes -p {name} model")
