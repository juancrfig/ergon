# 0025 · A project's repos are the git clones in its folder

Status: accepted (2026-10-20)

## Context
Split and Build work on every repo of a project (ADR 0023, 0024). Ergon needs to know which repos those are, and
Split must read code without being able to change it.

## Decision
- A project's repos are the git clones directly inside the project folder, as in theSystem: company, projects,
  source clones. Nothing registers them.
- A repo's files are the ones git tracks or would add: ignored files (dependencies, builds) are not code.
- The read-only tool gains `search_code` and `read_files`, offered only when code scopes a run to repos. Paths are
  `<repo>/<path>`; a path outside its repo, or ignored, is refused. Read-only is the tool's property, not an
  instruction.

## Consequences
- Intake and Plan see no code tools.
- A project with no clone cannot run Split.
