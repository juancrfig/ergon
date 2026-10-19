# Ergon

A factory of nodes. A node turns a defined input into a structured output; its contract declares both. Terms:
`GLOSSARY.md`. Decisions: `docs/adr/`. Read a folder's AGENTS.md before working in it.

```text
README.md        the only README: for humans
GLOSSARY.md      one word per concept
docs/adr/        architecture decision records
docs/factory.md  the whole factory (Mermaid); update it with every change
bin/ergon        entry point
ergon/           the code shared by every node, plus one module per node
nodes/<node>/    a node: contracts (JSON Schemas) and diagrams.md (Mermaid, kept current)
profiles/<name>/ a node agent's skills
```

Rules for maintainers:
- Documentation for agents goes in AGENTS.md files, never in more READMEs (ADR 0009).
- Keep each AGENTS.md short: it lands in the context of every agent that works in its folder.
- A decision that changes how ergon works gets a new ADR before or with the change.
- Python standard library only. The gate: every module parses and `bin/ergon --help` runs.
