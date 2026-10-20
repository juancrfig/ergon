# Overview

A framework to reliably build high-quality software by leveraging AI agents

# Infrastructure

- **[Hermes Harness](https://hermes-agent.nousresearch.com/docs)**
- **[llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**

# Install

Needs Python 3 and Hermes. From the repo root, once per machine and project:

```
python3 -m ergon --project <project folder> install   # creates the node profiles and the project's folders
hermes -p wiki-maintainer model  # then set each profile's model and credentials by hand
hermes -p planner model
hermes -p architect model
hermes -p builder model
```

Running it again is safe: existing profiles are left as they are.

# The Four Problems

1. How to gather, curate, and maintain knowledge?
2. What are skills, tools, scripts, and context in general an agent needs to operate effectively?
3. How to ensure the implementation respects the constraints and follows the plan, while mitigating 
blast radius write-allowed agents may cause?
4. How the system will improve over time?

# Tenets

1. Take the deterministic parts out of the LLM's responsibilities, what you cannot make deterministic, at least make the decision narrow.
2. Use triggers to pull information back into the loop, so the human does not bottleneck the system by having to.
3. Design the system to evolve so it needs less human intervention the longer it is used; spend the human's time on the decisions that need it most, not on cheap ones.

# Decisions & Rationale

- Instructions for agents must be carefully maintained. Ideally, agents should handle entirely the 
self-improvement mechanism. However, the protocol agents follow to do this must not be left in
charge of agents. I've noticed agents are not good (by default) when trying to generalize their 
reflections from mistakes, effectivelly bloating their own memory with ticket-specific learnings. 
Until a clear protocol is designed and battle-tested, the feedback loop must remain in charge of humans.
- **Tenet 1:** Three LLM readings missed a missing quote that a compiler catches in seconds, every time. A model judging one rule at a time decides more reliably than one reviewer holding every rule at once. For example, enforce safety deterministically by denying access to a resource rather than storing a memory telling the model not to use it.
- **Tenet 3:** The goal is not to remove the human but to put their limited time where their judgment matters. A decision the human makes the same way again and again is a cheap decision: the system should learn it and take it over. For example, every human intervention records the proposal, the human's decision and their reason; repeated corrections become a rule the human approves once; a decision type that matches the human many times in a row becomes automatic, with sampled checks and a monitor that hands it back to the human when it drifts. 
