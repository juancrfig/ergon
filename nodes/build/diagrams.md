# Build: diagrams

Back to [the factory](../../docs/factory.md).

## The belt

```mermaid
stateDiagram-v2
    [*] --> inbox: Split's tasks pass
    inbox --> working: run
    working --> working: next task, one commit each
    working --> done: every task built
    working --> rejected: stop (back to Split), malformed or failed
    done --> [*]
    rejected --> [*]
```
