# Prompt engineering: change a node's skills or prompts

For whoever changes how a node's agent is instructed: the Learn agent proposing a skill change from run evidence, or
a maintainer editing one. Every change waits for the human's approval.

## Know the reader before editing
- **Model class.** The card for each profile in `agents/AGENTS.md` gives its class. Cheap agents (wiki-maintainer,
  builder) need exact steps; frontier ones (planner, architect) need the goal and the bar. Weight the prompting
  advice of the vendor the profile runs on.
- **The whole prompt, not the skill alone.** A skill is the first section of a prompt that code assembles: skill,
  then data sections, then the JSON Schema of the answer contract, plus Hermes' trimmed system prompt. Read a real
  `<call>.prompt.md` and `<call>.system-prompt.md` before editing, and say nothing another section already says.
- **What code checks.** Read the node's problems check in `ergon/<node>.py` and its contract in
  `nodes/<node>/contracts/`. A rule code enforces becomes one line of context ("code rejects a file the task does not
  list") so the agent knows the cost; it needs no procedure.

## Rules
1. **Every sentence changes behavior.** The model is already capable. Delete a sentence that matches what it would
   do anyway, repeats the contract, or repeats another section.
2. **Goal and done bar first.** State what the answer is for, who reads it next, and what makes it good. Give steps
   only where a slip is costly or the model is cheap: freedom matches fragility.
3. **A reason with each rule**, in one clause. The reason lets the agent handle the case the rule did not list.
4. **No contradictions.** When two rules can collide, say which wins. Reasoning models spend effort reconciling
   conflicts instead of doing the job.
5. **Calm wording.** "Use X when…", not CRITICAL/MUST/NEVER in capitals: newer models over-apply emphasis. Keep
   "never" for a hard guardrail, paired with what to do instead.
6. **Say what to do.** "Don't X" puts X in front of the agent.
7. **A job, not a persona.** Title a skill by its job and place in the flow. "You are an expert…" does not improve
   accuracy (Zheng et al., EMNLP 2024); who reads the output and what code checks are information, so keep those.
8. **Placement depends on the vendor.** OpenAI: instructions above long context work better than below; both ends
   is best. Anthropic: long documents first, the question last. Ergon's order (skill, data, contract) fits OpenAI.
9. **One term per concept**, and it is the contract's field name or the GLOSSARY term. Markdown headings delimit
   sections.
10. **Examples are short, concrete and varied.** One example becomes a template; give two when variety matters.
11. **Mechanics go to code, not prose.** If code could check it, propose the check instead of a sentence: a
    sentence is followed only most of the time.
12. **Nothing that goes stale**: no dates, model names or numbers code owns. Only Ergon vocabulary.

## Checklist for each change
- Each line: changes behavior? not in the contract, code or another section? has its reason? stated positively?
- Words match the contract fields and GLOSSARY.
- When to stop and what a stop returns is explicit.
- The answer's done bar is explicit.
- Statements about code are true: read the code path (what is checked, retried, reset) before describing it.
- Shorter, or each added line justified. A skill renamed or loaded differently → its profile card in
  `agents/AGENTS.md` changes in the same commit.

## Evidence before and after
1. **Baseline.** Start from real runs: `<call>.session.jsonl`, the tool-call logs, rejected answers. Name each
   failure and the run that shows it. No failure seen, no change proposed.
2. **Scenarios.** About three per failure, each a request that reproduces it.
3. **Smallest edit** that makes them pass; run them again. Each run needs the human's approval; without runs, say
   the change is untested.
4. **When stuck**, give a model the prompt plus the desired and the observed behavior, ask for minimal edits, then
   judge its edits with these rules.

## Sources
- Anthropic: docs.anthropic.com, agent-skills best practices and Claude prompting best practices;
  anthropic.com/engineering/effective-context-engineering-for-ai-agents
- OpenAI: cookbook GPT-5 and GPT-4.1 prompting guides (placement: GPT-4.1, Prompt Organization);
  developers.openai.com/api/docs/guides/reasoning-best-practices; cookbook "Skills in OpenAI API"
- agentskills.io/specification; Zheng et al., arXiv 2311.10054
