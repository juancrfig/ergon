"""The Build node. Input: the tasks Split made for one plan. Output: one commit per task on the plan's branch, in
every repo the task changes (ADR 0023, 0024).

The builder is a cheap model with the terminal and file tools. It carries out one task at a time, in Split's
order, and makes no design decision: a task that leaves one open is a stop, the architect's failure. Code checks
what changed against the task, then commits; the builder never runs git. Gate and Inspect are not built yet.
"""
import json
import subprocess
from pathlib import Path

from ergon import agent, gate
from ergon.node import Node
from ergon.split import CONVENTION, Split, repos

PROFILE = "builder"
SKILL = gate.SKILLS / "building.md"
MAX_TURNS = 60   # ADR 0023
AUTHOR = ["-c", "user.name=Ergon", "-c", "user.email=ergon@localhost"]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} in {root.name} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def changed(root: Path) -> list[str]:
    """The paths git sees as changed, added or deleted, untracked files included and ignored ones not."""
    out = []
    for line in git(root, "status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        out.append(path)
    return sorted(out)


class Build(Node):
    name, profile, types = "build", PROFILE, ("build",)

    def handle(self, rid: str, request: dict) -> str:
        split_dir = Split(self.project).belt.run_dir(request["split"])
        plan = Split(self.project).belt.read(request["split"])["plan"]
        tasks = json.loads((split_dir / "tasks.json").read_text())["tasks"]
        stories = json.loads((self.project / ".ergon" / "plan" / "runs" / plan / "stories.json").read_text())["stories"]
        found = repos(self.project)
        used = {r: found[r] for t in tasks for r in t["repos"] if r in found}
        branch = f"plan/{plan}"
        for root in used.values():       # code owns the branches (ADR 0023)
            if changed(root):
                raise ValueError(f"repo {root.name} has uncommitted changes; commit or stash them first")
        for root in used.values():
            exists = git(root, "branch", "--list", branch).strip()
            git(root, "checkout", "-q", *([branch] if exists else ["-b", branch]))
        run_dir = self.belt.run_dir(rid)
        built_path = run_dir / "built.json"
        built = json.loads(built_path.read_text()) if built_path.exists() else []
        done = {b["task"] for b in built}
        for n, task in enumerate(tasks, 1):
            if task["id"] in done:
                continue
            task_dir = run_dir / f"{n:02d}-{task['id']}"
            agent.scope(task_dir, self.wiki.pages_dir)
            try:
                answer = agent.ask(PROFILE, self._context(task, tasks[:n - 1], stories, used), self.contracts / "result.json",
                                   task_dir, "result", lambda a: _problems(a, task, used), tools=("terminal", "file"),
                                   turns=MAX_TURNS, cwd=self.project)
            except agent.AgentError:
                _discard(task_dir, used)
                raise
            if "stop" in answer:
                _discard(task_dir, used)
                stop = answer["stop"]
                self.belt.reject(rid, "working", f"stopped at task {task['id']}; it goes back to Split: "
                                                 f"{stop['reason']}\nQuestion: {stop['question']}")
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

    def _context(self, task: dict, before: list, stories: list, used: dict) -> str:
        from ergon.plan import criterion_id
        texts = {criterion_id(s, n): (s, d) for s in stories for n, d in enumerate(s["done_when"], 1)}
        rules = [p for p in self.wiki.pages().values() if CONVENTION in (p.meta.get("tags") or [])]
        parts = [SKILL.read_text().strip(), "# Project conventions",
                 "\n\n".join(f"## [[{p.slug}]]\n\n{p.text.strip()}" for p in rules) or "None."]
        for name in task["repos"]:
            guide = used[name] / "AGENTS.md"
            if guide.exists():
                parts.append(f"# {name}/AGENTS.md\n\n{guide.read_text().strip()}")
        parts.append(f"# Where you are\nThe terminal starts in the project folder, {self.project}. Each repo is a "
                     f"folder in it: " + ", ".join(task["repos"]) + ". Paths below are <repo>/<path>.")
        if before:
            parts.append("# Already built, in earlier tasks\n" + "\n".join(f"- {t['id']}: {t['title']}" for t in before))
        story_ids = list(dict.fromkeys(texts[c][0]["id"] for c in task["covers"]))
        for sid in story_ids:
            s = next(s for s in stories if s["id"] == sid)
            parts.append(f"# Story {s['id']}: {s['title']}\nAs {s['as_a']}, I want {s['i_want']}, so that "
                         f"{s['so_that']}.")
        parts.append("# Criteria this task makes true\n" + "\n".join(f"- {c}: {texts[c][1]}" for c in task["covers"]))
        parts.append(f"# Your task: {task['id']}\n{task['title']}\n\nFiles:\n"
                     + "\n".join(f"- {f['action']} {f['path']}" for f in task["files"]) + f"\n\n{task['change']}")
        return "\n\n".join(parts) + "\n"

    def show(self, rid: str) -> str:
        lines, path = [self.header(rid)], self.belt.run_dir(rid) / "built.json"
        for b in json.loads(path.read_text()) if path.exists() else []:
            commits = ", ".join(f"{r} {sha}" for r, sha in b["commits"].items()) or "no commit"
            lines.append(f"- {b['task']}: {b['outcome']} ({commits})")
        return "\n".join(lines)


def _problems(answer: dict, task: dict, used: dict) -> list[str]:
    """Everything about the builder's work that code can decide."""
    if "stop" in answer:
        return []
    out, allowed = [], {f["path"] for f in task["files"]}
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
