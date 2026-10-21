"""Run Ergon's evals: one command for one case, several, or all (docs/evals.md).

    python3 evals/run.py                       every case, one trial each
    python3 evals/run.py todo-cli -k 3         three trials of one case
    python3 evals/run.py --check               no agent: each case's reference must pass its hidden tests, and an
                                               empty program must fail them
    python3 evals/run.py todo-cli --from split --snapshot evals/trials/<trial>
                                               repeat Split and Build on an earlier trial's approved plan

A trial is one attempt at a case in a fresh folder: Intake ingests the sources, Plan asks the client agent its
questions, every approval is automatic, Split and Build run, and the hidden tests grade the result. The trial folder
never holds the brief, the hidden tests or the reference. Trials run in parallel, one thread each.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from ergon import agent, profiles  # noqa: E402
from ergon.build import Build  # noqa: E402
from ergon.intake import Intake  # noqa: E402
from ergon.plan import Plan  # noqa: E402
from ergon.split import Split  # noqa: E402
from evals import audit, index  # noqa: E402

CASES, TRIALS = ROOT / "cases", ROOT / "trials"
NODES = ("intake", "plan", "split", "build")
CLIENT = "client"   # Hermes profile of the simulated client: the cheap model class
AUTHOR = ["-c", "user.name=Eval", "-c", "user.email=eval@localhost"]


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def hidden_tests(case: Path, app: Path) -> list:
    """One row per hidden test, run in a separate process so a broken program cannot stop the harness."""
    result = subprocess.run([sys.executable, "-B", str(ROOT / "testrun.py"), str(case / "hidden-tests"), str(app)],
                            capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise RuntimeError(f"hidden tests did not run: {result.stderr[-2000:]}")
    return json.loads(result.stdout)


def case_version(case: Path) -> str:
    """A hash of every file of the case: a changed brief or hidden test makes older scores incomparable."""
    digest = hashlib.sha256()
    for f in sorted(p for p in case.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(str(f.relative_to(case)).encode() + b"\0" + f.read_bytes() + b"\0")
    return digest.hexdigest()[:12]


def scores(rows: list) -> dict:
    out = {}
    for tag in ("stated", "ask", "kept", "rule", "untagged"):
        mine = [r for r in rows if r["tag"] == tag]
        if mine:
            out[tag] = {"passed": sum(r["outcome"] == "pass" for r in mine), "total": len(mine)}
    return out


# --- one trial -------------------------------------------------------------------------------------------------


class Trial:
    def __init__(self, case: Path, number: int, start: str = "intake", snapshot: Path | None = None):
        self.case, self.spec = case, json.loads((case / "case.json").read_text())
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.dir = TRIALS / f"{stamp}-{case.name}-{number}"
        self.project = self.dir / "project"
        self.start, self.snapshot = start, snapshot
        self.record = {"case": case.name, "case_version": case_version(case), "trial": self.dir.name, "start": start,
                       "snapshot": str(snapshot or ""),
                       "reached": None, "stopped_at": None, "reason": None, "client_rounds": 0}

    def log(self, text: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {self.dir.name}: {text}"
        print(line, flush=True)
        with (self.dir / "trial.log").open("a") as f:
            f.write(line + "\n")

    def run(self) -> dict:
        self.dir.mkdir(parents=True)
        # The project runs in an empty folder outside the repo, so no agent finds the cases, the hidden tests, the
        # client's brief or other trials next to it; it moves into the trial folder when the trial ends.
        self.project = Path(tempfile.mkdtemp(prefix=f"ergon-{self.dir.name}-", dir="/tmp")) / "project"
        clock, started = time.monotonic(), _now()
        try:
            self._prepare()
            for node in NODES[NODES.index(self.start):]:
                if not getattr(self, f"_{node}")():
                    self.record["stopped_at"] = node
                    break
                self.record["reached"] = node
        except Exception as exc:   # a harness or Ergon crash is a finding too: record it and grade what exists
            self.record.update(stopped_at=self.record["stopped_at"] or "harness", reason=f"{type(exc).__name__}: {exc}")
            (self.dir / "crash.txt").write_text(traceback.format_exc())
            self.log(f"crashed: {exc}")
        self.record.update(started=started, ended=_now(), seconds=round(time.monotonic() - clock, 1))
        if self.project.exists():
            shutil.move(self.project, self.dir / "project")
            self.project.parent.rmdir()
        self.project = self.dir / "project"
        self._grade()
        self.record.update(audit.trial(self.project, self.dir / "client", self.spec, self.start))
        (self.dir / "trial.json").write_text(json.dumps(self.record, indent=2) + "\n")
        self.log(f"finished in {self.record['seconds']}s: {summary(self.record)}")
        return self.record

    # --- setting up --------------------------------------------------------------------------------------------

    def _prepare(self) -> None:
        if self.snapshot:
            self._from_snapshot()
            return
        self.project.mkdir()
        git(self.project, "init", "-q", "-b", "main")
        git(self.project, "config", "user.name", "Eval")   # Intake commits the wiki here
        git(self.project, "config", "user.email", "eval@localhost")
        (self.project / ".gitignore").write_text(".ergon/\n" + "".join(f"/{r}/\n" for r in self.spec["repos"]))
        git(self.project, "add", ".gitignore")
        git(self.project, *AUTHOR, "commit", "-q", "-m", "eval project")
        for node in (Intake, Plan, Split, Build):
            node(self.project).belt.create()
        raw = self.project / "wiki" / "raw"
        (self.project / "wiki" / "pages").mkdir(parents=True)
        shutil.copytree(self.case / "sources", raw)
        for name, seed in self.spec["repos"].items():
            repo = self.project / name
            if seed:
                shutil.copytree(self.case / seed, repo)
            else:   # the verification skill the human writes before the first ticket (ADR 0033)
                shutil.copytree(self.case / "verify", repo / ".agents" / "skills" / "verify")
                (repo / ".gitignore").write_text("__pycache__/\n.verify/\n")
            git(repo, "init", "-q", "-b", "main")
            git(repo, "add", "-A")
            git(repo, *AUTHOR, "commit", "-q", "--allow-empty", "-m", "start")

    def _from_snapshot(self) -> None:
        """Copy an earlier trial's project, then drop every belt from the start node on and reset the repos, so the
        start node runs fresh on the earlier nodes' approved output."""
        assert self.snapshot
        shutil.copytree(Path(self.snapshot) / "project", self.project, symlinks=True)
        for node in NODES[NODES.index(self.start):]:
            shutil.rmtree(self.project / ".ergon" / node, ignore_errors=True)
            {"intake": Intake, "plan": Plan, "split": Split, "build": Build}[node](self.project).belt.create()
        for name in self.spec["repos"]:
            repo = self.project / name
            git(repo, "checkout", "-q", "-f", "main")
            git(repo, "clean", "-q", "-fdx")
            for branch in git(repo, "branch", "--format=%(refname:short)").split():
                if branch != "main":
                    git(repo, "branch", "-q", "-D", branch)
        if self.start == "intake":
            raise ValueError("--from intake needs no snapshot")
        if self.start == "split":
            plan = Plan(self.project).belt.ids("done")[-1]
            Split(self.project).submit({"type": "split", "from": "eval", "plan": plan})
        elif self.start == "build":
            split = Split(self.project).belt.ids("done")[-1]
            Build(self.project).submit({"type": "build", "from": "eval", "split": split})

    # --- the nodes, with the human's part played by code and the client agent -----------------------------------

    def _intake(self) -> bool:
        intake = Intake(self.project)
        for source in sorted((self.project / "wiki" / "raw").iterdir()):
            rid = intake.submit({"type": "ingest", "from": "eval", "source": f"wiki/raw/{source.name}"})
            intake.run(log=self.log)
            if intake.belt.state_of(rid) != "review":
                return self._stop(intake, rid)
            self.log(intake.approve(rid))
        return True

    def _plan(self) -> bool:
        plan = Plan(self.project)
        rid = plan.submit({"type": "plan", "from": "eval", "ticket": self.case.name, "goal": self.spec["goal"]})
        while True:
            plan.run(log=self.log)
            state = plan.belt.state_of(rid)
            if state == "waiting":
                self.log(plan.answer(rid, self._client(plan, rid)))
            elif state == "review":
                intake = Intake(self.project)   # the plan's decisions go into the wiki before approval (ADR 0028)
                intake.run(log=self.log)
                self.log(plan.approve(rid))
                return True
            else:
                return self._stop(plan, rid)

    def _split(self) -> bool:
        split = Split(self.project)
        split.run(log=self.log)
        rid = split.belt.ids("done")[-1:] or split.belt.ids("rejected")[-1:]
        return bool(split.belt.ids("done")) or self._stop(split, rid[0] if rid else None)

    def _build(self) -> bool:
        build = Build(self.project)
        build.run(log=self.log)
        rid = build.belt.ids("done")[-1:] or build.belt.ids("rejected")[-1:]
        return bool(build.belt.ids("done")) or self._stop(build, rid[0] if rid else None)

    def _stop(self, node, rid) -> bool:
        reason = node.belt.run_dir(rid) / "rejected.txt" if rid else None
        self.record["reason"] = reason.read_text().strip() if reason and reason.exists() else f"no request reached done"
        self.log(f"{node.name} stopped: {self.record['reason'][:300]}")
        return False

    def _client(self, plan: Plan, rid: str) -> dict:
        """The client agent answers one round, from the brief and the sources only. Its own run folder, outside the
        project, so no node can read it."""
        self.record["client_rounds"] += 1
        number = self.record["client_rounds"]
        run_dir, empty = self.dir / "client", self.dir / "client" / "no-pages"
        empty.mkdir(parents=True, exist_ok=True)
        agent.scope(run_dir, empty, f"tool-calls-round-{number}.jsonl")
        questions = json.loads((plan.belt.run_dir(rid) / f"round-{number}.json").read_text())["questions"]
        sources = "\n\n".join(f"## {p.name}\n\n{p.read_text().strip()}" for p in sorted((self.case / "sources").iterdir()))
        prompt = "\n\n".join([
            (ROOT / "client.md").read_text().strip(), "# Your brief", (self.case / "brief.md").read_text().strip(),
            "# What you and the people around you already sent the developers", sources,
            "# The developers' questions", json.dumps(questions, indent=2)]) + "\n"
        return agent.ask(CLIENT, prompt, Plan(self.project).contracts / "answers.json", run_dir, f"answers-{number}",
                         lambda a: [f"{x['question']} is not a question of this round" for x in a["answers"]
                                    if x["question"] not in {q["id"] for q in questions}])

    # --- grading ------------------------------------------------------------------------------------------------

    def _grade(self) -> None:
        app = self.project / next(iter(self.spec["repos"]))
        rows = hidden_tests(self.case, app) if app.is_dir() else []
        (self.dir / "hidden-tests.json").write_text(json.dumps(rows, indent=2) + "\n")
        self.record["tests"] = scores(rows)
        # From a saved plan, the questions are already asked or missed: an ask test grades that plan, not this run.
        graded = [r for r in rows if self.start == "intake" or r["tag"] != "ask"]
        self.record["passed"] = bool(graded) and all(r["outcome"] == "pass" for r in graded)


