# Gate contract

A gate is the class of verification that needs no approval: compile, type check and build. This file is the contract
every project's gate follows, so agents and the orchestrator use one interface everywhere.

## Declaration

- One file per project: `<project>/agents/skills/verify-<project>/gate.json`.
- `setup`: what makes the worktree ready (install dependencies). A setup failure is an environment problem, reported
  as such (exit 2), never as a code error.
- `steps`: one entry per check, each with `name`, `cwd` (relative to the worktree) and `run`. Each step calls the
  stack's own tool, or a script of the project that does.
- Run it with `scripts/gate.py <gate.json> --root <worktree>`. Exit 0 = green, 1 = red, 2 = setup or config failure.

## What a gate may contain

- Compile, strict type check, build. Nothing that launches the app, calls a real data source or needs a secret.
- Fast: about 2 minutes for the whole gate, after setup. Slower checks (container images, tests) are not gates.
- Offline after setup. Installs use the shared local package cache.
- No lint until a real incident shows the need (rule: no incident, no check).

## Standard recipes

Copy the recipe for the project's stack. Change it only for a stated reason.

- **TypeScript (Node + Vite):** `setup`: `pnpm install --frozen-lockfile`. Steps: `tsc --noEmit` for each
  tsconfig (server, web: each part of the code is in exactly one), then `vite build`.
- **Python 3.11+:** `setup`: create the virtual environment and install the locked dependencies. Steps:
  `python -m compileall -q <package>` (syntax), then `pyright` (types). Every Python project follows these typing
  rules from its first line:
  - **Strict pyright** for the whole package (`typeCheckingMode = "strict"` in `pyproject.toml`), so values of
    unknown type are errors, including those from untyped libraries. Why: an unchecked function looks clean.
  - **Typed boundaries inside the code:** every function's parameters and return type, and every class field.
    Local variables are annotated only when pyright cannot infer them. Why: errors cross between functions;
    annotating `total = 0` adds noise, not safety.
  - **Typed shapes at external boundaries:** data from sheets, APIs, databases and files becomes a typed model
    (dataclass, `TypedDict` or a validation model) where it enters the code. No untyped `dict` travels past that
    point. Why: most of our errors start as untyped outside data deep in the code.
  - **Untyped libraries stay behind a small typed module** that the rest of the code calls. Why: one place absorbs
    the missing types instead of every caller.
  - **Ignores name the error and give a reason**, for example `# pyright: ignore[reportUnknownMemberType]  # gspread
    has no stubs`. Bare `# type: ignore` is rejected (`enableTypeIgnoreComments = false`), and an ignore that no
    longer silences anything is an error (`reportUnnecessaryTypeIgnoreComment = "error"`). Silencing an error to
    pass the gate is never allowed.
  - Pyright, not mypy: faster, checks unannotated functions, and matches the editor. Reconsider only for a framework
    that needs a mypy plugin (Django).
- **No JavaScript recipe.** JavaScript code uses the TypeScript recipe: a JavaScript project's gate task moves it to
  TypeScript strict before any other task. Why: a gate without a type checker cannot catch most agent errors, so a
  stack without one gets no recipe.
- Every project is typed (TypeScript strict, or Python with pyright strict): the type checker is the cheapest gate.
- **Every stack: file size first.** The first step is `python3 <skills>/verification-heuristics/scripts/file_size.py
  --config <guide>/file-size.json` (run from the worktree root). It fails when an agent-authored file passes 5,000
  tokens (bytes/4; about 450 lines), skipping lockfiles, build output, generated, vendored and binary files and READMEs, and
  prints how to split. Files already over the limit when the check is turned on are recorded once with `--init`
  and may not grow (a ratchet); splitting them is its own task, after which `--update` lowers their entries. Why:
  workers re-read large files in short slices; one worker re-opened a 20 KB file 26 times in a run. A deterministic
  limit keeps files small enough to read once. It runs in the gate, not a pre-commit hook, because workers do not
  commit: the gate is where the worker reads the error and splits the file itself.

## Feedback to the agent

The agent must be able to fix every error from the gate's output alone.

- The tools' own messages, unchanged: file, line, column, error code, message, and the source excerpt when the tool
  prints one. The gate never rewrites or summarises them away.
- Every step runs, even after one fails, so all errors come in one round.
- A summary first: which steps failed, how many error lines, which files.
- Long output is cut at a budget with a note saying where the full log is. Nothing is dropped silently.
- Plain text: terminal colour codes are removed.
- The exact command to run the gate again.

## In a task run

1. The worker runs the gate before it finishes and fixes what it reports.
2. The orchestrator runs the gate again on the worker's change. Why: an instruction can be skipped; this run cannot.
3. Red: the orchestrator sends the worker the gate output, with each error line marked `[new]` (caused by the change)
   or `[old]` (already on the base commit), the round number and the rounds left. Up to 2 gate rounds.
4. The `[old]`/`[new]` marks come from running the gate once on the base commit (`--save-errors`), then on the change
   (`--baseline`). A worker fixes `[new]` errors; `[old]` ones are fixed only when the task says so.
5. Still red after 2 rounds: the run is `failed` with code `gate`, and goes to the human. Gate rounds are not review
   failures; the reviewer only sees code that passes, apart from `[old]` errors the task did not cover.
6. The gate output of every round is kept with the run evidence.

## A project without a gate

The orchestrator stops the run and tells the human. It never skips the gate silently. The first task of a project is
its gate; for a new project it comes before any feature task.
