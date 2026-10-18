---
name: grilling-heuristics
description: "Use when grilling. Apply learned user decision preferences so each session asks fewer obvious questions."
---

# Grilling heuristics

The human's decision-making preferences, learned from past grilling sessions. Use them so each session asks fewer
obvious questions and spends the human's attention on the important, non-obvious ones.

## How to apply

1. Load this skill before the first round of any grilling session.
2. For each frontier question, check the heuristics below. If a heuristic decides it with high confidence, do not
   ask it. Add it to a short "Decided by heuristic" list at the top of the round (one line each: the decision and the
   heuristic number), so the human can veto it.
3. Ask only the questions that no heuristic settles, or where the heuristic and the situation conflict. Questions
   with a large blast radius, irreversible effects, cost, security or data-integrity impact are always asked, even
   when a heuristic suggests an answer.
4. If the human says unanswered questions count as agreement with the recommendation, record unanswered
   recommendations as approved and do not ask again during the synthesis. Do not apply this before the human says it.
5. A question the human marks with "(flag)" was obvious and should not have been asked. Treat it as evidence for a
   new or stronger heuristic.
6. Before presenting a decision, give enough plain-language context: the existing system, what is already built, and
   the concrete consequence of each option. An unexplained acronym or implementation detail makes a question unusable.

## Calibration sessions

When the human reviews earlier design recommendations to calibrate this skill, do not skip historical decisions with
the heuristic shortcut: present every recommendation in the agreed scope and ask for the human's judgment and
rationale. Keep the original proposal, the human's judgment, implementation status and new inferences distinct; say
"not recorded" when a rationale is absent. A past recommendation is not an approval. Record project-specific feedback
in the project's docs, separate from candidate general heuristics, and consolidate across the agreed projects before
proposing changes to this skill.

## Closing the interview

Before closing, consolidate the agreements and replace proposals that were superseded. Separate approved decisions,
operational details the agent can resolve, and open questions that really block. Do not ask again for approval of
what is already agreed.

## How to update (always with the human's approval)

At the end of every grilling session that taught something new:

1. Draft the changes: new heuristics, sharpened ones and removals, each with its evidence from the session (the
   question, the human's answer, any "(flag)").
2. Show the exact proposed text and ask for explicit confirmation.
3. Write only what the human approves, worded as the human corrected it. Never update this skill silently.

Write each heuristic as one rule plus its reason. Keep them general; project facts go to the project's docs.

## Heuristics

Seed heuristics. Each workspace sharpens them with its own human.

1. **Simplest first.** For a first version, pick the simplest option that works.
2. **Undefined business process means a pending decision.** When a decision depends on a process nobody has defined,
   record it as pending; do not invent a solution.
3. **Reuse what exists.** Inherit the working product's behavior and conventions unless the request signals a change.
   During a migration, copy the old system's recipients, routes and rules as they are; validating why each exists is
   not part of the migration. **Why:** a migration changes the platform, not the business.
4. **Research before grilling; ask only open consequential decisions.** Inspect the existing product, protocols and
   the human's standing preferences first. Do not ask the human to restate established behavior, reconfirm an
   explicit request or reopen what a standing preference settles.
5. **Do not change how end users enter without a reason.** Replacing spreadsheets or legacy tools with the central
   app is a reason (see 18). **Why:** habit changes cost, but centralizing information is the goal.
6. **Legacy becomes obsolete, never deleted.** Old sheets, flows and files are kept as reference.
7. **No data loss, no guessing.** Keep records even if the source changes or deletes them; alert instead of guessing.
8. **Derive data from what already exists.** Avoid new lists someone must maintain by hand.
9. **An infrastructure outage does not block design.** Continue locally with the same structure and move later.
10. **Extras after the foundation.** Features that depend on something unsettled stay out of scope until it is
    confirmed.
11. **Alerts go to the human's chat channel** during the initial phase of a project.
12. **Prevent the worst cases by design.** Consider connection failures, unavailability and bad data in each
    dependency. Keep safe functions running (e.g. a copy of the last good read); a failure never replaces valid data
    with an empty, partial or invalid load. Make staleness visible and alert. Choose the simplest sufficient
    protection without asking whether to include it.
13. **Design autonomy as a reusable protocol.** For recurring agent work, ask for boundaries, exceptions and
    escalation conditions, not approval for every case. **Why:** case-by-case approval makes the human a bottleneck.
14. **Receiving a request does not grant authority to do it.** Distinguish who can request, who can assign and which
    actions are authorized.
15. **Under uncertainty, choose the cheaper failure.** If it is unknown whether an obligation was already fulfilled,
    prefer repeating a cheap, reversible action (e.g. a duplicate notice) over missing the obligation. Not for harmful,
    irreversible or costly actions. **Why:** a missed obligation costs more than a redundant notice.
16. **Decouple a capability from its cardinality.** One or many recipients, items or channels use the same
    capability. **Why:** scalable systems must not break when they grow from one to many.
17. **Without a webhook, poll as fast as the limits allow.** Use the shortest interval within the provider's limits,
    as long as the risk of overloading the API is nil. Check the limits, and check that variable cost (e.g. AI) depends
    on new items, not on frequency. Do not copy the old interval or ask about frequency. **Why:** polling is cheap;
    delay is the real cost for whoever waits.
18. **Centralized information, not spreadsheets.** If a person manages the data, design a simple web app (CRUD) on the
    company's central database instead of a spreadsheet as source or entry point.
19. **One-time copy when migrating.** Copy the old sheet's or system's data once; the original stays as reference only,
    with no sync. **Why:** two synced sources create identity and authority conflicts.
20. **Graphical interface only if a person uses the system.** A system that runs on its own needs a CLI or API only.
21. **Approved AI providers need no new approval.** Use the providers the human approved (recorded in the workspace
    decisions, `docs/`); ask only about a new provider.
22. **Do not duplicate what a trusted source system already keeps** (e.g. the mail provider): store references and
    what the system produces. Exception: the system actively works with the document, or receives files the source
    does not hold.
23. **A recurring task with no owner goes to the main agent**, under a protocol, escalating only exceptions.
    **Why:** the human designs the frame; the agent operates inside it.
24. **If users already run a flow, the new interface follows its intent.** No validation is needed before building;
    adjust with use. **Why:** the running flow is already the validation.
