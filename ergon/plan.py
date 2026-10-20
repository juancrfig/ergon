"""The Plan node. Input: a goal plus the wiki. Output: approved user stories with acceptance criteria.

The planner works in rounds (ADR 0013). Each round returns either questions, which wait for the human's answers,
or the final stories, which wait for approval. Documents reach Plan only through Intake: the planner reads the wiki.

The human's answers are decisions about the project, so they go into the wiki (ADR 0028): with the stories, code
saves every answered round as a source and hands it to Intake. Approving the plan applies that wiki change too, so
the wiki never contradicts approved stories and later nodes never stop on the difference.
"""
import json
from pathlib import Path

from ergon import agent, profiles, schema
from ergon.intake import Intake
from ergon.node import Node
from ergon.wiki import today

SKILL = profiles.SKILLS / "planning.md"
MAX_ROUNDS = 5     # the last round must return stories


class Plan(Node):
    name, profile, types = "plan", "planner", ("plan",)

    def handle(self, rid: str, request: dict) -> str:
        """One round."""
        run_dir = self.belt.run_dir(rid)
        rounds = self._rounds(run_dir)
        number, final = len(rounds) + 1, len(rounds) + 1 >= MAX_ROUNDS
        agent.scope(run_dir, self.wiki.pages_dir, f"tool-calls-round-{number}.jsonl")
        prompt = self._context(request, rounds, number, final)
        known = set(self.wiki.pages())
        answer = agent.ask(self.profile, prompt, self.contracts / "round.json", run_dir, f"round-{number}",
                           lambda r: _round_problems(r, known, final))
        if "questions" in answer:
            self.belt.move(rid, "working", "waiting")
            return f"round {number}: {len(answer['questions'])} questions wait for your answers"
        (run_dir / "stories.json").write_text(json.dumps(answer, indent=2) + "\n")
        note = self._record_decisions(rid, request, rounds)
        self.belt.move(rid, "working", "review")
        return f"round {number}: {len(answer['stories'])} stories wait for approval" + note

    def _record_decisions(self, rid: str, request: dict, rounds: list) -> str:
        """Save the answered rounds as a source in the wiki's raw folder and ask Intake to ingest it."""
        if not rounds:
            return ""
        lines = [f"# Decisions made while planning", "",
                 f"The human answered the planner's questions on {today()} (plan {rid}), planning this goal:", "",
                 request["goal"], "",
                 "Each answer is the human's decision. It settles the open question or contradiction it answers and "
                 "replaces any older statement it disagrees with. \"Not specified\" means the human left it open.", ""]
        for i, (questions, answers) in enumerate(rounds, 1):
            given = {a["question"]: a for a in answers}
            for q in questions:
                a = given[q["id"]]
                how = " (left unanswered: the planner's recommendation)" if a.get("skipped") else ""
                lines += [f"## Round {i}, {q['id']}: {q['question']}", "", f"Answer{how}: {a['answer']}", ""]
        source = Path("wiki") / "raw" / f"plan-{rid}-decisions.md"
        (self.project / source).parent.mkdir(parents=True, exist_ok=True)
        (self.project / source).write_text("\n".join(lines))
        intake = self.hand_off("intake", {"type": "ingest", "from": "plan", "source": str(source),
                                          "note": "Decisions the human made while planning. They settle the questions "
                                                  "they answer: update the pages, do not record them as contradictions."})
        (self.belt.run_dir(rid) / "decisions.json").write_text(
            json.dumps({"source": str(source), "intake": intake}, indent=2) + "\n")
        return f"; the wiki update for its decisions, {intake}, waits in Intake's inbox"

    def _decisions(self, rid: str) -> tuple[Intake, str] | None:
        """Intake and the request that puts this plan's decisions in the wiki; None when no round was answered."""
        path = self.belt.run_dir(rid) / "decisions.json"
        return (Intake(self.project), json.loads(path.read_text())["intake"]) if path.exists() else None

    def _context(self, request, rounds, number, final) -> str:
        """Everything the planner is given. Pages it reads through the wiki tool, and the log records them."""
        parts = [SKILL.read_text().strip(), "# Wiki index", self.wiki.index_text(), "# Goal", request["goal"]]
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
        applied = ""
        decisions = self._decisions(rid)
        if decisions:   # the wiki takes the decisions first: no node after Plan may see stories the wiki contradicts
            intake, irid = decisions
            state = intake.belt.state_of(irid)
            if state == "rejected":
                reason = (intake.belt.run_dir(irid) / "rejected.txt").read_text().strip()
                raise ValueError(f"the wiki update for this plan's decisions ({irid}) was rejected: {reason}\n"
                                 "Reject the plan and plan again.")
            if state != "review":
                raise ValueError(f"the wiki update for this plan's decisions ({irid}) is not drafted yet: run Intake")
            applied = "; wiki " + intake.approve(irid)
        gone = sorted({s for story in stories for s in story["sources"]} - set(self.wiki.pages()))
        if gone:
            raise ValueError(f"wiki pages the stories cite no longer exist: {', '.join(gone)}; reject and plan again")
        self.belt.move(rid, "review", "done")
        split = self.hand_off("split", {"type": "split", "from": "plan", "plan": rid})   # ADR 0024
        return f"approved: {len(stories)} stories{applied}; split request {split} waits in Split's inbox"

    def reject(self, rid: str, reason: str) -> None:
        """A rejected plan takes its pending wiki update with it: the decisions were never approved."""
        super().reject(rid, reason)
        decisions = self._decisions(rid)
        if decisions and decisions[0].belt.state_of(decisions[1]) in ("inbox", "review"):
            decisions[0].reject(decisions[1], f"its plan {rid} was rejected")

    def approved(self, rid: str) -> list:
        """The stories of an approved plan: what Split and Build read of Plan."""
        if self.belt.state_of(rid) != "done":
            raise ValueError(f"plan {rid} is not approved")
        return json.loads((self.belt.run_dir(rid) / "stories.json").read_text())["stories"]

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
                lines += ["", story_text(s), "Sources: " + ", ".join(f"[[{p}]]" for p in s["sources"])]
        decisions = self._decisions(rid)
        if decisions:
            lines += ["", "Wiki update for the decisions, applied with the approval:", decisions[0].show(decisions[1])]
        return "\n".join(lines)


def criteria(stories: list) -> dict[str, str]:
    """Every done_when criterion by its id: the story id and its 1-based position. Approved stories never change, so
    the id is fixed; later nodes cite criteria by it."""
    return {f"{s['id']}#{n}": d for s in stories for n, d in enumerate(s["done_when"], 1)}


def story_text(story: dict, full: bool = True) -> str:
    """A story as the human and the agents read it; without full, only its title and its as/want/so-that line."""
    lines = [f"[{story['id']}] {story['title']}",
             f"As {story['as_a']}, I want {story['i_want']}, so that {story['so_that']}."]
    if full:
        lines += ["Done when:"] + [f"- {c}: {d}" for c, d in criteria([story]).items()]
        if story["out_of_scope"]:
            lines += ["Out of scope:"] + [f"- {o}" for o in story["out_of_scope"]]
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
