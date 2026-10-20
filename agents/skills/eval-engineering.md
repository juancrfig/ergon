# Eval engineering: design cases, grade trials, read results

For whoever builds or reads Ergon's evals (`docs/evals.md`): the Learn agent turning trial failures into skill
changes, or a maintainer adding a case. A score is evidence only when the case is fair, the grader is right, and
someone has read the trials behind it.

## Design a case
1. **One case, one main stress.** Name the node the case is built to strain (Intake's contradiction, Plan's
   questions, Split's reading of code). A failure then points at a node instead of at the whole chain.
2. **Everything a hidden test checks is reachable.** It is in the sources, or in a brief fact the client agent gives
   when asked. A test that assumes a name, path or format nobody stated fails the case, not the agent.
3. **Tag every hidden test** `stated`, `ask` or `kept`, and report the three pass rates apart: `stated` failures point
   at Split or Build, `ask` failures at Plan's questions, `kept` failures at Build breaking what worked.
4. **Write the reference solution first**, and run the hidden tests on it. A case its own solution fails is broken.
5. **Test both directions.** Plant a contradiction and also a case with none; a fact the planner must ask for and
   one it must not ask about. One-sided cases train a node to over-trigger.
6. **Keep hidden files out of the trial folder.** The trial gets `sources/` and `seed/` only; the brief, the tests
   and the reference stay with the harness, so no agent can read the answers.

## Grade
7. **Grade the outcome, not the path.** Run the built code; do not require a sequence of tool calls. An agent may
   find a valid way the case did not foresee.
8. **Code graders first.** Use a model grader only for what code cannot decide, give it one dimension per call and
   a way to answer "unknown", and check it against the human's verdict on a sample before trusting it.
9. **Pass or fail per check**, not 1–5 scores; partial credit comes from counting checks, not from a scale.
10. **Make cheating fail.** A test that an empty program, a hard-coded answer or a deleted test can pass is wrong.

## Run
11. **Isolate every trial**: a fresh folder and a fresh git repo. State left by an earlier trial (files, branches,
    history) makes trials depend on each other and inflates scores.
12. **Several trials per case.** One trial shows what can happen, not what usually happens. Report pass@1 and
    pass^k; pass^k is the headline for Ergon, which must be dependable.
13. **Start from a snapshot** to repeat one node: an approved plan run through Split five times costs five Split
    calls.
14. **Report effort next to quality**: time per clock (wall, agent, waiting for the human, code) and tokens, from
    each run's `calls.jsonl`. A change that gains a point and doubles the tokens is a trade, not a win.

## Read results
15. **Read the trials before the numbers.** For each failed trial, note the first thing that went wrong (later
    failures often follow from it), then group the notes into failure types and count them.
16. **Suspect the case first** when an easy case fails every trial, or only hard cases pass: check its tests, its
    sources and its reference before changing a skill.
17. **A grader per recurring failure type only.** A failure seen once is a note, not a check.
18. **Hold one case per layer out.** Never tune skills on it; run it only to confirm a change helped. Tuning on every
    case overfits Ergon to the dummy projects.
19. **A case every trial passes** becomes a regression case: it guards against breakage and no longer measures
    progress. Add a harder case to keep room to climb.

## Sources
- Anthropic, "Demystifying evals for AI agents" (anthropic.com/engineering), 2026
- Zhu et al., "Establishing Best Practices for Building Rigorous Agentic Benchmarks" (ABC), arXiv 2507.02825
- Kapoor et al., "AI Agents That Matter", arXiv 2407.01502
- Yao et al., "τ-bench" (pass^k, simulated user), arXiv 2406.12045
- Husain and Shankar, "AI Evals FAQ" (hamel.dev), error analysis
