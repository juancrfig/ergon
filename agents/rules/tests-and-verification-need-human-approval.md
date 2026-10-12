Rule:
Tests are a scarce good. Write, change or run automated tests only at the end of development, and only when the
human explicitly approves each test. Verification follows the same principle: do not run the application, evidence
runs, linters or smoke checks to confirm your own work unless the human explicitly asks for it. Gates are the
exception: the project's deterministic checks (compile, type check, build), declared in its verification guide
(`verify-<project>/gate.json`). Workers run the gate before finishing and fix what it reports; this needs no approval.
Approval of a spec, a task split or a task is not approval of tests or evidence runs. Never block or delay delivery
because tests or evidence runs are missing, and never claim that something was tested or verified when it was not.

Prevents:
Agents spent most of each task writing speculative tests and verification harnesses that nobody asked for, delaying
working code and growing suites the human did not want to maintain. The gate exception prevents the opposite failure:
a missing quote in Preoperacional passed a worker re-read and two reviewers because nothing compiled the code.

Enforce with:
Read the diff for added or changed test files, fixtures, mocks, snapshots and test configuration. Each one must trace
to an explicit human approval quoted in the task. Read the worker's report for test runs or evidence runs that the
task did not request; gate runs are allowed. Changes to a project's gate steps must be part of the task.
