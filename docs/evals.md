# Evals: measuring Ergon on dummy projects

Status: built for Layer 1 (`evals/`), no real trial run yet. Sections say what is **not built yet**.

## Why

Every node exists, but no goal has gone from raw sources to built code in one run. Skill changes need evidence
(`agents/skills/prompt-engineering.md`; how to build evals: `agents/skills/eval-engineering.md`, "Evidence before and after"): an eval produces that evidence on demand,
instead of waiting for a real client project to fail.

Two questions, in order:
1. **Smoke**: does one goal go Intake → Plan → Split → Build with no crash, no stuck request, no broken hand-off?
2. **Quality**: how well did each node do its job, measured against what the client really wanted?

Quality numbers mean nothing until smoke passes on every case.

## Vocabulary

Ergon already uses *task* (Split's output) and *run* (one request's folder). The eval uses other words:

- **Case**: one dummy project with its inputs and its graders. Example: `todo-cli`.
- **Layer**: a group of cases of similar difficulty. Layer 1 is the easiest.
- **Trial**: one attempt at a case, from an empty project folder to graded result. Models vary between attempts, so
  a case runs several trials.
- **Brief**: what the client really wants. Only the client agent and the graders see it.
- **Client agent**: the agent that plays the client: answers the planner's questions from the brief.
- **Grader**: code that scores one aspect of a trial. Hidden tests are the main one.
- **Hidden tests**: acceptance tests no node sees. They run on the built code after the trial.
- **Reference solution**: code written for the case that passes every hidden test. It proves the case is solvable
  and the tests are right.
- **Snapshot**: the belts and repos saved after a node finished, so a later trial can start from that point.

## The layers

- **Layer 1**: one repo, Python standard library, a command-line program. Every behavior is checkable by running a
  command, so the builder's missing browser does not matter.
- **Layer 2**: two repos (an API and a web screen). Tests whether Split writes the interface between repos well.
  Needs browser checks, so it waits for issue #66.
- **Layer 3**: hidden-rule-heavy domains (chess: castling, en passant, promotion; graded by perft, the known count
  of legal positions after N moves) and changes to a larger existing codebase.

## Anatomy of a case

```text
evals/cases/<case>/
  case.json        layer, the node it stresses, the goal Plan gets, the repos (empty or from seed/), the planted
                   contradictions with the words that recognize them
  sources/         what Intake ingests: client email, meeting notes (with planted traps)
  seed/            optional: the repo as it is before the change (brownfield cases)
  brief.md         hidden: what the client wants, as numbered facts (F1, F2, …)
  hidden-tests/    hidden: acceptance tests, each tagged with the facts it checks
  reference/       hidden: the reference solution
```

Rules for a fair case (from the research below):
- **Everything a hidden test checks is in the sources, or in a brief fact the client gives when asked.** The
  command names and output format are in the sources; a test that assumes a file path nobody stated is a broken
  test, not a failed agent.
- **Each hidden test is tagged**: `stated` (in the sources), `ask` (only in the brief: passes only if the planner
  asked for it), or `kept` (an existing behavior of the seed that must still work). The three pass rates are
  reported apart: they point at different nodes.
- **The reference solution passes every hidden test** before the case is used. A case at 0% across all trials is
  first suspected broken.
- **Hidden files never enter the trial folder.** The harness copies only `sources/` and `seed/` into it.

## The client agent

- A separate Hermes profile, `client`, on the cheap model class (the human's choice). It sees the brief and the
  planner's questions, nothing else.
- It answers only from the brief and the sources. For a question neither covers it answers "Not specified; use
  your judgment." Its instructions are `evals/client.md`; its answers are checked against Plan's answers contract.
- **Not built yet**: answers naming the brief facts they used, so code can count the facts the planner drew out.
- **Approvals are automatic in Layer 1**: Intake proposals and Plan stories are approved as they come. Rejection
  policies ("reject a story that adds accounts") come later, as cases of their own.

## The command

```text
python3 evals/run.py                         every case, 1 trial each
python3 evals/run.py todo-cli -k 3           one case, 3 trials (-j: trials at once, default 3)
python3 evals/run.py --check                 no agent: every case is sound
python3 evals/run.py todo-cli --from split --snapshot evals/trials/<trial>   repeat Split and Build only
```

- Every trial runs in a fresh folder, `evals/trials/<time>-<case>-<n>/` (not committed): a new git repo for the
  project and for each of its repos, no history from earlier trials.
- Trials run in parallel, one thread each. Each run first checks the cases, then writes a report beside the trials.
- **A sound case**: its reference passes every hidden test, an empty program passes none, and its seed passes every
  `kept` test. `--check` runs only this, in seconds.
- The harness drives the nodes through their classes, the way the command line does (ADR 0026).
- **Starting from a node**: `--from split --snapshot` copies an earlier trial's project, drops the belts from Split
  on, resets the repos, and submits a new split of the approved plan. Five Split trials from one approved plan
  cost five Split calls, not five full trials.
- **Runs happen when the human starts them**, not on every commit: a full trial calls frontier models.

## What each trial records

One `trial.json` per trial, beside the trial's project (every node's run folder), `hidden-tests.json`,
`trial.log`, and the client's run folder.

