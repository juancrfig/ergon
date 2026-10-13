Rule:
theSystem is a public repository. Every push from a theSystem clone runs the push guard (`thesystem/push_guard.py`,
enabled by `core.hooksPath agents/.harness/git-hooks`). Never bypass it: no `--no-verify`, no other hooks path, no
push from a clone where the guard is off. When the guard blocks a push, remove the data or show the human the exact
text; only the human may decide to push it anyway.

Prevents:
Company data from a private instance reaching the public repository. Improvements flow back from company instances,
so every push carries that risk.

Enforce with:
Check that the pushing clone has `core.hooksPath` set to `agents/.harness/git-hooks`, and that no push command in the
run uses `--no-verify`.