def identity() -> dict:
    """The Ergon commit (and whether the tree had changes), a hash of every node skill, and each profile's model."""
    repo = ROOT.parent
    out = {"commit": git(repo, "rev-parse", "--short", "HEAD").strip(),
           "dirty": bool(git(repo, "status", "--porcelain", "--", "ergon", "agents", "nodes").strip()),
           "skills": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:12] for p in sorted(profiles.SKILLS.glob("*.md"))},
           "backend": profiles.backend(), "models": {}}
    if profiles.backend() == "agy":
        out["agy"] = subprocess.run(["agy", "--version"], capture_output=True, text=True).stdout.strip()
    for profile in (CLIENT, *(n.profile for n in (Intake, Plan, Split, Build))):
        if profiles.backend() == "agy":
            out["models"][profile] = profiles.AGY_MODEL
            continue
        config = (profiles.installed(profile) / "config.yaml").read_text()
        found = re.search(r"^model:\n  default: (\S+)", config, re.M)
        out["models"][profile] = found.group(1) if found else None
    return out


def summary(record: dict) -> str:
    tests = " ".join(f"{t} {s['passed']}/{s['total']}" for t, s in record.get("tests", {}).items())
    end = "built" if record["reached"] == "build" else f"stopped at {record['stopped_at']}"
    return f"{end}; tests {tests or 'none'}; {'PASS' if record['passed'] else 'FAIL'}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- the check without agents ----------------------------------------------------------------------------------


