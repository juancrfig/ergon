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

3. **Design the system to evolve so it needs less human intervention the longer it is used; spend the human's time
   on the decisions that need it most, not on cheap ones.**
   Why: the goal is not to remove the human but to put their limited time where their judgment matters. A decision the
   human makes the same way again and again is a cheap decision: the system should learn it and take it over.
   For example, every human intervention records the proposal, the human's decision and their reason; repeated
   corrections become a rule the human approves once; a decision type that matches the human many times in a row
   becomes automatic, with sampled checks and a monitor that hands it back to the human when it drifts.
