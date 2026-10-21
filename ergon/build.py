"""The Build node. Input: the tasks Split made for one plan. Output: one commit per task on the plan's branch, in
every repo the task changes (ADR 0023, 0024).

The builder is a cheap model with the terminal and file tools. It carries out one task at a time, in Split's
order, and makes no design decision: a task that leaves one open is a stop, the architect's failure. Code checks
what changed against the task and replays the builder's proof of every criterion (ADR 0033), then commits; the
builder never runs git. Gate is not built yet.
A stop is a rejection; sending it back to Split is not built.
"""
import json
import subprocess
from pathlib import Path

from ergon import agent, profiles, proof
from ergon.node import Node, repos
from ergon.plan import Plan, criteria, story_text
from ergon.split import Split

SKILL = profiles.SKILLS / "building.md"
MAX_TURNS = 60   # ADR 0023
AUTHOR = ["-c", "user.name=Ergon", "-c", "user.email=ergon@localhost"]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} in {root.name} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def changed(root: Path) -> list[str]:
    """The paths git sees as changed, added or deleted, untracked files included and ignored ones not."""
    lines = git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
    return sorted(line[3:].split(" -> ")[-1].strip('"') for line in lines)


# Files tools write when the builder runs code or tests. Never the builder's change: git ignores them in this clone
# only (.git/info/exclude), so they are neither checked against the task nor committed.
CACHES = ("__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", "node_modules/.cache/")


def _ignore_caches(root: Path) -> None:
    exclude = root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    have = exclude.read_text().splitlines() if exclude.exists() else []
    missing = [c for c in CACHES if c not in have]
    if missing:
        with exclude.open("a") as f:
            f.write("".join(f"{c}\n" for c in missing))


class Build(Node):
    name, profile, types = "build", "builder", ("build",)

    def handle(self, rid: str, request: dict) -> str:
        plan, tasks = Split(self.project).tasks(request["split"])
        stories = Plan(self.project).approved(plan)
        found = repos(self.project)
        used = {r: found[r] for t in tasks for r in t["repos"] if r in found}
        branch = f"plan/{plan}"
        for root in used.values():       # code owns the branches (ADR 0023)
            if changed(root):
                raise ValueError(f"repo {root.name} has uncommitted changes; commit or stash them first")
        absent = proof.missing(used)   # ADR 0033: no verification skill, no build
        if absent:
            raise ValueError("no verification skill: run the wizard in each repo first; missing " + ", ".join(absent))
        for root in used.values():
            _ignore_caches(root)
            exists = git(root, "branch", "--list", branch).strip()
            git(root, "checkout", "-q", *([branch] if exists else ["-b", branch]))
        run_dir = self.belt.run_dir(rid)
        built_path = run_dir / "built.json"
        built = self._built_before(rid, request["split"], tasks)
        built_path.write_text(json.dumps(built, indent=2) + "\n")
        done = {b["task"] for b in built}
        for n, task in enumerate(tasks, 1):
            if task["id"] in done:
                continue
            task_dir = run_dir / f"{n:02d}-{task['id']}"
            agent.scope(task_dir, self.wiki.pages_dir)
            try:
                answer = agent.ask(self.profile, self._context(task, tasks[:n - 1], stories, found),
                                   self.contracts / "result.json", task_dir, "result", lambda a: _problems(a, task, used, task_dir),
                                   tools=("terminal", "file"),
                                   turns=MAX_TURNS, cwd=self.project, yolo=True)
            except agent.AgentError:
                _discard(task_dir, used)
                raise
            if "stop" in answer:
                _discard(task_dir, used)
                stop = answer["stop"]
                self.belt.reject(rid, "working", f"stopped at task {task['id']}: {stop['reason']}\n"
                                                 f"Question: {stop['question']}")
                return f"stopped at task {task['id']}: {stop['question']}"
            commits = {}
            for name in task["repos"]:
                root = used[name]
                if changed(root):
                    git(root, "add", "-A")
                    git(root, *AUTHOR, "commit", "-q", "-m", f"{task['id']}: {task['title']}\n\nPlan {plan}, "
                        f"Ergon build {rid}.\nCovers: {', '.join(task['covers'])}")
                    commits[name] = git(root, "rev-parse", "--short", "HEAD").strip()
            built.append({"task": task["id"], "outcome": "change" if commits else "no change", "commits": commits})
            built_path.write_text(json.dumps(built, indent=2) + "\n")
        self.belt.move(rid, "working", "done")
        return f"{len(tasks)} tasks built on branch {branch}"

    def _built_before(self, rid: str, split: str, tasks: list) -> list:
        """Tasks of this split an earlier build of it recorded, so a resubmitted build picks up where the last one
        stopped. Each build records a task right after committing it."""
        built = {}
        for state in ("done", "rejected"):
            for other in self.belt.ids(state):
                path = self.belt.run_dir(other) / "built.json"
                if other != rid and self.belt.read(other).get("split") == split and path.exists():
                    built.update({b["task"]: b for b in json.loads(path.read_text())})
        return [built[t["id"]] for t in tasks if t["id"] in built]

    def _context(self, task: dict, before: list, stories: list, found: dict) -> str:
        """Long material first and the task last; agent.ask appends the answer contract after it."""
        texts = criteria(stories)
        parts = [SKILL.read_text().strip()]
        conventions = self.wiki.convention_text()
        if conventions != "None.":
            parts += ["# Project conventions", conventions]
        for name in task["repos"]:
            parts.append(proof.skill_text(name, found[name]))
        parts.append(f"# Where you are\nThe terminal starts in the project folder, {self.project}. Each repo is a "
                     f"folder in it: " + ", ".join(task["repos"]) + ". Paths below are <repo>/<path>.")
        if before:
            parts.append("# Already built, in earlier tasks\n"
                         + "\n".join(f"- {t['id']}: {t['title']}" for t in before))
        given = [f["path"] for f in task["files"] if f["action"] != "create"] + task.get("read", [])
        if given:
            parts.append("# Files as they are now")
            for path in given:
                repo, _, rel = path.partition("/")
                text = (found[repo] / rel).read_text(errors="replace")
                parts.append(f"## {path}\n\n````\n{text.rstrip()}\n````")
        story_ids = list(dict.fromkeys(c.rpartition("#")[0] for c in task["covers"]))
        parts += ["# Story " + story_text(s, full=False) for s in stories if s["id"] in story_ids]
        parts.append("# Criteria this task makes true\n" + "\n".join(f"- {c}: {texts[c]}" for c in task["covers"]))
        parts.append(f"# Your task: {task['id']}\n{task['title']}\n\nFiles:\n"
                     + "\n".join(f"- {f['action']} {f['path']}" for f in task["files"]) + f"\n\n{task['change']}")
        return "\n\n".join(parts) + "\n"

    def show(self, rid: str) -> str:
        lines, path = [self.header(rid)], self.belt.run_dir(rid) / "built.json"
        for b in json.loads(path.read_text()) if path.exists() else []:
            commits = ", ".join(f"{r} {sha}" for r, sha in b["commits"].items()) or "no commit"
            lines.append(f"- {b['task']}: {b['outcome']} ({commits})")
        return "\n".join(lines)


