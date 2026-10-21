"""What a trial's records show: time and effort per node, contracts re-checked, and claims compared with actions.

Everything here reads files a trial left; nothing calls an agent. Sources:
- calls.jsonl in every run folder: each agent call's time, tokens and verdict (ergon/agent.py).
- events.jsonl on every belt: each request's moves, so time working and time waiting for the human.
- the saved requests and answers, re-checked against their contracts.
- the wiki tool's call logs and Hermes' session exports: what each agent really read and ran.
- each build task's commit: the project files its new code uses, against the files Split named (ADR 0030).
"""
import ast
import calendar
import subprocess
import json
import os
import re
import statistics
import time
from pathlib import Path

from ergon import schema
from ergon.node import NODES as CONTRACTS

NODES = ("intake", "plan", "split", "build")
TOKENS = ("input_tokens", "output_tokens", "cache_read_tokens", "reasoning_tokens")
# answer files each node saves, and the contract each must still satisfy
ANSWERS = {"intake": [(r"proposal\.json", "proposal.json"), (r"health-report\.json", "health-report.json")],
           "plan": [(r"round-\d+\.json", "round.json")],   # answers-N.json is Plan's record, not the contract's
           "split": [(r"tasks\.json", "tasks.json")],
           "build": [(r"result\.json", "result.json")]}


def trial(project: Path, client_dir: Path, spec: dict, start: str = "intake") -> dict:
    """A trial from a snapshot counts only the nodes it ran: the earlier ones' records came with the copy."""
    ergon = project / ".ergon"
    nodes = {n: _calls(ergon / n / "runs") for n in NODES[NODES.index(start):]}
    nodes["client"] = _calls(client_dir)
    for n in NODES[NODES.index(start):]:
        nodes[n].update(_belt_time(ergon / n / "events.jsonl"))
    return {"nodes": nodes, "contract_problems": _contracts(ergon), "behavior": _behavior(ergon, spec)}


# --- time and effort --------------------------------------------------------------------------------------------


def _calls(folder: Path) -> dict:
    rows = [json.loads(line) for f in sorted(folder.rglob("calls.jsonl")) for line in f.read_text().splitlines()
            if line.strip()] if folder.exists() else []
    out: dict = {"calls": len(rows), "agent_seconds": round(sum(r.get("seconds") or 0 for r in rows), 1)}
    for outcome in ("accepted", "rejected", "failed"):
        out[outcome] = sum(r["outcome"] == outcome for r in rows)
    out["tokens"] = {k: sum(r.get(k) or 0 for r in rows) for k in TOKENS}
    out["reasons"] = [f"{r['label']}: {reason}" for r in rows if r["outcome"] != "accepted" for reason in r["reasons"]]
    return out


def _belt_time(events: Path) -> dict:
    """Seconds requests spent working (code and agents), waiting for the human's answers (here the client agent) and
    in review until approved, from the belt's moves. Events are to the second. A plan's review time is mostly Intake
    writing its decisions into the wiki before approval (ADR 0028), which is Intake's agent time too."""
    out = {"working_seconds": 0, "waiting_seconds": 0, "review_seconds": 0}
    if not events.exists():
        return out
    since = {}
    for line in events.read_text().splitlines():
        e = json.loads(line)
        t = _seconds(e["time"])
        if e["id"] in since and e["from"] in ("working", "waiting", "review"):
            key = e["from"] + "_seconds"
            out[key] += t - since[e["id"]]
        since[e["id"]] = t
    return out


def _seconds(stamp: str) -> int:
    return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))


# --- contracts --------------------------------------------------------------------------------------------------


