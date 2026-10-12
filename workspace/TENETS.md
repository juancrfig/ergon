# theSystem tenets

These tenets are general to theSystem; each project or skill makes them concrete; the human approves every change to them.

1. **Take the deterministic parts out of the LLM's responsibilities; what you cannot make deterministic, at least
   make the decision narrow.**
   Why: three LLM readings missed a missing quote that a compiler catches in seconds, every time. A model judging one
   rule at a time decides more reliably than one reviewer holding every rule at once.
   For example, enforce safety deterministically by denying access to a resource rather than storing a memory telling the model not to use it.

2. **Use triggers to pull information back into the loop, so the human does not bottleneck the system by having to.**
   Why: when no trigger brings a failure back to the agent, the human becomes the trigger, a meat proxy between the
   agent and reality.
