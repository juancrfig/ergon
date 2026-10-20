# 0011 · Model class per node

Status: accepted (2026-10-18); superseded in part by 0022

## Context
Each node's model is set by hand in its Hermes profile (ADR 0010). The choice needs a rule, not intuition.

## Decision
- frontier-reasoning: Plan, Build, Inspect, Learn. Their errors spread downstream, or they are the last defense.
- cheap-smart-enough: Intake, Split. Code checks almost all of their output.
- No model: Gate, Merge.

## Consequences
- A node moves to another class only when its metrics show the need, through a new ADR.
