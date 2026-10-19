# Ergon: current state

Updated with every change to ergon. Solid boxes are built; dashed boxes are designed but not built.

## The factory

```mermaid
flowchart LR
    raw([Raw information]) --> intake
    intake[Intake<br/>wiki-maintainer] --> wiki[(Project wiki)]
    wiki --> plan
    human((Human)) -. answers, approval .-> plan
    plan[Plan] -. user stories .-> split[Split]
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
    class intake,wiki built;
    class plan,split,build,gate,inspect,merge,learn todo;
```

## Intake: the belt

```mermaid
stateDiagram-v2
    [*] --> inbox: submit (schema check)
    inbox --> working: run
    inbox --> rejected: human rejects
    working --> rejected: malformed, duplicate or failed
    working --> review: proposal drafted (ingest, correct)
    working --> done: report written (health check)
    review --> done: human approves, code writes the wiki
    review --> rejected: human rejects
    done --> [*]
    rejected --> [*]
```

## Intake: who does what in one ingest

```mermaid
sequenceDiagram
    participant S as Sender
    participant C as Code
    participant A as wiki-maintainer
    participant H as Human
    S->>C: request (JSON)
    C->>C: check schema, context gate, fetch source, skip duplicates
    C->>A: entire context, built by code
    A->>C: proposal (JSON)
    C->>C: check citations, links, tags, length
    C-->>A: errors (at most 2 retries)
    C->>H: proposal waits in review
    H->>C: approve
    C->>C: write pages, index, log, commit, ledger
    C->>S: result in reply_to
```
