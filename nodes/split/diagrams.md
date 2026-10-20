# Split: diagrams

Back to [the factory](../../docs/factory.md).

## The belt

```mermaid
stateDiagram-v2
    [*] --> inbox: plan approved
    inbox --> working: run
    working --> done: tasks pass code checks
    working --> rejected: stop, malformed or failed
    done --> [*]
    rejected --> [*]
```
