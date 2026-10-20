"""A project wiki, and every wiki operation with one right answer.

Layout: wiki/pages/<slug>.md, wiki/index.md (written only by code), wiki/raw/ (sources),
wiki/conventions.json (optional: tags, max_page_lines, stale_days, notes).

A page is front matter (title, tags, updated) plus a Markdown body. Pages link each other as [[slug]].
"""
import datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path

FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
LINK = re.compile(r"\[\[([a-z0-9]+(?:-[a-z0-9]+)*)\]\]")
PATHLIKE = re.compile(r"^(/|~|\.{1,2}/|raw/|wiki/)|^[^:]*\.(md|txt|pdf|html?|json|docx?)$", re.I)
CONVENTION = "convention"   # the tag of a page holding a project rule every design and change must follow
DEFAULTS = {"tags": [], "max_page_lines": 200, "stale_days": 180, "notes": ""}


def today() -> str:
    return datetime.date.today().isoformat()


class Page:
    def __init__(self, slug: str, text: str):
        self.slug, self.text = slug, text
        match = FRONT.match(text)
        self.meta, self.body = ({}, text) if not match else (_parse_front(match.group(1)), match.group(2))

    @property
    def links(self) -> set[str]:
        return set(LINK.findall(self.body))


def _parse_front(block: str) -> dict:
    meta = {}
    for line in block.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        meta[key.strip()] = value
    return meta


def render(title: str, tags: list[str], body: str, updated: str) -> str:
    return f"---\ntitle: {title}\ntags: [{', '.join(tags)}]\nupdated: {updated}\n---\n{body.strip()}\n"