def _problems(answer: dict, task: dict, used: dict, task_dir: Path) -> list[str]:
    """Everything about the builder's work that code can decide; the proof is replayed last, once the rest holds."""
    if "stop" in answer:
        return []
    out, allowed = [], {f["path"] for f in task["files"]}
    allowed |= {f"{r}/{proof.VERIFY}/FEATURES.md" for r in task["repos"]}   # the feature map follows the code
    touched = [f"{name}/{p}" for name, root in used.items() for p in changed(root)]
    out += [f"{p} changed, but repo {p.split('/')[0]} is not one of this task's repos; undo it"
            for p in touched if p.split("/")[0] not in task["repos"]]
    out += [f"{p} changed, but the task does not list it; undo it" for p in touched
            if p.split("/")[0] in task["repos"] and p not in allowed]
    kind = "change" if "change" in answer else "no_change"
    if kind == "change" and not touched:
        out.append("the answer says change, but no file changed")
    if kind == "no_change" and touched:
        out.append("the answer says no change, but files changed: " + ", ".join(touched))
    reported = [r["criterion"] for r in answer[kind]]
    out += [f"criterion {c} has no report" for c in task["covers"] if c not in reported]
    out += [f"{c} is not a criterion of this task" for c in reported if c not in task["covers"]]
    if out:
        return out
    out, record = proof.replay(answer[kind], {r: used[r] for r in task["repos"]})
    with (task_dir / "proof.jsonl").open("a") as f:   # every replay, rejected ones too
        f.write(json.dumps({"problems": out, "steps": record}) + "\n")
    return out


def _discard(task_dir: Path, used: dict) -> None:
    """Keep the unfinished work as evidence, then put every repo back to its last commit."""
    for name, root in used.items():
        diff = git(root, "diff", "HEAD")
        new = git(root, "ls-files", "--others", "--exclude-standard")
        if diff or new:
            (task_dir / f"discarded-{name}.diff").write_text(diff + ("\nNew files:\n" + new if new else ""))
        git(root, "checkout", "-q", "--", ".")
        git(root, "clean", "-q", "-fd")   # only untracked files Build made: the repo was clean when it started