**Identity**: case, trial, Ergon commit (and whether the tree had changes), a hash of each skill, the model of
each profile.

**Outcome**
- Finished (reached Build done) or the node and reason it stopped.
- Hidden tests passed, per tag: `stated`, `ask`, `kept`.

**Time** (three clocks, per node and in total)
- *Wall*: the whole trial, measured by the harness.
- *Agent*: the sum of every agent call's duration (`calls.jsonl`).
- *Working* and *waiting for the human*: the time requests spent in `working`, and in `waiting` and `review` (belt
  events). The client agent's time is reported as its own row, so agent speed is not mixed with human speed.
- **Not built yet**: *code* time (working minus agent) in the report.

**Effort**: per agent call: input, output, cached and reasoning tokens, API calls, tool calls. Cost reads 0 on a
subscription, so tokens are the cost measure.

**Contract compliance** (see the next section).

**Node quality** (counts, no judge)
- Intake: planted contradictions caught (named in the proposal) out of those planted.
- Plan: client rounds. **Not built yet**: questions asked, brief facts drawn out.
- Split and Build: rejected attempts with code's reasons, from `calls.jsonl`.

**Reliability across trials**: pass@1 (share of trials that pass) and pass^k (the chance that all k trials pass).
Ergon is meant to be dependable, so pass^3 is the headline number.

## Contracts against behavior

Code already checks each answer against its contract, and retries a rejected one. The eval adds three checks:

1. **Every rejected attempt is counted, with its reasons.** A node that passes only on its third attempt is not the
   same as one that passes on its first.
2. **Every artifact is checked again after the trial**: each request on each belt, and each saved answer, against
   its contract. This catches code that writes something the contract does not allow.
3. **Claims are compared with the tool-call log.** Each of these is a contract the schema cannot see:
   - Plan: every page in a story's `sources` was read in that run (built).
   - Build: a task whose session ran no terminal command checked nothing (built).
   - The tools each call used, from its session export (built; the export's shape is Hermes', so it is read
     loosely: check it on the first real run).
   - **Not built yet**: Split: every existing file a task names was read.

## Is Ergon ready to measure?

Checked against the code on the `ergon` branch.

**Ready**
- Belt events log every move with a timestamp: wall time and time waiting for the human, per request.
- The session export holds each call's start and end, tokens, API calls and tool calls (ADR 0027).
- The chain is traceable: a build request names its split, a split request names its plan.
- Requests and answers are checked against their contracts; rejected answers are retried.

**Gaps closed** (`ergon/agent.py`)
1. A failed call lost its record: Hermes exiting with an error raised before the session was saved. Now its time is
   logged first, and its session saved when one exists.
2. A timed-out call crashed the node and left the request in `working`. Now it is a failed call: logged, and the
   request is rejected with the reason.
3. Rejected attempts left no structured record. Now every call writes one line to `calls.jsonl` in its run folder:
   label, profile, start and end (to the millisecond), seconds, exit code, session, model, tokens, API and tool
   calls, outcome (`accepted`, `rejected`, `failed`) and code's reasons.

`calls.jsonl` is the source of agent time and effort; belt events (to the second) are the source of wall time and
time waiting for the human.

## The three Layer 1 cases (approved)

Each case stresses a different node, so a failure points somewhere.

### 1. `todo-cli`: the smoke case
- **Product**: a to-do list for one person, on the command line: add, list, mark done, remove; saved to a file.
- **Sources**: an email from the client and short meeting notes. One planted contradiction: the email says
  "remove deletes it for good", the notes say "removed items should be recoverable".
