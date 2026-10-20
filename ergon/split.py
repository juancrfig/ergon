"""The Split node. Input: an approved plan's stories. Output: tasks a cheap builder carries out with no design
decision of its own (ADR 0024).

Split owns the how. The architect reads the project's repos and wiki, read-only, and returns either the tasks or a
stop: a product question the stories do not settle, which sends the plan back to Plan. Code checks the tasks
against the stories and the repos; no human approves them.
"""
import json
from pathlib import Path

from ergon import agent, gate
from ergon.node import Node
from ergon.wikitool import repo_files

PROFILE = "architect"
SKILL = gate.SKILLS / "splitting.md"
CONVENTION = "convention"   # the wiki tag of a project rule every design must follow
MAX_LISTING = 2000          # files listed per repo in the prompt


def repos(project: Path) -> dict[str, Path]:
    """The project's repos: every git clone directly inside the project folder (ADR 0025)."""
    return {p.name: p for p in sorted(Path(project).iterdir()) if p.is_dir() and (p / ".git").exists()}


def criteria(stories: list) -> list[str]:
    from ergon.plan import criterion_id
    return [criterion_id(s, n) for s in stories for n in range(1, len(s["done_when"]) + 1)]


class Split(Node):
    name, profile, types = "split", PROFILE, ("split",)

    def handle(self, rid: str, request: dict) -> str:
        stories = self._stories(request["plan"])
        found = repos(self.project)
        if not found:
            raise ValueError(f"the project has no repos: clone them into {self.project}")
        run_dir = self.belt.run_dir(rid)
        agent.scope(run_dir, self.wiki.pages_dir, repos=found)
        answer = agent.ask(PROFILE, self._context(stories, found), self.contracts / "tasks.json", run_dir, "tasks",
                           lambda a: _task_problems(a, stories, found))
        if "stop" in answer:
            stop = answer["stop"]
            self.belt.reject(rid, "working", f"stopped, the plan goes back to Plan: {stop['reason']}\n"
                                             f"Question: {stop['question']}")
            return f"stopped: {stop['question']}"
        self.belt.move(rid, "working", "done")
        from ergon.build import Build   # tasks go straight to Build: no human approves them (ADR 0024)
        build = Build(self.project).submit({"type": "build", "from": "split", "split": rid})
        return f"{len(answer['tasks'])} tasks for plan {request['plan']}; build request {build} waits in Build's inbox"

    def _stories(self, plan: str) -> list:
        path = self.project / ".ergon" / "plan" / "done" / f"{plan}.json"
        if not path.exists():
            raise ValueError(f"plan {plan} is not approved")
        return json.loads((self.project / ".ergon" / "plan" / "runs" / plan / "stories.json").read_text())["stories"]

    def _context(self, stories: list, found: dict) -> str:
        """Everything the architect is given. Files and pages it reads through the tool, and the log records them."""
        from ergon.plan import criterion_id
        pages = self.wiki.pages()
        rules = [p for p in pages.values() if CONVENTION in (p.meta.get("tags") or [])]
        parts = [SKILL.read_text().strip(), "# Project conventions",
                 "\n\n".join(f"## [[{p.slug}]]\n\n{p.text.strip()}" for p in rules) or "None.",
                 "# Wiki index", self.wiki.index_text(pages),
                 "Find pages with search_wiki and read them with read_pages. Find code with search_code and read it "
                 "with read_files; ask for every file you need in one call.", "# Stories, in build order"]
        for s in stories:
            lines = [f"## [{s['id']}] {s['title']}", f"As {s['as_a']}, I want {s['i_want']}, so that {s['so_that']}.",
                     "Done when:"] + [f"- {criterion_id(s, n)}: {d}" for n, d in enumerate(s["done_when"], 1)]
            if s["out_of_scope"]:
                lines += ["Out of scope:"] + [f"- {o}" for o in s["out_of_scope"]]
            parts.append("\n".join(lines))
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
                lines.append("  " + t["change"].replace("\n", "\n  "))
        return "\n".join(lines)


def _task_problems(answer: dict, stories: list, found: dict) -> list[str]:
    """Everything about the tasks that code can decide."""
    if "stop" in answer:
        return []
    out, tasks = [], answer["tasks"]
    ids = [t["id"] for t in tasks]
    out += [f"task id {i!r} is repeated" for i in sorted({i for i in ids if ids.count(i) > 1})]
    known = criteria(stories)
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
                    out.append(f"{t['id']}: {f['path']} does not exist; only a create may name a new file")
            elif ".." in rel.split("/"):
                out.append(f"{t['id']}: {f['path']} leaves its repo")
        out += [f"{t['id']}: repo {r!r} has no file in this task" for r in t["repos"]
                if r in found and not any(f["path"].startswith(r + "/") for f in t["files"])]
    return out
