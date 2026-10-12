---
name: curate-memory
description: "Use when reviewing or curating pending memory or skill writes. Approved rules decide clear cases; the human decides the rest, one at a time."
---

# Curate memory

Use this skill at the start of a new conversation to review pending writes for
`memory` and `skills` in the main agent's Hermes profile (`default`). It does not create or maintain another queue.

The goal is automatic curation. Human-approved rules (the sweep and R1–R6) decide clear cases
without asking; every other request goes to the human, one at a time. Each rule the human approves
removes one kind of question.

## Evaluators

Each criterion in `criteria.json` is asked about the request's literal payload by one evaluator:

- **Jev** (TypeSafe System One), when `SYSTEM_ONE_API` is set in the environment or the
  workspace `.env`. It returns a probability per criterion.
- **Headless Hermes** otherwise: a fresh one-shot session in the main agent's profile, with no
  tools and no workspace context. It returns concerns with reasons, never numbers.

## Authority limits

- Decide without the human only through a human-approved rule: the sweep, or R1–R6 below.
- Do not approve or reject based on a probability, missing signals, or a Jev
  error.
- Do not modify a pending request, split its operations, or reconstruct a write
  with file or memory tools.
- Do not send conversations, current memories, installed skills, or summaries to
  Jev. The only permitted remote state is the literal `payload` object from the
  native pending request.
- If the review is `RETAINED LOCALLY`, do not expose or copy the detected
  value and do not send it to Jev. Explain that the detector can have false
  positives and negatives.
- With `NO CRITERIA`, do not call Jev or invent scores: begin human review of
  real cases.

## Batch start

The review runs in an isolated interpreter at `.agents/memory-review` in the
workspace. If the review script reports that the interpreter is unavailable
(first use, or after a Hermes upgrade changed its Python), prepare it once:

```sh
python3 agents/skills/curate-memory/scripts/prepare_environment.py
```

It finds Hermes's Python through the `hermes` launcher on PATH, creates a
virtualenv on that Python (with `uv` if available, including the copy Hermes
bundles, otherwise `venv` + `pip`), installs the pinned `typesafe-sdk` from
`requirements.txt`, and links Hermes's own modules into it. Rerunning it is
safe. Never install dependencies any other way, and never during a review.

The review script finds the interpreter from its own location, regardless of
the current directory or skill symlinks. Do not ask the user to export
variables. `HERMES_MEMORY_REVIEW_PYTHON` is only an optional explicit choice of
another prepared interpreter.

```sh
python3 \
  agents/skills/curate-memory/scripts/review_memory_requests.py inventory
```

Report the counts of `memory`, `skills`, and unreadable records. Unreadable
records cannot be approved; leave them pending and show their identity/error.

Review one request at a time. `show` sends only the selected request to Jev (the
others wait their turn) and renders its already-evaluated panel; there is no
prior step that shows the proposal and evaluates it later.

```sh
python3 \
  agents/skills/curate-memory/scripts/review_memory_requests.py show \
  --position 1
```

Copy the panel inside a code block, without added comments or JSON. For the
human view, show only the profile name in the header and hide technical
identifiers (`pending-id`, `record_sha256`, `payload_sha256`). Keep those values
internally for `decide`. The panel shows `Target` (`memory`, `user`, or
`skill:<name>`), each operation as `ADD`, `DELETE`, or `REPLACE` with its text
(`−` old, `+` new) without detailing where it lands in the file, and each Jev
question with its probability (higher = more likely problem). Do not average or
convert results into a quality score. Show at most one request per turn.

## System One routing (Jev)

- **Shadow:** route every pending request with Jev `jev-1.13.0`; append choices, probabilities, confidence, Noul values, usage, and hashes to the ignored shadow log. Apply nothing. Keep labeled outcomes separate from model output.
- **Gated:** after reviewing shadow evidence, set per-rule probability and confidence thresholds. Apply only a rule whose decision and thresholds pass; log `decided_by: jev`, model, and probabilities. Reset thresholds when the model changes.
- **Live:** schedule the gated run daily and send a digest of decisions and items needing a human.

The main agent may reword or split a request: it writes the new memory itself and rejects the original, without asking, only when Jev rates every new piece `durable-fact` with high confidence and no secret/contradiction flag; report each one in a line. Deleting a live entry still needs the human.

## Curation rules (human-approved)

Apply these after the sweep, to each request in turn, before showing its panel. Read the live
memory files with their sizes and limits first. A rule decides only when it applies clearly; when in
doubt, show the panel and let the human decide.

- **R1 Superseded.** A newer request that replaces or contains an older one supersedes it: reject the
  older one.
- **R2 Procedures go to skills.** A memory that says how to do a task belongs in a skill. Add it to the
  existing related skill (create a skill only when none covers the domain), then reject the memory. If the
  skill already holds the procedure, just reject.
- **R3 Ideas go to the vault.** A future project or idea the human has not started goes to the ideas list
  in the vault at `$VAULT_PATH` (`0 - Inbox/_Ideas.md`), then the request is rejected. When `VAULT_PATH`
  is not set or the file is missing, R3 does not decide: show the request to the human.