- **Brief facts**: which of the two wins; whether `list` shows done items; the order of `list`.
- **Stresses**: the whole chain; Intake catching the contradiction.
- **Graders**: about 15 hidden tests that run the program and compare its output.

### 2. `split-bill`: the rules case
- **Product**: splits a shared bill among friends: who paid what, who owes whom, and the fewest payments that
  settle everyone up.
- **Sources**: the client's description and two worked examples.
- **Hidden rules, only in the brief**: amounts in cents, never floats; how leftover cents are shared out (which
  person gets the extra cent); an even split by default, shares by percentage on request.
- **Stresses**: Plan. A planner that does not ask about rounding gets a program that is off by one cent, and the
  `ask` tests show it.
- **Graders**: tests on exact amounts, plus a check that the payments settle every balance to zero, for random
  bills.

### 3. `gradebook`: the brownfield case
- **Product**: an existing grade-book program (about 200 lines, with its own tests and conventions). The change:
  weighted categories (homework 40%, exams 60%) and an export to CSV, a spreadsheet file format.
- **Seed**: the existing repo, so Split has to design from code that is already there.
- **Stresses**: Split reading the code before naming files; Build keeping the existing conventions.
- **Graders**: `stated` tests for the new feature, plus `kept` tests: the seed's own tests must still pass. That
  is how SWE-bench grades: fix what was asked without breaking what worked.

## What the research says

- **Anthropic, "Demystifying evals for AI agents" (January 2026)**: start with 20–50 tasks drawn from real
  failures, not hundreds. Grade the outcome (the built code), not the path the agent took. Prefer code graders;
  use model graders only where needed, calibrated against a human. Give each case a reference solution. Isolate
  trials: shared state, including git history from an earlier trial, inflated their scores. Read the
  transcripts: a score is not trusted until someone has. Use pass@k and pass^k. Separate capability evals (low
  pass rate, room to climb) from regression evals (near 100%, catch breakage).
- **Zhu et al., "Establishing Best Practices for Building Rigorous Agentic Benchmarks" (ABC checklist, 2025)**:
  real benchmarks over- or under-state agents by up to 100% because of flawed tasks or graders. Checks that apply
  here: clean the state between trials (T.4); keep the agent away from the hidden answers (T.5); freeze the
  environment (T.6); provide an oracle solver (T.9); inspect outliers in pilot runs (T.10): failing only easy cases
  means a broken case, passing only hard ones means a shortcut. Unit tests can miss edge cases: check the tests
  themselves (O.d).
- **Kapoor et al., "AI Agents That Matter" (2024)**: report cost next to accuracy, never accuracy alone; keep
  held-out cases so tuning cannot overfit; standardize how runs are made so results reproduce.
- **Yao et al., τ-bench (2024)**: a model plays the user; grading compares the final state with the goal state;
  introduced pass^k, because agents that pass once often fail on a repeat.
- **Husain and Shankar, "AI Evals FAQ"**: error analysis first. Read 20–50 traces, write notes on the first
  failure in each, group the notes into failure types, count them. Build a grader only for a failure type that
  recurs. Prefer pass/fail over 1–5 scores. One domain expert decides what good means (here: the human).

What this means for Ergon:
- Three cases is a start, not a suite. The suite grows from failures the trials find.
- The first trials are read by hand. The numbers come after the failure types are known.
- One case per layer stays held out: never used while tuning skills, only to confirm a change helped.

## Hidden tests and Inspect

Decided: the hidden tests stay eval-only; they never become Inspect.

- **Inspect** checks the built code against the approved stories' `done_when`: what Ergon understood.
- **Hidden tests** check it against the brief: what the client wanted. Real projects have no brief, so Inspect must
  never see the hidden tests: it would score with an answer key production never has.
- **Their disagreement is the signal**, once Inspect exists:
  - Inspect passes, `ask` tests fail: Plan or Intake missed a requirement.
  - Inspect passes, `stated` tests fail: Inspect is too lenient.
  - Inspect fails, hidden tests pass: Inspect is too strict or invents a requirement.
- **The eval grades Inspect too**: its verdicts against the hidden tests, counted as false passes and false fails.
- **Shared**: the machinery only (running checks on a fresh copy of the code, one verdict per criterion), not the
  tests.
- Until Inspect is built, the hidden tests are the only check on what is built.

## Open decisions

None.