def check(cases: list) -> bool:
    """A case is sound when its reference passes every hidden test, an empty program fails every stated and ask
    test, and its seed (if any) passes every kept test."""
    ok = True
    for case in cases:
        spec = json.loads((case / "case.json").read_text())
        problems = [f"{r['test']}: {r['outcome']}" for r in hidden_tests(case, case / "reference")
                    if r["outcome"] != "pass"]
        problems += [f"{r['test']}: untagged" for r in hidden_tests(case, case / "reference") if r["tag"] == "untagged"]
        with tempfile.TemporaryDirectory() as empty:
            problems += [f"{r['test']}: an empty program passes it" for r in hidden_tests(case, Path(empty))
                         if r["outcome"] == "pass"]
        seed = next(iter(spec["repos"].values()))
        if seed:
            problems += [f"{r['test']}: the seed fails a kept test" for r in hidden_tests(case, case / seed)
                         if r["tag"] == "kept" and r["outcome"] != "pass"]
        skill = (case / seed / ".agents/skills/verify") if seed else case / "verify"
        problems += [f"{skill.relative_to(case)}/{f} is missing" for f in ("SKILL.md", "FEATURES.md", "app")
                     if not (skill / f).exists()]
        for name in ("brief.md", "sources"):
            if not (case / name).exists():
                problems.append(f"{name} is missing")
        print(f"{case.name}: " + ("ok" if not problems else "BROKEN\n  " + "\n  ".join(problems)))
        ok = ok and not problems
    return ok


