# Plan: diagrams

Back to [the factory](../../docs/factory.md).

## The belt

```mermaid
stateDiagram-v2
    [*] --> inbox: submit (schema check)
    inbox --> working: run
    working --> waiting: round returns questions
    waiting --> inbox: human answers (skipped = recommendation)
    working --> review: round returns stories
    working --> rejected: malformed or failed
    review --> done: human approves
    waiting --> rejected: human rejects
    review --> rejected: human rejects
    done --> [*]
    rejected --> [*]
```
