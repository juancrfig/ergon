"""The Plan node. Input: a goal plus the wiki. Output: approved user stories with acceptance criteria.

The planner works in rounds (ADR 0013). Each round returns either questions, which wait for the human's answers,
or the final stories, which wait for approval. Documents reach Plan only through Intake: the planner reads the wiki.
"""
import json
from pathlib import Path

from ergon import agent, gate, schema
from ergon.intake import CONTRACTS as INTAKE_CONTRACTS, FULL_WIKI_CHARS
from ergon.node import Node

PROFILE = "planner"
SKILL = gate.REPO / "profiles" / PROFILE / "skills" / "planning.md"
MAX_ROUNDS = 5     # the last round must return stories


class Plan(Node):
    name, profile, types = "plan", PROFILE, ("plan",)

    def run(self, log=print) -> None:
        gate.require(PROFILE)
        for rid in self.belt.ids("inbox"):
            self.belt.move(rid, "inbox", "working")
            request = self.belt.read(rid)
            problems = self.request_problems(request)
            if problems:
                self.finish_rejected(rid, request, "working", "malformed request:\n" + "\n".join(problems))
                log(f"{rid}: rejected (malformed)")
                continue
            try:
                outcome = self._round(rid, request)
            except (agent.AgentError, OSError, ValueError) as exc:
                self.finish_rejected(rid, request, "working", f"failed: {exc}")
                outcome = f"rejected: {exc}"
            log(f"{rid}: {outcome}")

    def _round(self, rid: str, request: dict) -> str:
        run_dir = self.belt.run_dir(rid)
        rounds = self._rounds(run_dir)
        number, final = len(rounds) + 1, len(rounds) + 1 >= MAX_ROUNDS
        pages = self._pages(rid, request, run_dir)
        prompt = self._context(request, pages, rounds, number, final)
        known = set(self.wiki.pages())
        answer = agent.ask(PROFILE, prompt, self.contracts / "round.json", run_dir, f"round-{number}",
                           lambda r: _round_problems(r, known, final))
        if "questions" in answer:
            self.belt.move(rid, "working", "waiting")
            return f"round {number}: {len(answer['questions'])} questions wait for your answers"
        (run_dir / "stories.json").write_text(json.dumps(answer, indent=2) + "\n")
        self.belt.move(rid, "working", "review")
        return f"round {number}: {len(answer['stories'])} stories wait for approval"

    def _pages(self, rid, request, run_dir) -> dict:
        pages = self.wiki.pages()
        if sum(len(p.text) for p in pages.values()) <= FULL_WIKI_CHARS:
            return pages
        chosen = run_dir / "page-selection.json"
        if not chosen.exists():  # chosen once per plan, in its first round
            prompt = (SKILL.read_text() + "\n\n# Wiki index\n\n" + self.wiki.index_text() + "\n# Goal\n\n"
                      + request["goal"] + "\n\n# Your job now\nThe wiki is too large to show whole. Pick the pages "
                      "(at most 15) you must read to plan this goal.\n")
            agent.ask(PROFILE, prompt, INTAKE_CONTRACTS / "page-selection.json", run_dir, "page-selection",
                      lambda r: [f"unknown page {s!r}" for s in r["pages"] if s not in pages])
        return {s: pages[s] for s in json.loads(chosen.read_text())["pages"] if s in pages}

    def _context(self, request, pages, rounds, number, final) -> str:
        """The planner's entire context. Nothing else reaches the model."""
        parts = [SKILL.read_text().strip(), "# Wiki index", self.wiki.index_text()]
        for slug, page in pages.items():
            parts += [f"# Page [[{slug}]]", page.text]
        parts += ["# Goal", request["goal"]]
        for i, (questions, answers) in enumerate(rounds, 1):
            parts.append(f"# Round {i}: your questions and the human's answers")
            given = {a["question"]: a["answer"] for a in answers}
            parts += [f"- {q['question']}\n  Answer: {given[q['id']]}" for q in questions]
        parts += ["# This round", f"Round {number} of at most {MAX_ROUNDS}. "
                  + ("This is the last round: return stories." if final else
                     "Return questions if a decision that changes the stories is still open; otherwise return stories.")]
        return "\n\n".join(parts) + "\n"

    def _rounds(self, run_dir: Path) -> list:
        out, number = [], 1
        while (run_dir / f"answers-{number}.json").exists():
            questions = json.loads((run_dir / f"round-{number}.json").read_text())["questions"]
            out.append((questions, json.loads((run_dir / f"answers-{number}.json").read_text())["answers"]))
            number += 1
        return out

    # --- the human ----------------------------------------------------------------------------------------------

    def answer(self, rid: str, doc: dict) -> str:
        """Record the human's answers to the waiting round and send the plan back to the inbox."""
        if self.belt.state_of(rid) != "waiting":
            raise ValueError(f"{rid} has no questions waiting for answers")
        problems = schema.errors(doc, schema.load(self.contracts / "answers.json"))
        if problems:
            raise ValueError("answers rejected:\n" + "\n".join(problems))
        run_dir = self.belt.run_dir(rid)
        number = len(self._rounds(run_dir)) + 1
        questions = {q["id"]: q for q in json.loads((run_dir / f"round-{number}.json").read_text())["questions"]}
        given = {a["question"]: a["answer"] for a in doc["answers"]}
        unknown = sorted(set(given) - set(questions))
        if unknown:
            raise ValueError(f"no such questions in round {number}: {', '.join(unknown)}")
        answers = []
        for qid, q in questions.items():
            text = given.get(qid, q["recommended"])
            # Recorded for metrics: how often the human takes the planner's recommendation.
            answers.append({"question": qid, "answer": text, "skipped": qid not in given,
                            "took_recommendation": text == q["recommended"]})
        (run_dir / f"answers-{number}.json").write_text(json.dumps({"answers": answers}, indent=2) + "\n")
        self.belt.move(rid, "waiting", "inbox")
        return f"round {number} answered; the plan is back in the inbox"

    def approve(self, rid: str) -> str:
        if self.belt.state_of(rid) != "review":
            raise ValueError(f"{rid} has no stories waiting for approval")
        run_dir = self.belt.run_dir(rid)
        stories = json.loads((run_dir / "stories.json").read_text())["stories"]
        gone = sorted({s for story in stories for s in story["sources"]} - set(self.wiki.pages()))
        if gone:
            raise ValueError(f"wiki pages the stories cite no longer exist: {', '.join(gone)}; reject and plan again")
        self.belt.move(rid, "review", "done")
        path = str((run_dir / "stories.json").relative_to(self.project))
        self.reply(self.belt.read(rid), rid, "done", f"{len(stories)} stories approved", stories=path)
        return f"approved: {len(stories)} stories in {path}"

    def show(self, rid: str) -> str:
        run_dir, lines = self.belt.run_dir(rid), [self.header(rid)]
        state = self.belt.state_of(rid)
        if state == "waiting":
            number = len(self._rounds(run_dir)) + 1
            lines.append(f"Round {number} questions (answer with a JSON file; a question left out takes the ★ option):")
            for q in json.loads((run_dir / f"round-{number}.json").read_text())["questions"]:
                lines.append(f"  {q['id']}. {q['question']}\n     why: {q['why']}")
                lines += [f"     {'★' if o == q['recommended'] else '-'} {o}" for o in q["options"]]
        if (run_dir / "stories.json").exists():
            for s in json.loads((run_dir / "stories.json").read_text())["stories"]:
                lines.append(f"\n[{s['id']}] {s['title']}\n  As {s['as_a']}, I want {s['i_want']}, so that {s['so_that']}.")
                lines += ["  Done when:"] + [f"    - {d}" for d in s["done_when"]]
                if s["out_of_scope"]:
                    lines += ["  Out of scope:"] + [f"    - {o}" for o in s["out_of_scope"]]
                lines.append("  Sources: " + ", ".join(f"[[{p}]]" for p in s["sources"]))
        return "\n".join(lines)


def _round_problems(answer: dict, known: set, final: bool) -> list[str]:
    """Everything about a round that code can decide."""
    out = []
    if "questions" in answer:
        if final:
            out.append("this is the last round: return stories, not questions")
        ids = [q["id"] for q in answer["questions"]]
        out += [f"question id {i!r} is repeated" for i in sorted({i for i in ids if ids.count(i) > 1})]
        out += [f"{q['id']}: recommended must be one of its options, copied exactly"
                for q in answer["questions"] if q["recommended"] not in q["options"]]
        return out
    ids = [s["id"] for s in answer["stories"]]
    out += [f"story id {i!r} is repeated" for i in sorted({i for i in ids if ids.count(i) > 1})]
    out += [f"{s['id']}: source [[{p}]] is not a wiki page" for s in answer["stories"] for p in s["sources"] if p not in known]
    return out