class Wiki:
    def __init__(self, project: Path):
        self.project = Path(project).resolve()
        self.dir = self.project / "wiki"
        self.pages_dir = self.dir / "pages"
        conv = self.dir / "conventions.json"
        self.conventions = {**DEFAULTS, **(json.loads(conv.read_text()) if conv.exists() else {})}

    def pages(self) -> dict[str, Page]:
        if not self.pages_dir.exists():
            return {}
        return {p.stem: Page(p.stem, p.read_text()) for p in sorted(self.pages_dir.glob("*.md"))}

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for slug, page in self.pages().items():
            digest.update(slug.encode() + b"\0" + page.text.encode() + b"\0")
        return digest.hexdigest()

    def index_text(self, pages: dict[str, Page] | None = None) -> str:
        pages = self.pages() if pages is None else pages
        lines = ["# Index", "", "Written by ergon. Do not edit.", ""]
        for slug, page in pages.items():
            tags = page.meta.get("tags") or []
            lines.append(f"- [[{slug}]] {page.meta.get('title', slug)}" + (f" ({', '.join(tags)})" if tags else ""))
        return "\n".join(lines) + "\n"

    def convention_text(self, pages: dict[str, Page] | None = None) -> str:
        """Every page tagged convention, in full: the project rules Split and Build are given."""
        pages = self.pages() if pages is None else pages
        rules = [p for p in pages.values() if CONVENTION in (p.meta.get("tags") or [])]
        return "\n\n".join(f"## [[{p.slug}]]\n\n{p.text.strip()}" for p in rules) or "None."

    # --- checks -----------------------------------------------------------------------------------------------

    def page_problems(self, page: Page, known: set[str]) -> list[str]:
        out = []
        for key in ("title", "tags", "updated"):
            if key not in page.meta:
                out.append(f"missing front matter field {key!r}")
        allowed = self.conventions["tags"]
        if allowed:
            out += [f"tag {t!r} is not in conventions.json" for t in page.meta.get("tags") or [] if t not in allowed]
        lines = page.text.count("\n") + 1
        if lines > self.conventions["max_page_lines"]:
            out.append(f"{lines} lines; the limit is {self.conventions['max_page_lines']}")
        out += [f"broken link [[{link}]]" for link in sorted(page.links - known)]
        return out

    def mechanical_findings(self) -> list[dict]:
        pages = self.pages()
        known = set(pages)
        findings = []
        inbound = {slug: 0 for slug in pages}
        for page in pages.values():
            for link in page.links & known:
                if link != page.slug:
                    inbound[link] += 1
        cutoff = (datetime.date.today() - datetime.timedelta(days=self.conventions["stale_days"])).isoformat()
        for slug, page in pages.items():
            findings += [{"page": slug, "kind": "format", "text": p} for p in self.page_problems(page, known)]
            if inbound[slug] == 0 and len(pages) > 1:
                findings.append({"page": slug, "kind": "orphan", "text": "no other page links here"})
            updated = page.meta.get("updated", "")
            if isinstance(updated, str) and updated and updated < cutoff:
                findings.append({"page": slug, "kind": "stale", "text": f"updated {updated}, before {cutoff}"})
        index = self.dir / "index.md"
        if pages and (not index.exists() or index.read_text() != self.index_text(pages)):
            findings.append({"page": "index", "kind": "index", "text": "index.md does not match the pages"})
        return findings

    def proposal_problems(self, proposal: dict) -> list[str]:
        """Everything about a proposal that code can decide."""
        pages = self.pages()
        out, after = [], dict(pages)
        for i, edit in enumerate(proposal["edits"]):
            where, slug = f"edits[{i}] ({edit['page']})", edit["page"]
            if edit["op"] == "create" and slug in after:
                out.append(f"{where}: create, but the page exists; use replace")
            if edit["op"] in ("replace", "delete") and slug not in after:
                out.append(f"{where}: {edit['op']}, but the page does not exist")
            if edit["op"] == "delete":
                after.pop(slug, None)
                continue
            missing = [k for k in ("title", "tags", "body") if k not in edit]
            if missing:
                out.append(f"{where}: {edit['op']} needs {missing}")
                continue
            if FRONT.match(edit["body"]):
                out.append(f"{where}: body must not contain front matter; code writes it")
            after[slug] = Page(slug, render(edit["title"], edit["tags"], edit["body"], today()))
        for i, edit in enumerate(proposal["edits"]):
            if edit["op"] != "delete" and edit["page"] in after:
                out += [f"edits[{i}] ({edit['page']}): {p}" for p in self.page_problems(after[edit["page"]], set(after))]
        for slug in set(pages) - set(after):
            out += [f"deleting {slug!r} breaks the link from {s!r}" for s, p in after.items() if slug in p.links]
        for i, item in enumerate(proposal["items"]):
            if PATHLIKE.search(item["citation"].strip()):
                out.append(f"items[{i}]: citation {item['citation']!r} is a file path; cite who, what and when")
            if item.get("page") and item["page"] not in after:
                out.append(f"items[{i}]: page {item['page']!r} does not exist after the edits")
        return out

    # --- writes (only after human approval) ------------------------------------------------------------------

    def apply(self, proposal: dict, rid: str) -> str | None:
        """Write the edits and the index, then commit the wiki in the project's repo; return the commit. The commits
        are the wiki's history, so a project folder that is not a git repo is refused before anything is written."""
        if subprocess.run(["git", "-C", str(self.project), "rev-parse", "--git-dir"], capture_output=True).returncode:
            raise ValueError(f"{self.project} is not a git repo; the wiki's history is its commits (git init it)")
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        for edit in proposal["edits"]:
            path = self.pages_dir / f"{edit['page']}.md"
            if edit["op"] == "delete":
                path.unlink()
            else:
                path.write_text(render(edit["title"], edit["tags"], edit["body"], today()))
        (self.dir / "index.md").write_text(self.index_text())
        return self._commit(f"wiki: {proposal['summary']}\n\nergon intake ingest {rid}")

    def _commit(self, message: str) -> str | None:
        git = ["git", "-C", str(self.project)]
        subprocess.run(git + ["add", "--", "wiki"], check=True, capture_output=True)
        if subprocess.run(git + ["diff", "--cached", "--quiet", "--", "wiki"]).returncode == 0:
            return None
        subprocess.run(git + ["commit", "-q", "-m", message, "--", "wiki"], check=True, capture_output=True)
        return subprocess.run(git + ["rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