- **R4 No to-dos.** Pending tasks and progress notes are rejected; chat history is their record.
- **R5 Space.** If an approval would exceed the memory limit, merge overlapping live entries into one
  shorter entry with the memory tool, then approve. Never edit the pending request itself. Ask only when
  a live entry would be deleted.
- **R6 Decided means done.** When a rule clearly decides a request, apply it without asking.

Apply a rule decision with `decide --rule <R1..R6>` instead of `--human-decision` (same identity and
hash checks; logged with `decided_by: rule`). Report each one in one line: rule, target, summary.
When a human decision reveals a reusable preference, propose it as a new rule.

Every edit to these rules needs the human's explicit approval of the exact text. Approval of a
memory decision is not approval of a rule.

## Decision per request

After showing exactly one panel, offer: **approve**, **reject**, **leave pending**,
or **discuss/propose a criterion**. Moving forward is not a decision.

Only after the person explicitly responds with `approve` or `reject`, use the
identity and `record_sha256` captured while reviewing the request: profile,
subsystem, and native ID. Do not select again by position. The hash prevents
acting on a pending request that was modified, replaced, or already resolved:

```sh
python3 \
  agents/skills/curate-memory/scripts/review_memory_requests.py decide \
  --profile default --subsystem memory --pending-id '<reviewed-id>' \
  --decision approve --human-decision \
  --expected-record-sha256 '<hash-shown-during-review>'
```

An approval targeting `user` requires `--lifespan lasting|until|review`, plus
`--date YYYY-MM-DD` for `until` (for `review`, the date defaults to six months
ahead). Lifespans are decided in the review session, never by a background
model: with each USER request's panel, propose its lifespan and date with a
one-line reason (a date already in the text is the strongest evidence), and the
human confirms or changes it together with approve/reject. A replace carries no
metadata forward: removed text is pruned, and each new entry receives the
chosen lifespan. Metadata errors are reported but never undo or block a
successful native apply.

Use `--decision reject` to reject. Verify the response: `success: true`,
`pending_removed: true`, and, for an approval, the Hermes `native_result`.
If it fails or the hash changed, do not repair, recreate, or apply a variant;
return to inventory and request a new review.

## USER memory lifespan review

At the start of each review, run `lifespan check`. It reports due entries,
USER.md entries without metadata, and metadata whose exact text is no longer
present. Dates passing never remove memory automatically. Show each DUE entry
to the human one at a time: if it is still true, refresh it with `lifespan set`
and a new date; if it is no longer true, remove it through a normal memory
request. For each UNCLASSIFIED entry, propose a lifespan and date the same way
and set it once the human confirms.

```sh
python3 agents/skills/curate-memory/scripts/review_memory_requests.py lifespan check
python3 agents/skills/curate-memory/scripts/review_memory_requests.py lifespan set \
  --entry-prefix 'unique beginning of entry' --lifespan review --date YYYY-MM-DD
```

`lifespan init --classify FILE` initializes metadata once from current USER.md;
it refuses to overwrite USER.json. `lifespan prune` removes ORPHANED metadata.
USER.md remains owned by Hermes's memory tool and `/memory approve`; preserve
its exact entry text because staged replace/remove approval matches it exactly.

## Staleness check

`show` also checks, locally and read-only, whether the request still fits its target, and
shows a warning above the scores:

- **Old text no longer present**: a replace or delete names text the current skill or memory
  file no longer contains. Hermes cannot apply it cleanly, or that part was already rewritten.
- **Target changed after this request**: the target was edited after the request was made.
  Any edit counts, so this means "check carefully", not "outdated".

**Automatic rejection (human-approved rule):** run `sweep` at the start of every review
session, before showing any request. It rejects every request with *Old text no longer
present* and prints one line per rejection (target, summary, created_at); report that list to
the human. *Target changed* alone never triggers it, because approving one request flags every
other request for the same skill. Sweep decisions are logged with `decided_by: auto`.

These are facts, not criteria: they are never sent to Jev. The check cannot tell whether a
request is still true about the code; only the human or a reader of the code can.

## Criterion learning

The questions sent to Jev live only in:

```text
agents/skills/curate-memory/criteria.json
```

Every edit to `criteria.json` (adding, rewording, versioning, or removing a
criterion, or changing `catalog_version`) requires explicit human approval of
the exact change text before it is written. Show the proposed diff and wait for
an explicit `yes`; your proposal, a Jev score, or prior approval of another
change does not count as approval.

After a rejection, ask whether the case warrants a general condition. Do not
add one by inference.

Each approved criterion requires `id`, `version`, `question`, `context`,
`definition.yes`, and `definition.no`, plus `exclusions` and `examples` when
they add clarity. State one condition per question and preserve the direction:
a higher probability means a higher probability of the described problem.
Increase `version` when the meaning changes.

After adding or changing a criterion, show/evaluate all remaining pending
requests again. Do not reuse results if the payload, criterion version, or
effective model identity changed. Retain previous results only when all four
dimensions match.

Only perform output inspection when a human explicitly asks for it.

A real Jev test requires at least one approved criterion, an eligible request,
and `SYSTEM_ONE_API` in the environment or the ignored checkout-root `.env`
(see `.env.example`); the environment takes priority. If any are missing,
report that blocker; never simulate an evaluation. Test native integration with
a temporary `HERMES_HOME`, never by approving or rejecting real pending writes
for coverage.