def _contracts(ergon: Path) -> list:
    """Every saved request and answer, checked again against its contract: a file code accepted and later changed,
    or a contract that changed under a saved answer, shows here."""
    out = []
    for node in NODES:
        contracts = CONTRACTS / node / "contracts"
        for state in ("inbox", "working", "waiting", "review", "done", "rejected"):
            for f in sorted((ergon / node / state).glob("*.json")):
                doc = json.loads(f.read_text())
                path = contracts / f"request.{doc.get('type')}.json"
                errs = schema.errors(doc, schema.load(path)) if path.exists() else [f"no contract for {doc.get('type')}"]
                out += [f"{node}/{f.stem}: {e}" for e in errs]
        for f in sorted((ergon / node / "runs").rglob("*.json")):
            for pattern, contract in ANSWERS[node]:
                if re.fullmatch(pattern, f.name):
                    errs = schema.errors(json.loads(f.read_text()), schema.load(contracts / contract))
                    out += [f"{node}/{f.relative_to(ergon / node / 'runs')}: {e}" for e in errs]
    return out


# --- claims against actions -------------------------------------------------------------------------------------


def _behavior(ergon: Path, spec: dict) -> dict:
    out = {}
    items = [i for f in sorted((ergon / "intake" / "runs").rglob("proposal.json"))
             for i in json.loads(f.read_text())["items"]]
    flagged = [i["text"] for i in items if i["kind"] == "contradiction" or i["status"] == "contradiction"]
    caught = {c["id"]: any(_matches(text, c["match"]) for text in flagged) for c in spec.get("contradictions", [])}
    out["contradictions"] = {"planted": caught, "flagged": len(flagged),
                             "unplanted": [t for t in flagged
                                           if not any(_matches(t, c["match"]) for c in spec.get("contradictions", []))]}
    # Plan: every page a story cites must be a page the planner read.
    read = set()
    for f in (ergon / "plan" / "runs").rglob("tool-calls-round-*.jsonl"):
        for line in f.read_text().splitlines():
            entry = json.loads(line)
            if entry.get("tool") == "read_pages":
                read.update(entry.get("found") or entry.get("asked") or [])
    cited = {p for f in (ergon / "plan" / "runs").rglob("stories.json") for s in json.loads(f.read_text())["stories"]
             for p in s["sources"]}
    out["plan_cited_unread"] = sorted(cited - read)
    # Every call: the tools it used, from its session; a builder task that ran no command checked nothing.
    tools = {}
    for f in sorted(ergon.rglob("*.session.jsonl")):
        tools[str(f.relative_to(ergon)).removesuffix(".session.jsonl")] = _tool_names(f)
    out["tools"] = tools
    out["files"] = _files(ergon)
    out["build_tasks_without_commands"] = sorted(
        str(f.parent.relative_to(ergon / "build" / "runs")) for f in (ergon / "build" / "runs").rglob("result.json")
        if not any(n == "terminal" for label, names in tools.items()
                   if label.startswith(str(f.parent.relative_to(ergon))) for n in names))
    return out


# --- the files Split named against the files the code needed --------------------------------------------------


def _files(ergon: Path) -> list:
    """Per build task: the files Split named (to change and to read), the project files the task's new Python code
    uses but does not change (needed), what Split missed and named for nothing, and the project files the builder
    opened that it was not given. Python, JavaScript and TypeScript; other languages show no needed files."""
    project, out = ergon.parent, []
    tasks, earlier = {}, {}
    for f in (ergon / "split" / "runs").rglob("tasks.json"):
        listed = json.loads(f.read_text()).get("tasks", [])   # none on a stop
        tasks[f.parent.name] = {t["id"]: t for t in listed}
        made = set()   # files the tasks before each one create
        for t in listed:
            earlier[(f.parent.name, t["id"])] = set(made)
            made |= {x["path"] for x in t["files"] if x["action"] == "create"}
    for built_file in sorted((ergon / "build" / "runs").rglob("built.json")):
        request = next((ergon / "build").glob(f"*/{built_file.parent.name}.json"), None)
        split = json.loads(request.read_text()).get("split") if request else None
        dirs = {d.name.split("-", 1)[1]: d for d in built_file.parent.iterdir() if d.is_dir()}
        for b in json.loads(built_file.read_text()):
            task = tasks.get(split, {}).get(b["task"])
            if not task:
                continue
            changed = {f["path"] for f in task["files"]}
            given = changed | set(task.get("read", []))
            needed = set()
            for repo, sha in b.get("commits", {}).items():
                needed |= _used(project, repo, sha)
            needed -= changed | _touched(project, b.get("commits", {}))
            opened = _opened(project, dirs.get(b["task"]))
            # A file an earlier task creates did not exist when Split read the code: missing it is a smaller miss.
            later = needed - given & earlier.get((split, b["task"]), set())
            out.append({"task": b["task"], "change": sorted(changed), "read": sorted(task.get("read", [])),
                        "needed": sorted(needed), "missing": sorted(needed - given - later),
                        "missing_from_earlier_task": sorted(later),
                        "extra": sorted(set(task.get("read", [])) - needed),
                        "found_by_builder": sorted(opened - given)})
    return out


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True).stdout


