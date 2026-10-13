Rule:
Decide small changes yourself. A change needs the human's approval only when it alters required functionality, an
approved scenario, security, performance or frontend requirements, or when it is destructive or hard to reverse.
Anything else (a small, targeted code change, including one needed to make an approved test or scenario run) is
yours to make without asking, as worker, reviewer, Monitor or main agent. Record what you changed and why in your
report so the decision can be traced. When unsure which side a change falls on, compare it against that list, not
against how large the diff looks.

Prevents:
Agents asked the human to approve small code changes needed to run a test of a scenario the human had already
approved. The human had to restate the same permission, which spent his time on cheap decisions (tenet 3).

Enforce with:
Read the change and the report. For each change made without approval, check it leaves required functionality,
approved scenarios, security, performance and frontend requirements unchanged and is reversible. For each approval
the agent asked for, check the change touched one of those; otherwise flag the question as unnecessary.
