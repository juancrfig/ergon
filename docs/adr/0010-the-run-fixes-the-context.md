# 0010 · The run fixes the context; profiles hold only model and credentials

Status: accepted (2026-10-18). Supersedes 0006.

## Context
ADR 0006 copied a config file from the repo into each Hermes profile and refused runs when it drifted. The human
wants to set each node's model by hand, and ADR 0008 already keeps every profile file out of the agent's context.

## Decision
- The context gate is the run itself: `--ignore-rules`, one harmless toolset, and a prompt built by code (ADR 0008).
- Ergon does not install or compare profiles. The human creates each profile (`--no-skills`) and sets its model and
  credentials by hand.
- Ergon refuses a run only when the profile does not exist.

## Consequences
- No profile drift to manage, no copied API keys.
- The model each node uses is not recorded in the repo.
- Residual risk: a Hermes setting that injects prompt text even with `--ignore-rules` would reach the agent unseen.
