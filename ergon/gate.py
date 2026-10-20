"""The context gate (ADR 0010): an agent's context is fixed by the run, not by its Hermes profile.

Every run passes --ignore-rules (no SOUL, AGENTS.md, memory or preloaded skills) and one toolset, ergon's read-only
wiki tool (ADR 0016), so nothing stored in the profile reaches the model. Before each run, code applies
ergon/hermes.yaml to the profile (ADR 0019); the human sets only the model and credentials. The skills an agent
reads live in agents/skills/ in this repo (ADR 0020).
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "ergon" / "hermes.yaml"
SKILLS = REPO / "agents" / "skills"
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


def _subkeys(lines: list) -> list:
    """Split one top-level block into (second-level key, lines); the key line itself has key None."""
    subs = [(None, [])]
    for line in lines[1:]:
        if line.startswith("  ") and line[2:3] not in (" ", "#", "-") and ":" in line:
            subs.append((line.split(":", 1)[0].strip(), []))
        subs[-1][1].append(line)
    return subs[1:]


def apply(name: str) -> Path:
    """Set every key ergon/hermes.yaml sets, down to the second level; keep every other key of the profile, so a
    hand-set value such as agent.reasoning_effort survives."""
    config = installed(name) / "config.yaml"
    profile = dict((k, l) for k, l in _blocks(config.read_text() if config.exists() else "") if k)
    out = []
    for k, lines in _blocks(CANONICAL.read_text()):
        if not k:
            continue
        ours = {sk for sk, _ in _subkeys(lines)}
        extra = [l for sk, ls in _subkeys(profile.pop(k, [])) if sk not in ours for l in ls]
        out.append("".join(lines).rstrip("\n") + "\n" + "".join(extra))
    kept = "".join("".join(l) for l in profile.values())
    config.write_text(kept.rstrip("\n") + "\n" + "".join(out))
    return config


def set_placeholder_model(name: str) -> None:
    """Give a new profile the SET-BY-HAND model, so no run starts on a model the human did not pick."""
    config = installed(name) / "config.yaml"
    text = config.read_text() if config.exists() else ""
    kept = "".join("".join(lines) for k, lines in _blocks(text) if k not in ("model", None))
    config.write_text(f"model:\n  default: {PLACEHOLDER}\n  provider: {PLACEHOLDER}\n" + kept)


def require(name: str) -> None:
    """Apply the canonical config, then refuse the run while the model is not set."""
    home = installed(name)
    if not home.exists():
        raise SystemExit(f"Hermes profile {name!r} does not exist. Run ./install, then set its model by hand:"
                         f" hermes -p {name} model")
    config = apply(name)
    text = config.read_text()
    if PLACEHOLDER in text or "model:" not in text:
        raise SystemExit(f"Hermes profile {name!r} has no model yet ({config}). Set the model and its credentials"
                         f" by hand: hermes -p {name} model")
