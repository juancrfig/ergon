# Task handoff checklist

Check every task body against this list before the gap review. Each item comes from a real gap that a gap reviewer
found in a task this skill wrote. Why: a worker that meets one of these gaps must invent a decision or stop.

## Identity and change of external data

- **Natural key:** name the exact fields of the key. For each field, say what happens when its value changes at the
  source, when two rows share the key, and when rows change order.
- **Change tracking:** say which version the main record keeps (the original or the latest), where other versions go,
  and what happens when the source returns to an earlier value.

- **Complete read:** when a task deletes or marks data based on an external read, define what counts as a complete
  read and what happens when the read comes back empty or partial. Prevents: an empty response marking every record
  as deleted.
- **Empty values:** when a special value means "empty" (e.g. NULL = no area), list which inputs count as empty:
  missing cell, empty text, whitespace only. Prevents: empty text stored instead of NULL, so the "empty" filter misses
  rows.

## Counts, aggregates and filters

- **Counters:** define each counter exactly: what it includes (header, empty rows, skipped runs) and when it is written.
- **Unit of an aggregate:** say what a number counts (distinct days, submissions, people).
- **Partial periods:** say how the first and last period of a range are handled when they are incomplete.
- **Several values in one group:** when a group (a person, a month) has several values of an attribute (name, area),
  say which one is shown.
- **Scope of a calculation:** for each derived value, say whether it is computed globally or after the active filters.

## Interfaces between tasks

- **One contract, one place:** when a later task extends an endpoint, table or object, state the full contract in the
  task that creates it and list exactly which fields the later task adds. Do not restate the contract differently.
- **One business rule, one function:** when a rule already exists in the code (search matching, date ranges,
  filters), name the function that implements it and require its reuse; when the rule exists only inline, require
  extracting it so every caller shares it. Prevents: two copies of the same rule that drift and behave differently.
- **Data that another task consumes:** when task B needs data that task A produces, put the field, its format and
  where it is stored in both tasks.

## Input from users

- **URL and query parameters:** name each parameter, its format, its default and what happens with an invalid or
  missing value.
- **Search:** for each searchable field, say how it matches (contains, exact, digits only, accents, case), including
  inputs that do not fit the field (letters in a numeric ID).

## Output

- **Order:** give a stable sort order, including the tie-breaker.
- **Paged or wide output** (PDF, tables): say how rows and columns split across pages and what repeats.
- **Times shown to people:** name the time zone and say whether the label shows it.

## Running services

- **State across restarts:** for each value a rule depends on (start time, last result), say where it is stored and
  what happens after a restart.
- **Notifications and retries:** say how a failed send is retried without sending duplicates, and what happens when
  the state it reports changes before the retry (e.g. an opening message still pending when the condition resolves).
  Prevents: a lost opening message after a fast resolution.

- **Locks between processes:** when a task uses a lock or mutual exclusion, say when a lock counts as abandoned and
  why that limit is safe. Prevents: a reviewer rejecting a deliberate stale-lock expiry, or a crashed run blocking all
  later runs.

## Project setup

- **Native dependencies:** when a task adds dependencies that compile on install, name the ones whose build scripts
  are allowed. Prevents: the package manager leaving them unbuilt and the app unable to start.
- **Container build context:** when a task creates a container, say which folder is the build context and which files
  outside the app folder it needs. Prevents: copying files from outside the build context.
- **Default paths:** write default paths relative to the app folder, not the repository root. Prevents: wrong
  multi-level parent calculations.
- **Agent-instruction files:** changes to agent-instruction files (AGENTS.md and similar) are not part of a worker's
  task; the main agent makes them at merge time. Prevents: a worker blocked by the harness's protection of those files.

- **Extension contract:** when a task adds a table, command, route or screen, name how the project registers one
  (file, function, an existing example to copy). Prevents: the worker spending minutes grepping to rediscover it.
- **Existing data:** when a task changes a stored schema, say what happens to data that already exists: migrate it,
  or reset it because the human said the data is not official yet. Prevents: a change that works only on new
  databases.

## Consistency

- **One value, one statement:** a range, limit or status list stated twice in a task (or in two tasks) must match.
  When a later precision replaces an earlier line, edit the earlier line instead of adding a contradiction.
