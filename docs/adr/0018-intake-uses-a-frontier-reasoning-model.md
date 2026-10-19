# 0018 · Intake uses a frontier reasoning model

Status: accepted (2026-10-19). Modifies 0011.

## Context
ADR 0011 put Intake in cheap-smart-enough because code checks almost all of its output. Code checks the shape of a
proposal, not its content: whether a claim was understood, merged without loss, or marked as a contradiction.
Intake writes the wiki every later node reads, so its content errors spread downstream like Plan's.

## Decision
- Intake moves to frontier-reasoning. The human decided this before the first real run; there are no metrics yet.
- The human sets the model and its credentials by hand. Until then the profile's model is the placeholder
  `SET-BY-HAND`, and `gate.require` refuses to run it.

## Consequences
- Each Intake run costs more.
- Moving Intake back to a cheaper class needs a new ADR, ideally with run evidence that a cheaper model is enough.