def _touched(project: Path, commits: dict) -> set:
    return {f"{repo}/{p}" for repo, sha in commits.items()
            for p in _git(project / repo, "show", "--name-only", "--format=", sha).split()}


def _used(project: Path, repo: str, sha: str) -> set:
    """Project modules referenced on the lines a commit added to its Python files, as project-relative paths."""
    root, used = project / repo, set()
    tree_now = set(_git(root, "ls-tree", "-r", "--name-only", sha).split())
    tree_before = set(_git(root, "ls-tree", "-r", "--name-only", f"{sha}^").split())
    for path in _git(root, "show", "--name-only", "--format=", sha).split():
        if not path.endswith(".py") and not path.endswith(JS):
            continue
        added = set()
        for hunk in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", _git(root, "show", "--format=", "-U0", sha, "--", path),
                                re.M):
            start, count = int(hunk[1]), int(hunk[2] or 1)
            added.update(range(start, start + count))
        if path.endswith(JS):
            used |= _used_js(root, sha, path, added, tree_now, tree_before)
            continue
        try:
            tree = ast.parse(_git(root, "show", f"{sha}:{path}"))
        except SyntaxError:
            continue
        try:
            before = _imports(tree_before, path, ast.parse(_git(root, "show", f"{sha}^:{path}")))
        except SyntaxError:
            before = {}
        names = _imports(tree_now, path, tree)
        used |= {target for name, target in names.items() if name not in before}   # a newly imported module
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in names and node.lineno in added:
                used.add(names[node.id])
    return {f"{repo}/{p}" for p in used}


JS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
# import a, {b, c as d} from './m' · import * as ns from './m' · import './m' · export ... from './m' ·
# const x = require('./m') · const {a, b} = require('./m'). Only relative paths are project files.
JS_IMPORT = re.compile(r"""(?:import\s+(?P<what>[^'"]*?)\s+from\s+|import\s+|export\s+[^'"]*?\s+from\s+|"""
                       r"""(?:const|let|var)\s+(?P<bound>[\w${}\s,:]+?)\s*=\s*require\(\s*)['"](?P<spec>\.{1,2}/[^'"]+)['"]""")


def _used_js(root: Path, sha: str, path: str, added: set, tree_now: set, tree_before: set) -> set:
    """The JavaScript and TypeScript version of _used for one file: modules it newly imports, and modules whose
    imported names appear on the lines the commit added. Read with patterns, not a parser: a close count."""
    def imports(text: str, files: set) -> dict:
        names = {}
        for m in JS_IMPORT.finditer(text):
            target = _js_module(files, path, m["spec"])
            if not target:
                continue
            what = m["what"] or m["bound"] or ""
            local = re.findall(r"(?:\w+\s+as\s+|\w+\s*:\s*)?([A-Za-z_$][\w$]*)", what.replace("* as", ""))
            for name in local or [f"<{target}>"]:   # a bare import still uses the module
                names[name] = target
        return names
    now = imports(_git(root, "show", f"{sha}:{path}"), tree_now)
    before = imports(_git(root, "show", f"{sha}^:{path}"), tree_before)
    used = {target for name, target in now.items() if name not in before}
    lines = _git(root, "show", f"{sha}:{path}").splitlines()
    text = "\n".join(lines[n - 1] for n in sorted(added) if 0 < n <= len(lines))
    used |= {target for name, target in now.items() if re.search(rf"(?<![\w$]){re.escape(name)}(?![\w$])", text)}
    return used