# --- the command ------------------------------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="evals/run.py")
    parser.add_argument("cases", nargs="*", help="case names (default: every case)")
    parser.add_argument("-k", "--trials", type=int, default=1, help="trials per case")
    parser.add_argument("-j", "--jobs", type=int, default=3, help="trials running at once")
    parser.add_argument("--from", dest="start", choices=NODES, default="intake", help="first node to run")
    parser.add_argument("--snapshot", type=Path, help="earlier trial folder to start from (with --from)")
    parser.add_argument("--check", action="store_true", help="check the cases without running any agent")
    parser.add_argument("--agent", choices=("hermes", "agy"), help="who runs every agent (default: ERGON_AGENT, "
                        "else hermes); agy runs every role on one model")
    parser.add_argument("--model", help="the agy model (default: ERGON_AGY_MODEL, else gemini-3.8-flash-medium)")
    args = parser.parse_args(argv)

    names = args.cases or sorted(p.name for p in CASES.iterdir() if (p / "case.json").exists())
    cases = [CASES / n for n in names]
    missing = [c.name for c in cases if not (c / "case.json").exists()]
    if missing:
        print(f"no such case: {', '.join(missing)}", file=sys.stderr)
        return 1
    if args.check:
        return 0 if check(cases) else 1
    if (args.start != "intake") != bool(args.snapshot) or (args.snapshot and len(cases) != 1):
        print("--from needs --snapshot of an earlier trial of the one case named, and --snapshot needs --from",
              file=sys.stderr)
        return 1
    if args.agent:
        os.environ["ERGON_AGENT"] = args.agent
    if args.model:
        os.environ["ERGON_AGY_MODEL"] = profiles.AGY_MODEL = args.model
    if not check(cases):
        return 1
    for profile in (CLIENT, *(n.profile for n in (Intake, Plan, Split, Build))):
        profiles.require(profile)
    TRIALS.mkdir(exist_ok=True)
    who = identity()
    trials = [Trial(c, n, args.start, args.snapshot) for c in cases for n in range(1, args.trials + 1)]
    for t in trials:   # same second: make each folder name unique
        while any(o is not t and o.dir == t.dir for o in trials) or t.dir.exists():
            t.dir = t.dir.with_name(t.dir.name + "x")
            t.record["trial"] = t.dir.name
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        records = list(pool.map(Trial.run, trials))
    for record in records:   # what ran: the same case on another commit, skill or model is another experiment
        record["identity"] = who
        (TRIALS / record["trial"] / "trial.json").write_text(json.dumps(record, indent=2) + "\n")
    index.build(TRIALS, TRIALS / index.DB)
    report = audit.report(records)
    out = TRIALS / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-report.md"
    out.write_text(report)
    print("\n" + report + f"\nReport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
