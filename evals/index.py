"""Index of every eval trial, for comparisons across models, skills, harnesses and Ergon versions.

The trial folders stay the source of truth: they hold the whole traces. trials.sqlite is rebuilt from them, so a
change to its layout or one broken trial never loses evidence. Rebuild by hand with `python3 -B evals/index.py`;
evals/run.py rebuilds it after every batch.

A trial that started from an earlier trial's snapshot is kept but marked partial (full = 0); compare full trials
with full trials unless a question is about one node.

Example: pass rate per experiment and case
    select e.harness, e.models, t.case_name, avg(t.passed), count(*)
    from trial t join experiment e using (experiment_id) where t.full group by 1, 2, 3;
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

DB = "trials.sqlite"

SCHEMA = """
create table experiment (     -- what was tested; every comparison groups by it
    experiment_id text primary key,   -- hash of the columns below
    commit_sha text, dirty integer,
    harness text,                     -- hermes or agy
    harness_version text,             -- agy --version; empty for hermes
    models text,                      -- json: role -> model
    skills text                       -- json: skill -> hash
);
create table trial (          -- one run of one case under one experiment
    trial_id text primary key,        -- the trial folder's name
    experiment_id text references experiment,
    case_name text, case_version text,
    full integer,                     -- 0: started from a snapshot of an earlier trial
    start_node text, snapshot text,
    reached text, stopped_at text, reason text,
    client_rounds integer,
    started text, ended text, seconds real,
    passed integer
);
create table node_run (       -- what only the belt knows; time and tokens per node add up from agent_call
    trial_id text references trial, node text,
    working_seconds integer, waiting_seconds integer,   -- waiting held review time too before review_seconds
    review_seconds integer,
    primary key (trial_id, node)
);
create table agent_call (     -- one attempt by one agent
    trial_id text references trial, node text, run text, label text,
    model text, outcome text, reasons text,   -- reasons: json list
    inherited integer,                        -- 1: copied in from the snapshot, not run by this trial
    started text, seconds real,
    input_tokens integer, output_tokens integer, cache_read_tokens integer, reasoning_tokens integer,
    api_calls integer, tool_calls integer,
    tools text,                               -- json list, in call order
    primary key (trial_id, node, run, label)
);
create table hidden_test (
    trial_id text references trial, test text,
    tag text,                         -- stated: in the sources; ask: the planner had to ask the client
    facts text,                       -- json list of fact ids
    outcome text, detail text,
    primary key (trial_id, test)
);
create table finding (        -- what the audit flagged
    trial_id text references trial,
    kind text,     -- contract, contradiction_missed, contradiction_unplanted, cited_unread, task_without_command
    detail text
);
"""


def _experiment(identity: dict) -> tuple:
    row = (identity.get("commit", ""), int(bool(identity.get("dirty"))), identity.get("backend", "hermes"),
           identity.get("agy", ""), json.dumps(identity.get("models", {}), sort_keys=True),
           json.dumps(identity.get("skills", {}), sort_keys=True))
    return (hashlib.sha256(json.dumps(row).encode()).hexdigest()[:12], *row)


def _calls(trial_id: str, folder: Path, tools: dict, started: str) -> list:
    rows = []
    for log in sorted(folder.rglob("calls.jsonl")):
        rel = log.parent.relative_to(folder)
        parts = rel.parts   # project/.ergon/<node>/runs/<run>, or client
        if parts[:2] == ("project", ".ergon") and len(parts) > 4:   # build nests one folder per task under its run
            node, run = parts[2], "/".join(parts[4:])
        else:
            node, run = (parts or ("?",))[0], ""
        for line in log.read_text().splitlines():
            c = json.loads(line)
            used = tools.get(f"{node}/runs/{run}/{c['label']}", [])
            inherited = int(bool(started and c.get("started") and c["started"] < started))
            rows.append((trial_id, node, run, c["label"], c.get("model"), c.get("outcome"),
                         json.dumps(c.get("reasons", [])), inherited, c.get("started"), c.get("seconds"),
                         c.get("input_tokens"), c.get("output_tokens"), c.get("cache_read_tokens"),
                         c.get("reasoning_tokens"), c.get("api_call_count"), c.get("tool_call_count"),
                         json.dumps(used)))
    return rows


def _findings(trial_id: str, record: dict) -> list:
    out = [(trial_id, "contract", json.dumps(p) if not isinstance(p, str) else p)
           for p in record.get("contract_problems", [])]
    b = record.get("behavior", {})
    c = b.get("contradictions", {})
    out += [(trial_id, "contradiction_missed", k) for k, hit in c.get("planted", {}).items() if not hit]
    out += [(trial_id, "contradiction_unplanted", json.dumps(u)) for u in c.get("unplanted", [])]
    out += [(trial_id, "cited_unread", json.dumps(u)) for u in b.get("plan_cited_unread", [])]
    out += [(trial_id, "task_without_command", json.dumps(u)) for u in b.get("build_tasks_without_commands", [])]
    return out


def build(trials: Path, db: Path) -> int:
    """Rebuild the index from every trial folder that has a trial.json. Returns the number of trials indexed."""
    tmp = db.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    count = 0
    for folder in sorted(p for p in trials.iterdir() if (p / "trial.json").is_file()):
        try:
            r = json.loads((folder / "trial.json").read_text())
        except ValueError as exc:
            print(f"skipped {folder.name}: {exc}", file=sys.stderr)
            continue
        exp = _experiment(r.get("identity", {}))
        con.execute("insert or ignore into experiment values (?,?,?,?,?,?,?)", exp)
        tid = folder.name
        con.execute("insert into trial values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            tid, exp[0], r.get("case"), r.get("case_version"), int(not r.get("snapshot")),
            r.get("start"), r.get("snapshot") or None, r.get("reached"), r.get("stopped_at"), r.get("reason"),
            r.get("client_rounds"), r.get("started"), r.get("ended"), r.get("seconds"), int(bool(r.get("passed")))))
        for node, n in r.get("nodes", {}).items():
            if "working_seconds" in n:
                con.execute("insert into node_run values (?,?,?,?,?)",
                            (tid, node, n["working_seconds"], n.get("waiting_seconds"), n.get("review_seconds")))
        con.executemany("insert into agent_call values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        _calls(tid, folder, r.get("behavior", {}).get("tools", {}), r.get("started", "")))
        tests = folder / "hidden-tests.json"
        for t in json.loads(tests.read_text()) if tests.is_file() else []:
            con.execute("insert or replace into hidden_test values (?,?,?,?,?,?)", (
                tid, t["test"], t.get("tag"), json.dumps(t.get("facts", [])), t.get("outcome"), t.get("detail")))
        con.executemany("insert into finding values (?,?,?)", _findings(tid, r))
        count += 1
    con.commit()
    con.close()
    tmp.replace(db)
    return count


if __name__ == "__main__":
    root = Path(__file__).resolve().parent / "trials"
    print(f"indexed {build(root, root / DB)} trials into {root / DB}")
