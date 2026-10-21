"""The Split node. Input: an approved plan's stories. Output: tasks a cheap builder carries out with no design
decision of its own (ADR 0024).

Split owns the how. The architect reads the project's repos and wiki, read-only, and returns either the tasks or a
stop: a product question the stories do not settle. A stop is a rejection; the human submits a new plan by hand.
Code checks the tasks against the stories and the repos; no human approves them.
"""
import json

from ergon import agent, profiles
from ergon.node import Node, repos
from ergon.plan import Plan, criteria, story_text
from ergon.wikitool import repo_files

SKILL = profiles.SKILLS / "splitting.md"
MAX_LISTING = 2000          # files listed per repo in the prompt


class Split(Node):
    name, profile, types = "split", "architect", ("split",)

    def handle(self, rid: str, request: dict) -> str:
        stories = Plan(self.project).approved(request["plan"])
        found = repos(self.project)
        if not found:
            raise ValueError(f"the project has no repos: clone them into {self.project}")
        run_dir = self.belt.run_dir(rid)
        agent.scope(run_dir, self.wiki.pages_dir, repos=found)
        answer = agent.ask(self.profile, self._context(stories, found), self.contracts / "tasks.json", run_dir, "tasks",
                           lambda a: _task_problems(a, stories, found))
        if "stop" in answer:
            stop = answer["stop"]
            self.belt.reject(rid, "working", f"stopped: {stop['reason']}\nQuestion: {stop['question']}")
            return f"stopped: {stop['question']}"
        self.belt.move(rid, "working", "done")
        build = self.hand_off("build", {"type": "build", "from": "split", "split": rid})   # no approval (ADR 0024)
        return f"{len(answer['tasks'])} tasks for plan {request['plan']}; build request {build} waits in Build's inbox"

    def tasks(self, rid: str) -> tuple[str, list]:
        """The plan and the tasks of a finished split: what Build reads of Split."""
        if self.belt.state_of(rid) != "done":
            raise ValueError(f"split {rid} is not done")
        return self.belt.read(rid)["plan"], json.loads((self.belt.run_dir(rid) / "tasks.json").read_text())["tasks"]

    def _context(self, stories: list, found: dict) -> str:
        """Everything the architect is given. Files and pages it reads through the tool, and the log records them."""
        pages = self.wiki.pages()
        parts = [SKILL.read_text().strip(), "# Project conventions", self.wiki.convention_text(pages),
                 "# Wiki index", self.wiki.index_text(pages), "# Stories, in build order"]
        parts += ["## " + story_text(s) for s in stories]
        parts.append("# Repos")
        for name, root in found.items():
            files = repo_files(root)
            cut = f"\n({len(files) - MAX_LISTING} more files not listed)" if len(files) > MAX_LISTING else ""
            parts.append(f"## {name}\n\n" + "\n".join(f"{name}/{f}" for f in files[:MAX_LISTING]) + cut)
        return "\n\n".join(parts) + "\n"

    def show(self, rid: str) -> str:
        lines, path = [self.header(rid)], self.belt.run_dir(rid) / "tasks.json"
        if path.exists() and "tasks" in (doc := json.loads(path.read_text())):
            for n, t in enumerate(doc["tasks"], 1):
                lines.append(f"\n{n}. [{t['id']}] {t['title']}\n  Covers: {', '.join(t['covers'])}")
                lines += [f"  {f['action']:6} {f['path']}" for f in t["files"]]
                lines += [f"  read   {p}" for p in t.get("read", [])]
                lines.append("  " + t["change"].replace("\n", "\n  "))
        return "\n".join(lines)


def _task_problems(answer: dict, stories: list, found: dict) -> list[str]:
    """Everything about the tasks that code can decide."""
    if "stop" in answer:
        return []
    out, tasks = [], answer["tasks"]
    ids = [t["id"] for t in tasks]
    out += [f"task id {i!r} is repeated" for i in sorted({i for i in ids if ids.count(i) > 1})]
    known = list(criteria(stories))
    covered = {c for t in tasks for c in t["covers"]}
    out += [f"{t['id']}: covers {c!r}, which is not a criterion of the stories"
            for t in tasks for c in t["covers"] if c not in known]
    out += [f"criterion {c} is covered by no task" for c in known if c not in covered]
    listed = {name: set(repo_files(root)) for name, root in found.items()}
    for t in tasks:
        out += [f"{t['id']}: repo {r!r} is not one of the project's repos ({', '.join(found)})"
                for r in t["repos"] if r not in found]
        for f in t["files"]:
            repo, _, rel = f["path"].partition("/")
            if repo not in t["repos"]:
                out.append(f"{t['id']}: {f['path']} is not in one of the task's repos")
            elif repo in listed and ".." not in rel.split("/"):
                exists = rel in listed[repo]
                if f["action"] == "create" and exists:
                    out.append(f"{t['id']}: {f['path']} already exists; its action is change, not create")
                if f["action"] != "create" and not exists:
                    out.append(f"{t['id']}: {f['path']} does not exist and no earlier task creates it; "
                               "only a create may name a new file")
            elif ".." in rel.split("/"):
                out.append(f"{t['id']}: {f['path']} leaves its repo")
        named = {f["path"] for f in t["files"]}
        for path in t["read"]:
            repo, _, rel = path.partition("/")
            if repo not in found:
                out.append(f"{t['id']}: read {path} is not in one of the project's repos ({', '.join(found)})")
            elif ".." in rel.split("/") or rel not in listed[repo]:
                out.append(f"{t['id']}: read {path} does not exist and no earlier task creates it")
            elif path in named:
                out.append(f"{t['id']}: read {path} is already in files; the builder gets its text either way")
        for f in t["files"]:   # tasks run in list order: a later task sees what the earlier ones created or deleted
            repo, _, rel = f["path"].partition("/")
            if repo in listed:
                (listed[repo].add if f["action"] == "create" else listed[repo].discard if f["action"] == "delete"
                 else (lambda _: None))(rel)
        out += [f"{t['id']}: repo {r!r} has no file in this task" for r in t["repos"]
                if r in found and not any(f["path"].startswith(r + "/") for f in t["files"])]
    return out
