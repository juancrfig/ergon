# 0019 · One canonical Hermes config for node profiles

Status: accepted (2026-10-19). Amends 0010 and 0017. Installer and module renamed by ADR 0026.

## Context
After 0016 and 0017 a node profile needs a wiki tool entry and a dozen prompt settings. They lived as text inside
`ergon/gate.py`; `gate.require` compared the profile line by line and asked the human to paste in what was missing.
theSystem's main agent already solved this with a canonical config file the installer applies on every install.
ADR 0006 copied a whole config and refused runs on drift; 0010 dropped it so the human keeps model and credentials.

## Decision
- `profiles/hermes.yaml` is the canonical Hermes config for every node profile, in Hermes' own config shape. It
  never holds model, provider or credentials.
- Before each run, code applies it: every key it sets, down to the second level, replaces the profile's own; every
  other key stays: the model, the credentials and hand-set values such as `agent.reasoning_effort`. The file wins over hand edits, so nothing drifts and nothing is compared.
- The wiki tool path reaches the profile as `${ERGON_TOOL}`, set per run like `${ERGON_RUN}`, so the file holds no
  machine path.
- It also turns on Hermes' hard stop for replayed tool calls (CLI runs only warn by default) and sets context
  compression the same as theSystem's main agent.
- Every node applies it in `Node.run`, so a new node's agent gets it with no extra step.
- One file for all profiles while they are the same. A profile gets its own file only when it must differ.

## Consequences
- The human creates each profile and sets its model by hand; Ergon does the rest. A run is refused only while the
  profile is missing or its model is `SET-BY-HAND`.
- A profile setting changes through a commit to `profiles/hermes.yaml`, not by editing the profile.