def _js_module(files: set, path: str, spec: str) -> str | None:
    """The repo file a relative import points at: as written, with an extension, or its folder's index file."""
    target = os.path.normpath(str(Path(path).parent / spec))
    stem = re.sub(r"\.(js|jsx|mjs|cjs)$", "", target)   # TypeScript imports name the .js the build will emit
    for candidate in [target] + [stem + ext for ext in JS] + [f"{target}/index{ext}" for ext in JS]:
        if candidate in files:
            return candidate
    return None


def _imports(files: set, path: str, tree: ast.AST) -> dict:
    """Local name -> the repo file it was imported from, for every import of a file."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = _module(files, path, node.module, node.level)
            for alias in node.names:
                sub = _module(files, path, f"{node.module}.{alias.name}" if node.module else alias.name, node.level)
                if sub or base:
                    names[alias.asname or alias.name] = sub or base
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _module(files, path, alias.name, 0)
                if target:
                    names[alias.asname or alias.name.split(".")[0]] = target
    return names


def _module(files: set, path: str, module: str | None, level: int) -> str | None:
    """The repo file a module name points at, or None when it is not among the commit's files."""
    base = Path(path).parent
    for _ in range(max(level - 1, 0)):
        base = base.parent
    if not level:
        base = Path()
    parts = (module or "").split(".") if module else []
    target = base.joinpath(*parts)
    for candidate in (target.with_suffix(".py"), target / "__init__.py"):
        if parts and str(candidate) in files:
            return str(candidate)
    return None


def _opened(project: Path, run_dir: Path | None) -> set:
    """Project files the builder opened with a file tool or named in a command, from its session."""
    found = set()
    if not run_dir:
        return found
    for f in run_dir.glob("*.session.jsonl"):
        text = f.read_text()
        for raw in re.findall(r'"(?:AbsolutePath|path|file_path|CommandLine)"\s*:\s*"((?:[^"\\]|\\.)*)"', text):
            for word in re.split(r"[\s'\"]+", raw):
                p = Path(word) if word.startswith("/") else None
                if p and p.is_relative_to(project) and p.is_file() and ".ergon" not in p.parts:
                    found.add(str(p.relative_to(project)))
    return found


def _matches(text: str, groups: list) -> bool:
    """A contradiction matches when the text holds a word from every group."""
    low = text.lower()
    return all(any(word in low for word in group) for group in groups)


def _tool_names(session_file: Path) -> list:
    """Every tool call in a Hermes session export or an agy step stream, in order. agy's run_command counts as
    terminal. The export's shape is Hermes', so search it loosely."""
    names = []

    def walk(node):
        if isinstance(node, dict):
            step = node.get("step_update")   # agy's stream: one DONE step per tool call
            if isinstance(step, dict) and step.get("step_type") == "tool" and step.get("state") == "DONE":
                name = step.get("tool_name") or "?"
                names.append("terminal" if name == "run_command" else name)
            for call in node.get("tool_calls") or []:
                if isinstance(call, dict):
                    names.append((call.get("function") or {}).get("name") or call.get("name") or "?")
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for line in session_file.read_text().splitlines():
        if line.strip():
            walk(json.loads(line))
    return names


# --- the report -------------------------------------------------------------------------------------------------


