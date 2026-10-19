# Ergon: the factory

The whole factory. Solid boxes are built; dashed boxes are designed but not built.
Each built node draws its own internals in `nodes/<node>/diagrams.md`.

## The factory

```mermaid
flowchart LR
    raw([Raw information]) --> intake
    intake[Intake<br/>wiki-maintainer] --> wiki[(Project wiki)]
    wiki --> plan
    human((Human)) -- answers, approval --> plan
    plan[Plan<br/>planner] -. user stories .-> split[Split]
    split -. tasks .-> build[Build]
    build -. change .-> gate[Gate]
    gate -. pass .-> inspect[Inspect]
    inspect -. PASS .-> merge[Merge]
    inspect -. FAIL .-> build
    merge -. evidence .-> learn[Learn]
    learn -. profile changes .-> human
    human -- approves proposals --> intake

    classDef built fill:#d4edda,stroke:#2e7d32,stroke-width:2px;
    classDef todo fill:#f5f5f5,stroke:#9e9e9e,stroke-dasharray:5 5;
    class intake,wiki,plan built;
    class split,build,gate,inspect,merge,learn todo;
```

## Nodes

- [Intake](../nodes/intake/diagrams.md)
- [Plan](../nodes/plan/diagrams.md)
