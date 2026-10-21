# 0034. A list of checks every change must pass

Status: accepted, 2026-10-21.

## Context
A bug in one project (a form that kept its fields after a successful submit) is a class of mistake that can return in
any project. A verification skill proves what a ticket asks for; nothing carried the lessons from one ticket to the
next or to another project.

## Decision
- `agents/checks.md` is one flat list of general rules. No classes, no tags, no per-project parts. It is organized
  only when it grows.
- Rules are written without any name from the project that taught them, and so that the verification skill can drive
  and see them.
- Code puts the list in the builder's prompt right after the Build skill. The Build skill tells the builder to drive
  each rule that names something its change touches, through the verification skill, after its last edit.
- A bug fix adds a rule when the bug is a class that could return elsewhere. The human approves the line like any
  change to a skill (ADR 0002).

## Consequences
- The proof replay still checks criteria only. A check on the list is required by the prompt, not yet by code: if
  builders skip them in real runs, add the checks to the answer contract as proof steps.
- The list costs prompt tokens on every task; it stays short by keeping only rules that came from a real bug.