def report(records: list) -> str:
    lines = ["# Eval report", ""]
    for case in sorted({r["case"] for r in records}):
        mine = [r for r in records if r["case"] == case]
        passed = sum(r["passed"] for r in mine)
        lines += [f"## {case}", f"- **Trials:** {len(mine)} · passed {passed} · pass^{len(mine)} "
                                f"{'yes' if passed == len(mine) else 'no'}"
                  + ("" if all(r.get("start", "intake") == "intake" for r in mine)
                     else " · ask tests not counted: the saved plan already asked or missed them")]
        tags = {}
        for r in mine:
            for tag, s in r.get("tests", {}).items():
                tags.setdefault(tag, [0, 0])
                tags[tag][0] += s["passed"]
                tags[tag][1] += s["total"]
        lines.append("- **Hidden tests:** " + (" · ".join(f"{t} {p}/{n}" for t, (p, n) in tags.items()) or "none ran"))
        stops = [f"{r['stopped_at']}" for r in mine if r["stopped_at"]]
        if stops:
            lines.append("- **Stopped at:** " + ", ".join(stops))
        lines.append(f"- **Wall time:** median {statistics.median(r['seconds'] for r in mine):.0f}s")
        for node in (*NODES, "client"):
            n = [r["nodes"][node] for r in mine if node in r["nodes"]]
            if not n or not sum(x["calls"] for x in n):
                continue
            tokens = sum(x["tokens"]["input_tokens"] + x["tokens"]["output_tokens"] for x in n)
            lines.append(f"- **{node}:** {sum(x['calls'] for x in n)} calls ({sum(x['rejected'] for x in n)} rejected, "
                         f"{sum(x['failed'] for x in n)} failed) · agent {sum(x['agent_seconds'] for x in n):.0f}s"
                         + (f" · waiting {sum(x['waiting_seconds'] for x in n)}s"
                            f" · in review {sum(x.get('review_seconds') or 0 for x in n)}s" if node != "client" else "")
                         + f" · {tokens} tokens")
        planted = [ok for r in mine for ok in r["behavior"]["contradictions"]["planted"].values()]
        if planted:
            lines.append(f"- **Contradictions caught:** {sum(planted)}/{len(planted)}")
        unplanted = sum(len(r["behavior"]["contradictions"]["unplanted"]) for r in mine)
        if unplanted:
            lines.append(f"- **Contradictions flagged but not planted:** {unplanted}")
        problems = [p for r in mine for p in r["contract_problems"]]
        lines.append(f"- **Contract re-check:** {len(problems)} problems" + "".join(f"\n  - {p}" for p in problems[:10]))
        unread = sorted({p for r in mine for p in r["behavior"]["plan_cited_unread"]})
        if unread:
            lines.append("- **Plan cites pages it never read:** " + ", ".join(unread))
        blind = [t for r in mine for t in r["behavior"]["build_tasks_without_commands"]]
        if blind:
            lines.append(f"- **Build tasks that ran no command:** {len(blind)}")
        files = [f for r in mine for f in r["behavior"].get("files", [])]
        if files:
            lines.append(f"- **Files per build task ({len(files)} tasks):** "
                         f"needed {sum(len(f['needed']) for f in files)} · missing {sum(len(f['missing']) for f in files)}"
                         f" · missing, made by an earlier task "
                         f"{sum(len(f.get('missing_from_earlier_task', [])) for f in files)}"
                         f" · named to read for nothing {sum(len(f['extra']) for f in files)}"
                         f" · opened by the builder, not given {sum(len(f['found_by_builder']) for f in files)}")
            for f in files:
                later = f.get("missing_from_earlier_task", [])
                if f["missing"] or later or f["extra"]:
                    lines.append(f"  - {f['task']}: missing {', '.join(f['missing']) or '-'}; "
                                 + (f"made by an earlier task {', '.join(later)}; " if later else "")
                                 + f"extra {', '.join(f['extra']) or '-'}")
        lines.append("- **Trials:** " + ", ".join(r["trial"] for r in mine))
        lines.append("")
    return "\n".join(lines)
