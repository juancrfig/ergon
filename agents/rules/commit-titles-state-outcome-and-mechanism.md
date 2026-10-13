# Commit titles state outcome and mechanism

Rule: Write commit titles as concise, imperative English sentences that pair the exact action with its concrete mechanism or outcome (`[Imperative Verb] [Direct Object] [Mechanism/Outcome/Condition]`). Do not use conventional commit prefixes (no `feat:`, `fix:`, `chore:`, `refactor:`, `[scope]`, etc.). Capitalize the first word (sentence case), do not end with a period, and keep each commit atomic to a single coherent change.

Prefer active, precise verbs ("Collapse", "Hand", "Keep", "Step", "Trim", "Decode", "Bind", "Answer", "Re-point") over generic verbs ("Update", "Fix", "Change", "Modify"). Include the condition, trade-off, or mechanism when it clarifies why or how the change works:
- Explain what happens: `Collapse identical notifications from the same sender into one toast`
- State the mechanism over the generic action: `Step the internal backlight in the shell instead of a script per keypress`
- State the performance or condition: `Get the bash prompt up ~30ms sooner`
- State the boundary or guard: `Answer npx for upstream's installer so the menu install does not stop to ask`
- Contrast against the old behavior: `Reach the migration helper through $OMARCHY_PATH rather than by name`
- Clarify state constraints: `Keep the lock wallpaper decoded so waking shows it with the password field`

Prevents: Vague commit histories filled with generic tags or headlines that obscure the behavioral delta and require digging through diffs.

Enforce with: Before committing, inspect the subject line:
1. Strip prefixes: reject titles beginning with `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, or `[tags]`.
2. Check mood and casing: begin with a capitalized imperative verb and contain no trailing period.
3. Check specificity and mechanism: replace generic "Update X" or "Fix bug in Y" with the exact behavior and the mechanism, outcome, or condition.
