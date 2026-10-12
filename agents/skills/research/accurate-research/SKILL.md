---
name: accurate-research
description: "Use when researching factual claims. Verify claims against full sources and counter-evidence."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, fact-checking, evidence, sources]
    category: research
    related_skills: [llm-wiki, typesafe-ai]
---

# Accurate research

Use this workflow for factual research. Keep findings separate from leads, record uncertainty, and preserve supported results with a review-by date.

## 1. Read saved findings first

Before searching, check for a personal vault: inspect `VAULT_PATH` and load the relevant vault skill if available. Otherwise, identify the project and load `llm-wiki` before using `<project>/wiki/`. Read the saved findings for this topic and their expiry dates. Reuse findings that are still in date only after checking that their cited sources remain available and relevant; treat expired findings as leads to re-check, not evidence.

Save the new or updated findings in that same destination. In a personal vault, follow its conventions. In a project wiki, follow `llm-wiki` conventions, including orientation, provenance, and index updates. Do not create a project wiki page without a clear project; ask which project if unclear.

## 2. Gather and read evidence

Search broadly for the claim and for primary material: original documents, datasets, statements, records, or first-hand reporting. Search results, snippets, previews, and AI-generated summaries are leads only. Evidence starts when you read the full source page. Use `web_extract` where available; if it truncates, read the saved full-text file. For JavaScript-heavy pages, use a browser. For inaccessible social posts, try a direct fetch or a suitable public API (for example, `api.fxtwitter.com` for X posts). If the source still cannot be read, do not treat its snippet or summary as evidence.

A finding is supported when either:

- At least one relevant primary source directly supports it; or
- At least three independent secondary sources support it.

Check independence: sources must not merely repeat one another, cite the same originating report, or come from the same origin. Trace copied claims to their original source. If neither threshold is met, label the finding **unconfirmed** and state what evidence is missing. Do not turn repetition into corroboration.

## 3. Search for counter-evidence

For every material claim, run at least one search specifically aimed at people or sources saying it is wrong. Use terms such as “false,” “incorrect,” “debunk,” “criticism,” or the known opposing position; search for primary evidence against it too. Read the full sources found, and assess whether they challenge the same claim and timeframe. Report counter-evidence even when it does not overturn the finding; explain material conflicts rather than hiding them.

## 4. Check each claim against its excerpt

Load the `typesafe-ai` skill for the current TypeSafe System One API instructions. When Jev is configured, submit each `(claim, source excerpt)` pair to Jev as a **Noul** question: “Does this excerpt support this claim?” Include enough excerpt context to judge the claim, and use the result as a check on the source-to-claim link, not as independent evidence or a truth verdict. The `SYSTEM_ONE_API` key may be available in the workspace `.env`; follow the `typesafe-ai` instructions and never expose the key.

A low support result means drop the claim or re-check the source and its context. Treat mid-range support as disputed. For a disputed claim, or when sources conflict, make a second pass with a reasoning model or subagent that reads the full sources and evaluates the disagreement. Keep its judgment distinct from source evidence. If Jev is not configured or cannot be used, perform the excerpt-to-claim check yourself and disclose that Jev was unavailable; do not imply it was run.

## 5. Label, disclose, and expire each finding

Give every finding one source label:

- **Primary** — supported directly by a relevant original or first-hand source.
- **Secondary** — supported by at least three independent secondary sources.
- **Unconfirmed** — neither evidence threshold is met, or a material dispute remains unresolved.

For each source, include its title, author or publisher, date when available, and direct link. Note a source author's relevant commercial interest when present (for example, selling a course, product, or service related to the claim). Do not infer that an author has no commercial interest when you have not checked.

Assign each finding a review-by / expiry date based on how quickly the subject changes: use a short interval for breaking news, active incidents, prices, or rapidly changing policy; a longer interval for stable historical or scientific facts. Choose and record an actual calendar date, not just an interval. Explain the date when it is not obvious. On later research, re-check expired findings from the beginning.

## Saved finding and final report format

Use this compact structure for each finding in both the saved note and final report:

```markdown
### <Claim>
- **Label:** primary | secondary | unconfirmed
- **Sources:** [Title — author/publisher, date](URL) — relevant excerpt or summary; commercial interest, if present
- **Counter-evidence found:** source links and what they challenge, or “No relevant counter-evidence found in the targeted search”
- **Expiry / review by:** YYYY-MM-DD
```

Keep the claim precise enough that evidence and counter-evidence can be evaluated against the same wording. State when the finding is disputed, when the targeted search found no counter-evidence, and when Jev was unavailable. A lack of counter-evidence is not proof of a claim.
