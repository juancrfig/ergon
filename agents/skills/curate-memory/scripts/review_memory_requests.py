#!/usr/bin/env python3
"""Review Hermes pending memory and skill writes without creating another queue.

The script is deliberately an adapter around Hermes's native pending-write store.
It inventories the main agent's profile, asks TypeSafe Jev only about the literal
staged payload of the one request being shown, renders a single ASCII panel, and delegates a human
approve/reject decision back to Hermes's native applier.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

# The main agent runs in Hermes' default profile. Task agents are its subagents and write no memory of their own.
PROFILES = ("default",)
SUBSYSTEMS = ("memory", "skills")
GRADUATION_STREAK = 20
DECISION_OPTIONS = ("approve", "reject", "trim")


class ReviewError(RuntimeError):
    pass


class StaleRequestError(ReviewError):
    pass


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    version: int
    question: str
    context: dict[str, Any]
    definition: dict[str, Any]
    exclusions: list[str]
    examples: list[str]


@dataclass(frozen=True)
class Catalog:
    catalog_version: int
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True)
class PendingRequest:
    profile: str
    home: Path
    subsystem: str
    pending_id: str
    record: dict[str, Any]
    record_sha256: str
    payload_sha256: str

    @property
    def payload(self) -> dict[str, Any]:
        payload = self.record.get("payload")
        if not isinstance(payload, dict):
            raise ReviewError(f"Pending {self.profile}/{self.subsystem}/{self.pending_id} has no object payload.")
        return payload


@dataclass(frozen=True)
class Inventory:
    requests: tuple[PendingRequest, ...]
    counts: dict[str, int]
    unreadable: tuple[str, ...]


@dataclass(frozen=True)
class Evaluation:
    status: str
    model: str
    results: dict[str, float]
    error: str = ""
    retention_categories: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _profile_homes(root: Path) -> Iterable[tuple[str, Path]]:
    yield "default", root
    for profile in PROFILES[1:]:
        home = root / "profiles" / profile
        if home.exists():
            yield profile, home


def _parse_pending_file(path: Path, profile: str, subsystem: str, home: Path) -> PendingRequest:
    raw = path.read_text(encoding="utf-8")
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ReviewError("record is not an object")
    pending_id = path.stem
    if not isinstance(record.get("payload"), dict):
        raise ReviewError("record payload is not an object")
    return PendingRequest(
        profile=profile,
        home=home,
        subsystem=subsystem,
        pending_id=pending_id,
        record=record,
        record_sha256=sha256_text(raw),
        payload_sha256=sha256_text(canonical_json(record["payload"])),
    )


def inventory_pending(root: Path) -> Inventory:
    requests: list[PendingRequest] = []
    unreadable: list[str] = []
    counts = {"memory": 0, "skills": 0, "unreadable": 0}
    for profile, home in _profile_homes(root):
        for subsystem in SUBSYSTEMS:
            directory = home / "pending" / subsystem
            for path in sorted(directory.glob("*.json")) if directory.exists() else ():
                try:
                    request = _parse_pending_file(path, profile, subsystem, home)
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ReviewError) as exc:
                    counts["unreadable"] += 1
                    unreadable.append(f"{profile}/{subsystem}/{path.name}: {exc}")
                    continue
                requests.append(request)
                counts[subsystem] += 1
    requests.sort(key=lambda item: (
        float(item.record.get("created_at", 0) or 0), item.profile, item.subsystem, item.pending_id))
    return Inventory(tuple(requests), counts, tuple(unreadable))


def load_catalog(catalog_path: Path) -> Catalog:
    try:
        document = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewError(f"Cannot read criteria catalog {catalog_path}: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("criteria", []), list):
        raise ReviewError("Catalog must be a JSON object with a criteria list.")
    criteria: list[Criterion] = []
    seen: set[str] = set()
    for row in document["criteria"]:
        if not isinstance(row, dict):
            raise ReviewError("Every catalog criterion must be an object.")
        ident, version, question = row.get("id"), row.get("version"), row.get("question")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ReviewError("Criterion ids must be unique, non-empty strings.")
        if not isinstance(version, int) or version < 1 or not isinstance(question, str) or not question:
            raise ReviewError(f"Criterion {ident!r} requires positive version and question.")
        context, definition = row.get("context"), row.get("definition")
        if not isinstance(context, dict):
            raise ReviewError(f"Criterion {ident!r} requires an object context.")
        if (not isinstance(definition, dict)
                or not isinstance(definition.get("yes"), str) or not definition["yes"].strip()
                or not isinstance(definition.get("no"), str) or not definition["no"].strip()):
            raise ReviewError(f"Criterion {ident!r} requires non-empty definition.yes and definition.no strings.")
        exclusions, examples = row.get("exclusions", []), row.get("examples", [])
        if not isinstance(exclusions, list) or not all(isinstance(item, str) for item in exclusions):
            raise ReviewError(f"Criterion {ident!r} exclusions must be a list of strings.")
        if not isinstance(examples, list) or not all(isinstance(item, str) for item in examples):
            raise ReviewError(f"Criterion {ident!r} examples must be a list of strings.")
        seen.add(ident)
        criteria.append(Criterion(ident, version, question, context, definition, exclusions, examples))
    catalog_version = document.get("catalog_version", 1)
    if not isinstance(catalog_version, int) or catalog_version < 1:
        raise ReviewError("catalog_version must be a positive integer.")
    return Catalog(catalog_version, tuple(criteria))


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("possible API key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
    ("secret assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}")),
)


def detect_possible_secrets(payload: dict[str, Any]) -> tuple[str, ...]:
    text = canonical_json(payload)
    return tuple(label for label, pattern in _SECRET_PATTERNS if pattern.search(text))


def _criterion_instructions(criterion: Criterion) -> dict[str, Any]:
    return {
        "question": criterion.question,
        "context": criterion.context,
        "yes_definition": criterion.definition.get("yes", "Yes means the stated problem exists."),
        "no_definition": criterion.definition.get("no", "No means the stated problem does not exist."),
        "exclusions": criterion.exclusions,
        "examples": criterion.examples,
        "direction": "A higher probability means the stated problem is more likely.",
    }


def evaluate_with_jev(request: PendingRequest, criteria: tuple[Criterion, ...], model: str | None = None) -> Evaluation:
    if not os.environ.get("SYSTEM_ONE_API"):
        return Evaluation("EVALUATION UNAVAILABLE", "", {}, "SYSTEM_ONE_API is not configured")
    try:
        from typesafe_sdk import Noul, TypeSafeClient
    except ImportError as exc:
        return Evaluation("EVALUATION ERROR", "", {}, f"TypeSafe SDK unavailable: {exc}")
    questions = {criterion.criterion_id: Noul(instructions=_criterion_instructions(criterion)) for criterion in criteria}
    try:
        # The SDK reads TYPESAFE_API_KEY by default; this workspace names the key SYSTEM_ONE_API.
        with TypeSafeClient(api_key=os.environ["SYSTEM_ONE_API"], model=model) as client:
            response = client.system_one(state={"proposal": request.payload}, questions=questions, model=model)
        results = {criterion.criterion_id: float(response.nouls[criterion.criterion_id].noul) for criterion in criteria}
        effective_model = str(getattr(response, "model", None) or model or "jev")
        return Evaluation("EVALUATED", effective_model, results)
    except Exception as exc:  # provider failure must remain visible and non-authorizing
        return Evaluation("EVALUATION ERROR", model or "", {}, f"{type(exc).__name__}: {exc}")


def evaluate_with_headless(request: PendingRequest, criteria: tuple[Criterion, ...]) -> Evaluation:
    """Fresh CLI evaluation: reasons only, never invented calibrated probabilities."""
    import shutil
    runtime = "hermes"
    executable = shutil.which(runtime)
    if not executable:
        return Evaluation("EVALUATION UNAVAILABLE", runtime, {}, f"{runtime} CLI unavailable")
    payload = {"proposal": request.payload, "criteria": [_criterion_instructions(c) | {"id": c.criterion_id} for c in criteria]}
    prompt = ("Review only the following literal proposal and advisory questions. "
              "Do not consult files, memory, tools, or other context. Return only a JSON object "
              "with a concerns array. Each concern must have criterion_id and reason. "
              "List only problems supported by the proposal; if none use an empty array. "
              "Do not invent numerical scores.\n" + canonical_json(payload))
    # Main agent's profile and model, but no tools ("none" matches no toolset) and no workspace context.
    command = [executable, "chat", "--oneshot", "--ignore-rules", "-t", "none", "--query-file", "-",
               "--run-budget", "55", "--max-turns", "3", "-Q"]
    if os.environ.get("HERMES_EVALUATOR_PROVIDER"):
        command.extend(["--provider", os.environ["HERMES_EVALUATOR_PROVIDER"]])
    if os.environ.get("HERMES_EVALUATOR_MODEL"):
        command.extend(["--model", os.environ["HERMES_EVALUATOR_MODEL"]])
    try:
        # Each call is a new CLI process; no resume or session reuse is permitted.
        env = os.environ.copy()
        process = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=65, check=False, env=env)
        if process.returncode:
            return Evaluation("EVALUATION UNAVAILABLE", runtime, {}, (process.stderr or process.stdout)[-600:])
        output = process.stdout.strip()
        if output.startswith("```"):
            output = re.sub(r"^```(?:json)?\s*|\s*```$", "", output).strip()
        try: result = json.loads(output)
        except json.JSONDecodeError:
            start, end = output.find("{"), output.rfind("}")
            result = json.loads(output[start:end+1]) if start >= 0 and end > start else None
        concerns = result.get("concerns") if isinstance(result, dict) else None
        ids = {c.criterion_id for c in criteria}
        if not isinstance(concerns, list) or any(
            not isinstance(row, dict) or row.get("criterion_id") not in ids or
            not isinstance(row.get("reason"), str) or not row["reason"].strip() for row in concerns
        ):
            return Evaluation("EVALUATION UNAVAILABLE", runtime, {}, "headless evaluator returned unusable concerns")
        return Evaluation("CONCERNS", runtime, {}, concerns=tuple(
            f"{row['criterion_id']}: {row['reason']}" for row in concerns))
    except Exception as exc:
        return Evaluation("EVALUATION UNAVAILABLE", runtime, {}, f"{type(exc).__name__}: {exc}")


def evaluate_request(
    request: PendingRequest,
    catalog: Catalog,
    evaluator: Callable[[PendingRequest, tuple[Criterion, ...]], Evaluation] | None = None,
    model: str | None = None,
) -> Evaluation:
    retained = detect_possible_secrets(request.payload)
    if retained:
        return Evaluation("RETAINED LOCALLY", "", {}, retention_categories=retained)
    if not catalog.criteria:
        return Evaluation("NO CRITERIA", "", {})
    if evaluator is not None:
        return evaluator(request, catalog.criteria)
    return evaluate_with_jev(request, catalog.criteria, model)


def _memory_limit(home: Path, target: str) -> int:
    defaults = {"memory": 2200, "user": 1375}
    config = home / "config.yaml"
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return defaults[target]
    keys = ("memory_char_limit", "memory_max_chars", "memory_chars") if target == "memory" else (
        "user_char_limit", "user_max_chars", "user_chars")
    for key in keys:
        match = re.search(rf"^\s*{re.escape(key)}\s*:\s*(\d+)\s*(?:#.*)?$", text, re.MULTILINE)
        if match:
            return int(match.group(1))
    return defaults[target]


def _live_memory_entries(home: Path, target: str) -> tuple[list[dict[str, Any]], int]:
    path = home / "memories" / ("USER.md" if target == "user" else "MEMORY.md")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    entries = [{"text": part, "chars": len(part)} for part in re.split(r"(?m)^§\s*$", text) if part.strip()]
    return entries, _memory_limit(home, target)


def route_with_jev(
    request: PendingRequest, live_entries: list[dict[str, Any]], other_pending: list[dict[str, Any]],
) -> dict[str, Any]:
    """Route one literal request with contextual memory and same-target pending work."""
    from typesafe_sdk import Choice, Noul, TypeSafeClient

    options = {
        "durable-fact": "A durable preference, correction, decision, constraint, or useful fact that belongs in memory for every session.",
        "procedure": "Instructions for how to perform a task; route to a skill under rule R2, not memory.",
        "idea": "An unstarted future project or idea; route to the ideas vault under rule R3.",
        "todo-or-progress": "A pending task, current progress, or time-bound status; reject under rule R4 because it will go stale.",
        "reachable-elsewhere": "Already available in a skill, file, note, code, or other reachable source; a short pointer may suffice, or reject as duplicative.",
    }
    questions: dict[str, Any] = {
        "home": Choice(
            instructions={
                "proposal": request.payload,
                "task": "Select the best disposition for this request's main content. Choose exactly one option.",
            },
            criteria=options,
        ),
        "contradicts_live": Noul(instructions={
            "proposal": request.payload, "live_entries": live_entries,
            "question": "Would adding this request contradict any currently live entry? Yes only for a genuine contradiction, not mere overlap.",
        }),
        "contains_secret": Noul(instructions={
            "proposal": request.payload,
            "question": "Does the proposal contain a credential, password, token, private key, or other secret that must not be stored?",
        }),
        "mixes_facts": Noul(instructions={
            "proposal": request.payload,
            "question": "Does this request combine multiple unrelated durable facts that should be split into separate memory entries?",
        }),
        "dated_status": Noul(instructions={
            "proposal": request.payload,
            "question": "Does this request state time-bound status or a fact likely to become stale?",
        }),
        "drops_live_info": Noul(instructions={
            "proposal": request.payload, "live_entries": live_entries,
            "question": "Would applying a replace or remove operation discard information in the live entries that remains useful?",
        }),
    }
    for item in other_pending:
        questions[f"superseded_by_{item['id']}"] = Noul(instructions={
            "proposal": request.payload,
            "other_pending_request": {"id": item["id"], "payload": item["payload"]},
            "question": "Does this other pending request supersede this proposal by replacing or containing its information?",
        })
    state = {
        "request": {"id": request.pending_id, "payload": request.payload},
        "live_entries": live_entries,
        "memory_limit_chars": _memory_limit(request.home, str(request.payload.get("target", "memory"))),
        "other_pending": other_pending,
    }
    with TypeSafeClient(api_key=os.environ["SYSTEM_ONE_API"], model="jev-1.13.0") as client:
        response = client.system_one(state=state, questions=questions, model="jev-1.13.0")
    choice = response.choices["home"]
    nouls = {key: float(answer.noul) for key, answer in response.nouls.items()}
    usage = getattr(response, "usage", None)
    usage_tokens = {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }
    return {
        "model": str(getattr(response, "model", None) or "jev-1.13.0"),
        "choice": str(choice.choice),
        "confidence": float(choice.confidence),
        "probabilities": {key: float(value) for key, value in choice.probabilities.items()},
        "nouls": nouls,
        "usage_tokens": usage_tokens,
    }


def shadow(inventory: Inventory, workspace: Path, instance: str) -> list[dict[str, Any]]:
    """Route pending requests and append audit rows; never decide or mutate a request."""
    if not os.environ.get("SYSTEM_ONE_API"):
        load_checkout_env()
    if not os.environ.get("SYSTEM_ONE_API"):
        raise ReviewError("SYSTEM_ONE_API is not configured")
    output = workspace / ".agents" / "memory-review" / "shadow" / (time.strftime("%Y-%m-%d") + ".jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for request in inventory.requests:
        target = str(request.payload.get("target", "memory"))
        live, _limit = _live_memory_entries(request.home, target)
        others = []
        for other in inventory.requests:
            if other is request or other.profile != request.profile or other.subsystem != request.subsystem:
                continue
            if str(other.payload.get("target", "memory")) != target:
                continue
            others.append({"id": other.pending_id, "payload": other.payload})
        routed = route_with_jev(request, live, others)
        row = {
            "instance": instance, "request_id": request.pending_id,
            "record_sha": request.record_sha256, "payload_sha": request.payload_sha256,
            "model": routed["model"], "choice": routed["choice"],
            "confidence": routed["confidence"], "probabilities": routed["probabilities"],
            "nouls": routed["nouls"], "usage_tokens": routed["usage_tokens"],
            "timestamp": time.time(),
        }
        with output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        results.append(row)
    return results


def _review_state_path(root: Path) -> Path:
    path = root / "curate-memory" / "state.json"
    legacy = root / "memory-request-review" / "state.json"
    if not path.exists() and legacy.exists():  # the skill was renamed; keep its decision history
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy.replace(path)
    return path


def load_review_state(root: Path) -> dict[str, Any]:
    path = _review_state_path(root)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"results": {}, "decisions": []}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"results": {}, "decisions": []}
    if not isinstance(state, dict):
        return {"results": {}, "decisions": []}
    results = state.get("results") if isinstance(state.get("results"), dict) else {}
    decisions = state.get("decisions") if isinstance(state.get("decisions"), list) else []
    return {"results": results, "decisions": decisions}


def save_review_state(root: Path, state: dict[str, Any]) -> None:
    path = _review_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def learn_decisions(state: dict[str, Any]) -> dict[str, Any]:
    """Summarize human-labeled decision types without granting automatic authority."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in state.get("decisions", []):
        if not isinstance(row, dict) or not isinstance(row.get("decision_type"), str) or not row["decision_type"]:
            continue
        groups.setdefault(row["decision_type"], []).append(row)
    summaries = {}
    for decision_type, rows in sorted(groups.items()):
        streak = 0
        for row in reversed(rows):
            if row.get("matched") is not True:
                break
            streak += 1
        mismatches = [
            {"at": row.get("at"), "decision": row.get("decision"), "proposal": row.get("proposal"),
             "why": row.get("why") or ""}
            for row in rows if row.get("matched") is False
        ]
        summaries[decision_type] = {
            "total_decisions": len(rows),
            "matched_streak": streak,
            "mismatches": mismatches,
            "graduation_candidate": streak >= GRADUATION_STREAK,
        }
    return {"graduation_streak_required": GRADUATION_STREAK, "decision_types": summaries,
            "automatic_authority": "human approval required"}


def stage_trimmed_request(request: PendingRequest, text: str) -> dict[str, Any]:
    if request.subsystem != "memory":
        raise ReviewError("Trim currently supports memory requests only.")
    target = request.payload.get("target", "memory")
    if target not in {"memory", "user"}:
        raise ReviewError("Trim requires a memory request targeting memory or user.")
    if not text.strip():
        raise ReviewError("Trimmed text must not be empty.")
    from tools import write_approval as wa
    payload = {"action": "add", "target": target, "content": text}
    previous_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(request.home)
    try:
        record = wa.stage_write(wa.MEMORY, payload, summary=f"trimmed memory request: {text[:120]}",
                                origin=wa.current_origin())
    finally:
        if previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous_home
    staged_path = request.home / "pending" / "memory" / f"{record.get('id', '')}.json"
    if not record.get("id") or not staged_path.is_file():
        raise ReviewError("Hermes did not persist the trimmed pending request.")
    return record


def _store_evaluation(state: dict[str, Any], request: PendingRequest, catalog: Catalog, evaluation: Evaluation) -> None:
    if evaluation.status != "EVALUATED" or not evaluation.model:
        return
    results = state.setdefault("results", {})
    for criterion in catalog.criteria:
        probability = evaluation.results.get(criterion.criterion_id)
        if probability is not None:
            results[cache_key(request, criterion, evaluation.model)] = {"probability": probability}


def evaluate_one(
    request: PendingRequest, catalog: Catalog, model: str | None = None, state: dict[str, Any] | None = None,
) -> Evaluation:
    """Evaluate only the request about to be shown; later pendings wait their turn.

    A result is reusable only when the caller supplies the same effective model
    identity and its payload/criterion-version cache key matches exactly.
    """
    state = state if state is not None else {"results": {}}
    retained = detect_possible_secrets(request.payload)
    if retained:
        return Evaluation("RETAINED LOCALLY", "", {}, retention_categories=retained)
    if not catalog.criteria:
        return Evaluation("NO CRITERIA", "", {})
    cached = reusable_results(request, catalog, model, state.get("results", {})) if model else {}
    if len(cached) == len(catalog.criteria):
        return Evaluation("EVALUATED", model, cached)
    # A possible secret is retained locally by the caller-facing show path.
    # Remote System One is preferred only when explicitly configured; every
    # failure falls back to a fresh headless Hermes evaluator.
    evaluation = evaluate_with_jev(request, catalog.criteria, model)
    if evaluation.status != "EVALUATED":
        evaluation = evaluate_with_headless(request, catalog.criteria)
    _store_evaluation(state, request, catalog, evaluation)
    return evaluation



def cache_key(request: PendingRequest, criterion: Criterion, model: str) -> str:
    return ":".join((request.profile, request.subsystem, request.pending_id, request.payload_sha256,
                     criterion.criterion_id, str(criterion.version), model))


def reusable_results(request: PendingRequest, catalog: Catalog, model: str, cache: dict[str, Any]) -> dict[str, float]:
    reusable: dict[str, float] = {}
    for criterion in catalog.criteria:
        row = cache.get(cache_key(request, criterion, model))
        if isinstance(row, dict) and isinstance(row.get("probability"), (float, int)):
            reusable[criterion.criterion_id] = float(row["probability"])
    return reusable


_WIDTH = 72
_DECISIONS = "approve · reject · pending · discuss"
# Location fields (skill file paths) are deliberately not rendered: the reviewer
# judges what is added, deleted, or replaced, not where it lands in the file.
_KNOWN_OPERATION_KEYS = {
    "action", "name", "target", "file_path", "old_text", "old_string", "content", "new_string", "file_content",
}
_VERBS = {
    "add": "ADD", "create": "ADD", "write_file": "ADD",
    "remove": "DELETE", "delete": "DELETE", "remove_file": "DELETE",
    "replace": "REPLACE", "patch": "REPLACE", "edit": "REPLACE",
}


@dataclass(frozen=True)
class Operation:
    verb: str
    old: str = ""
    new: str = ""


def _payload_operations(payload: dict[str, Any]) -> list[Any]:
    operations = payload.get("operations")
    return list(operations) if isinstance(operations, list) else [payload]


def describe_operations(request: PendingRequest) -> list[Operation]:
    """Reduce a native payload to ADD/DELETE/REPLACE rows without hiding any content."""
    described: list[Operation] = []
    for raw in _payload_operations(request.payload):
        if not isinstance(raw, dict):
            described.append(Operation("UNKNOWN", new=canonical_json(raw)))
            continue
        action = str(raw.get("action", "unknown"))
        old = str(raw.get("old_text", raw.get("old_string", "")) or "")
        new = str(raw.get("content", raw.get("new_string", raw.get("file_content", ""))) or "")
        extra = {key: value for key, value in raw.items() if key not in _KNOWN_OPERATION_KEYS}
        if extra:
            new = (new + "\n" if new else "") + canonical_json(extra)
        # A replace that keeps its old text intact only adds text next to it.
        if old and new != old and new.endswith(old):
            described.append(Operation("ADD", new=new[:-len(old)].rstrip()))
        elif old and new != old and new.startswith(old):
            described.append(Operation("ADD", new=new[len(old):].lstrip()))
        else:
            described.append(Operation(_VERBS.get(action, action.upper()), old, new))
    return described


def target_label(request: PendingRequest) -> str:
    payload = request.payload
    if request.subsystem == "memory":
        return str(payload.get("target", "memory"))
    names: list[str] = []
    for raw in _payload_operations(payload):
        name = (raw.get("name") if isinstance(raw, dict) else None) or payload.get("name")
        if name and str(name) not in names:
            names.append(str(name))
    return ", ".join(f"skill:{name}" for name in names) or "skill:<unknown>"


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width, break_on_hyphens=False, replace_whitespace=False) or [""])
    return lines


def _hang(prefix: str, text: str, width: int) -> list[str]:
    """Wrap text under a prefix; continuation lines align after the prefix."""
    body = _wrap(text, width - len(prefix))
    return [prefix + body[0]] + [" " * len(prefix) + line for line in body[1:]]


def _band(probability: float) -> str:
    return "likely" if probability >= 0.7 else "unlikely" if probability <= 0.3 else "uncertain"


def _bar(probability: float, cells: int = 10) -> str:
    filled = max(0, min(cells, round(probability * cells)))
    return "█" * filled + "░" * (cells - filled)


def _verdict_note(evaluation: Evaluation) -> str:
    if evaluation.status == "RETAINED LOCALLY":
        return "possible secret (" + ", ".join(evaluation.retention_categories) + "): kept local, Jev not called"
    if evaluation.status == "NO CRITERIA":
        return "no criteria in the catalog: Jev not called"
    if evaluation.error:
        label = "headless evaluator" if evaluation.status == "EVALUATION UNAVAILABLE" else "Jev"
        return f"{label} failed: " + evaluation.error
    return ""


def _questions(evaluation: Evaluation, catalog: Catalog) -> list[tuple[str, float | None]]:
    """Every catalog question, scored or not, so the reviewer always sees what Jev was asked."""
    return [(criterion.question, evaluation.results.get(criterion.criterion_id)) for criterion in catalog.criteria]


def render_panel(
    request: PendingRequest, evaluation: Evaluation, position: int, total: int, catalog: Catalog | None = None,
    staleness: tuple[str, ...] = (),
) -> str:
    catalog = catalog or Catalog(1, ())
    inner = _WIDTH - 4
    rule = lambda left, right: left + "─" * (_WIDTH - 2) + right  # noqa: E731

    def rule_with_junction(left: str, right: str, content_col: int, junction: str) -> str:
        """Draw a horizontal border with one vertical junction aligned to content column."""
        span = ["─"] * (_WIDTH - 2)
        index = content_col + 1  # content starts after leading "│ " in boxed rows
        if 0 <= index < len(span):
            span[index] = junction
        return left + "".join(span) + right
    def _fit(text: str) -> str:
        if len(text) <= inner:
            return text
        if inner <= 1:
            return text[:inner]
        return text[:inner - 1] + "…"

    box = lambda text: f"│ {_fit(text):<{inner}} │"  # noqa: E731

    def _compose_with_right(left: str, right: str, width: int) -> str:
        """Keep right-aligned metadata visible; shrink the left side first."""
        if len(left) + 1 + len(right) <= width:
            return left + " " * (width - len(left) - len(right)) + right
        if width <= len(right):
            return right[:width]
        room_for_left = width - len(right) - 1
        if room_for_left <= 0:
            return right[:width]
        if len(left) > room_for_left:
            left = left[:max(1, room_for_left - 1)] + ("…" if room_for_left > 1 else "")
        return left + " " * (width - len(left) - len(right)) + right

    head = f"REQUEST {position}/{total}"
    ident = request.profile
    left = f"{head} │   Target: {target_label(request)}"
    header = _compose_with_right(left, ident, inner)
    divider_col = header.find("│")
    if divider_col >= 0:
        rows = [rule_with_junction("╭", "╮", divider_col, "┬"), box(header)]
    else:
        rows = [rule("╭", "╮"), box(header)]
    # Jev comes first: long operations must never push the verdict out of a collapsed view.
    if divider_col >= 0:
        rows.append(rule_with_junction("├", "┤", divider_col, "┴"))
    else:
        rows.append(rule("├", "┤"))
    note = _verdict_note(evaluation)
    question_blocks: list[str] = []
    for flag in staleness:
        question_blocks.extend(_hang("⚠ ", _STALENESS_TEXT.get(flag, flag), inner))
    if staleness:
        question_blocks.append("")
    questions = _questions(evaluation, catalog)
    for index, (question, probability) in enumerate(questions):
        if index > 0:
            question_blocks.append("")
        question_blocks.extend(_wrap(question, inner))
        question_blocks.append("·  no score" if probability is None
                               else f"{_bar(probability)}  {probability:.2f}")
    if evaluation.status == "CONCERNS":
        question_blocks.append("Evaluator: " + evaluation.model + " (reasons, no calibrated score)")
        for concern in evaluation.concerns or ("No concerns returned.",):
            question_blocks.extend(_hang("• ", concern, inner))  # wrapped: a cut reason cannot be judged
    if note and evaluation.status != "RETAINED LOCALLY":
        if question_blocks:
            question_blocks.append("")
        question_blocks.extend(_wrap(note, inner))
    if question_blocks:
        rows.append(box(""))
        rows += [box(line) for line in question_blocks]
        rows.append(box(""))
    rows.append(rule("├", "┤"))
    if evaluation.status == "RETAINED LOCALLY":
        rows += [box(line) for line in _wrap("Content withheld: " + note, inner)]
    else:
        def _verb_badge(verb: str) -> list[str]:
            label = f" {verb} "
            top = "╭" + "─" * len(label) + "╮"
            mid = "│" + label + "│"
            bot = "╰" + "─" * len(label) + "╯"
            return [top.center(inner), mid.center(inner), bot.center(inner)]

        operations = describe_operations(request)
        if operations:
            rows.append(box(""))
        for index, op in enumerate(operations, 1):
            if index > 1:
                rows.append(box(""))
            rows += [box(line) for line in _verb_badge(op.verb)]
            if op.old:
                rows += [box(line) for line in _hang("   − ", op.old, inner)]
            if op.new:
                rows += [box(line) for line in _hang("   + ", op.new, inner)]
        if operations:
            rows.append(box(""))
    rows += [rule("╰", "╯")]
    return "\n".join(rows)


_STALENESS_TEXT = {
    "old-text-missing": "Old text no longer present: the target no longer contains text this request replaces or deletes.",
    "target-changed": "Target changed after this request: it was edited after the request was made; check it still applies.",
}


def _skill_roots(request: PendingRequest) -> list[Path]:
    local = request.home / "skills"
    if request.profile == "default":
        try:  # Hermes's own precedence: trusted project skills (the workspace) first, then local, then external
            from agent.skill_utils import get_skill_search_roots
            return [Path(path) for _tier, path in get_skill_search_roots(local)]
        except Exception:
            pass
    return [local]


def _find_skill_dir(request: PendingRequest, name: str) -> Path | None:
    for root in _skill_roots(request):
        if root.is_dir():
            for skill_md in sorted(root.rglob("SKILL.md")):
                if skill_md.parent.name == name:
                    return skill_md.parent
    return None


def _squash(text: str) -> str:
    return " ".join(text.split())


def _latest_mtime(path: Path) -> float:
    if path.is_file():
        return path.stat().st_mtime
    return max((item.stat().st_mtime for item in path.rglob("*") if item.is_file()), default=0.0)


def staleness(request: PendingRequest) -> tuple[str, ...]:
    """Local, read-only facts about whether a request still fits its target. Never sent to Jev.

    old-text-missing: a replace/delete names text the current target (or an earlier operation
    of the same batch) does not contain. target-changed: the target was edited after the
    request was made. Whitespace is ignored because Hermes matches old text fuzzily.
    """
    created_at = float(request.record.get("created_at", 0) or 0)
    targets: list[Path] = []
    missing = False
    written: dict[Path, str] = {}
    for raw in _payload_operations(request.payload):
        if not isinstance(raw, dict):
            continue
        if request.subsystem == "memory":
            target = request.home / "memories" / ("USER.md" if raw.get("target", request.payload.get("target")) == "user" else "MEMORY.md")
            path, base = target, target
        else:
            name = raw.get("name") or request.payload.get("name")
            base = _find_skill_dir(request, str(name)) if name else None
            if base is None:
                continue
            path = base / str(raw.get("file_path") or "SKILL.md")
        if base not in targets:
            targets.append(base)
        old = str(raw.get("old_text", raw.get("old_string", "")) or "")
        new = str(raw.get("content", raw.get("new_string", raw.get("file_content", ""))) or "")
        if old:
            current = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            if _squash(old) not in _squash(current + "\n" + written.get(path, "")):
                missing = True
        if new:
            written[path] = written.get(path, "") + "\n" + new
    flags = ["old-text-missing"] if missing else []
    if created_at and any(target.exists() and _latest_mtime(target) > created_at for target in targets):
        flags.append("target-changed")
    return tuple(flags)


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(b"missing")
        return digest.hexdigest()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


def _destination_digest(request: PendingRequest) -> str:
    if request.subsystem == "memory":
        filename = "USER.md" if request.payload.get("target") == "user" else "MEMORY.md"
        return _tree_digest(request.home / "memories" / filename)
    digest = hashlib.sha256()
    for root in _skill_roots(request):  # workspace skills live outside the profile's own skills dir
        digest.update(str(root).encode("utf-8"))
        digest.update(_tree_digest(root).encode("utf-8"))
    return digest.hexdigest()


def _apply_native_decision_at_home(
    home: Path, subsystem: str, pending_id: str, decision: str, expected_record_sha256: str,
) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise ReviewError("Only approve or reject can invoke Hermes's native flow.")
    path = home / "pending" / subsystem / f"{pending_id}.json"
    try:
        current_raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StaleRequestError("The pending request was already resolved.") from exc
    if sha256_text(current_raw) != expected_record_sha256:
        raise StaleRequestError("The pending request changed after review; inspect it again before acting.")
    request = _parse_pending_file(path, "native", subsystem, home)
    destination_before = _destination_digest(request)
    from tools import write_approval as wa
    if decision == "reject":
        removed = wa.discard_pending(request.subsystem, request.pending_id)
        destination_unchanged = destination_before == _destination_digest(request)
        return {"success": bool(removed and not path.exists() and destination_unchanged), "decision": decision,
                "pending_removed": not path.exists(), "destination": target_label(request),
                "destination_unchanged": destination_unchanged}
    from hermes_cli.write_approval_commands import _apply_one
    if request.subsystem == wa.MEMORY:
        from tools.memory_tool import load_on_disk_store
        store = load_on_disk_store()
    else:
        store = None
    ok, error, result = _apply_one(request.subsystem, request.record, store)
    if not ok:
        return {"success": False, "decision": decision, "error": error, "native_result": result,
                "pending_removed": False}
    discarded = wa.discard_pending(request.subsystem, request.pending_id)
    return {"success": bool(discarded and not path.exists()), "decision": decision, "native_result": result,
            "destination": target_label(request), "destination_changed": destination_before != _destination_digest(request),
            "pending_removed": not path.exists()}


def apply_native_decision(request: PendingRequest, decision: str, expected_record_sha256: str) -> dict[str, Any]:
    path = request.home / "pending" / request.subsystem / f"{request.pending_id}.json"
    try:
        current_raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StaleRequestError("The pending request was already resolved.") from exc
    if sha256_text(current_raw) != expected_record_sha256:
        raise StaleRequestError("The pending request changed after review; inspect it again before acting.")
    command = [
        sys.executable, str(Path(__file__).resolve()), "native-apply", "--subsystem", request.subsystem,
        "--pending-id", request.pending_id, "--decision", decision,
        "--expected-record-sha256", expected_record_sha256,
    ]
    runtime_path = os.pathsep.join(path for path in sys.path if path)
    process = subprocess.run(
        command,
        # The child must retain the exact prepared interpreter selected for this
        # review. Otherwise its startup guard falls back to a checkout-local
        # path even though we deliberately invoked sys.executable below.
        env={
            "HERMES_HOME": str(request.home),
            "HERMES_MEMORY_REVIEW_PYTHON": sys.executable,
            "PYTHONPATH": runtime_path,
        },
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "native Hermes decision failed"
        raise ReviewError(detail)
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ReviewError("Native Hermes decision returned invalid JSON.") from exc
    if not isinstance(result, dict):
        raise ReviewError("Native Hermes decision returned a non-object result.")
    return result


def load_checkout_env() -> None:
    """Read KEY=VALUE lines from the checkout's gitignored .env; real env vars win."""
    path = Path(__file__).resolve().parents[4] / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def ensure_review_runtime() -> None:
    # Resolve the checkout, not the caller's cwd or a project-skill symlink.
    default = Path(__file__).resolve().parents[4] / ".agents" / "memory-review" / "bin" / "python"
    selected = os.environ.get("HERMES_MEMORY_REVIEW_PYTHON") or str(default)
    interpreter = os.path.abspath(os.path.expanduser(selected))
    if not Path(interpreter).is_file() or not os.access(interpreter, os.X_OK):
        raise ReviewError(
            f"Review interpreter is unavailable: {interpreter}. "
            f"Run `python3 {Path(__file__).resolve().with_name('prepare_environment.py')}` once, "
            "or set HERMES_MEMORY_REVIEW_PYTHON to a prepared interpreter. Review never installs dependencies."
        )
    # Do not resolve the executable symlink: virtualenvs share a base Python.
    if os.path.abspath(sys.executable) != interpreter:
        os.execv(interpreter, [interpreter, str(Path(__file__).resolve()), *sys.argv[1:]])


def sweep(inventory: Inventory, home_root: Path) -> list[dict[str, Any]]:
    """Reject, without the human, every request whose old text is gone from its target.

    The human approved this one automatic rule: such a request cannot apply cleanly.
    `target-changed` alone never triggers it, since approving one request flags the others.
    """
    swept: list[dict[str, Any]] = []
    for request in inventory.requests:
        if "old-text-missing" not in staleness(request):
            continue
        try:
            result = apply_native_decision(request, "reject", request.record_sha256)
        except ReviewError as exc:
            result = {"success": False, "error": str(exc)}
        state = load_review_state(home_root)
        state.setdefault("decisions", []).append({
            "at": time.time(), "profile": request.profile, "subsystem": request.subsystem,
            "pending_id": request.pending_id, "record_sha256": request.record_sha256,
            "payload_sha256": request.payload_sha256, "decision": "reject",
            "success": bool(result.get("success")), "decided_by": "auto", "reason": "old-text-missing",
        })
        save_review_state(home_root, state)
        swept.append({"profile": request.profile, "subsystem": request.subsystem, "id": request.pending_id,
                      "target": target_label(request), "summary": str(request.record.get("summary", "")),
                      "created_at": request.record.get("created_at"), "success": bool(result.get("success")),
                      **({"error": result["error"]} if result.get("error") else {})})
    return swept


def _default_catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "criteria.json"


def _user_entries(home: Path) -> list[str]:
    text = (home / "memories" / "USER.md").read_text(encoding="utf-8")
    return [part.strip("\r\n") for part in re.split(r"(?m)^§[ \t]*$", text) if part.strip("\r\n")]


def _metadata_path(home: Path) -> Path:
    return home / "memories" / "USER.json"


def _read_metadata(home: Path) -> dict[str, Any]:
    path = _metadata_path(home)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("items"), list):
        raise ReviewError(f"Invalid USER lifespan metadata: {path}")
    return value


def _write_metadata(home: Path, value: dict[str, Any]) -> None:
    path = _metadata_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _six_months_after(day: date) -> date:
    month_index = day.year * 12 + day.month - 1 + 6
    year, month = divmod(month_index, 12)
    month += 1
    import calendar
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _lifespan_item(text: str, lifespan: str, due: date | None, today: date, source: str) -> dict[str, Any]:
    if lifespan == "lasting":
        due = None
    elif lifespan == "until" and due is None:
        raise ReviewError("lifespan 'until' requires --date.")
    elif lifespan == "review" and due is None:
        due = _six_months_after(today)
    return {"key": sha256_text(text), "text": text, "lifespan": lifespan,
            "date": due.isoformat() if due else None, "created": today.isoformat(),
            "verified": today.isoformat(), "source": source}


def _personality_text(home: Path, name: str) -> str | None:
    """Read one Hermes personality block from config.yaml without a YAML dependency."""
    try:
        lines = (home / "config.yaml").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    try:
        start = lines.index("personalities:")
    except ValueError:
        return None
    header = f"  {name}: |"
    for i in range(start + 1, len(lines)):
        if lines[i].startswith(header):
            body = []
            for line in lines[i + 1:]:
                if line.strip() and not line.startswith("    "):
                    break
                body.append(line[4:])
            return "\n".join(body).strip()
        if lines[i] and not lines[i].startswith(" "):
            return None
    return None


def _channel_prompt_text(home: Path, platform: str, chat_id: str) -> str | None:
    """Read one per-chat prompt (root `<platform>.channel_prompts.<chat_id>` block scalar) without YAML."""
    try:
        lines = (home / "config.yaml").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    in_platform = in_prompts = False
    for i, line in enumerate(lines):
        if line and not line.startswith(" "):
            in_platform, in_prompts = line == f"{platform}:", False
            continue
        if in_platform and line.startswith("  ") and not line.startswith("   "):
            in_prompts = line.strip() == "channel_prompts:"
            continue
        if in_prompts and line.lstrip("'\" ").startswith(chat_id) and line.rstrip().endswith(("|", "|-")):
            body = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.startswith("      "):
                    break
                body.append(nxt[6:])
            return "\n".join(body).strip()
    return None


def manage_lifespan(args: argparse.Namespace) -> None:
    home = args.hermes_home
    today = args.today if args.lifespan_command == "check" and args.today else date.today()
    if args.lifespan_command == "init":
        path = _metadata_path(home)
        if path.exists():
            raise ReviewError(f"Refusing to overwrite existing {path}.")
        try:
            classification = json.loads(args.classify.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReviewError(f"Cannot read classification file {args.classify}: {exc}") from exc
        rows = classification.get("items") if isinstance(classification, dict) else None
        if not isinstance(rows, list):
            raise ReviewError("Classification file must contain an items list.")
        by_text = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise ReviewError("Every classification item requires exact text and lifespan fields.")
            by_text[row["text"]] = row
        items = []
        for text in _user_entries(home):
            row = by_text.get(text)
            if row is None:
                raise ReviewError("Classification file does not cover every USER.md entry.")
            lifespan = row.get("lifespan")
            if lifespan not in {"lasting", "until", "review"}:
                raise ReviewError(f"Invalid lifespan for entry: {text[:80]}")
            due = date.fromisoformat(row["date"]) if row.get("date") else None
            items.append(_lifespan_item(text, lifespan, due, today, "init"))
        _write_metadata(home, {"version": 1, "items": items})
        return
    entries = _user_entries(home)
    entry_keys = {sha256_text(text): text for text in entries}
    metadata = _read_metadata(home)
    if args.lifespan_command == "check":
        known = {item.get("key"): item for item in metadata["items"] if isinstance(item, dict)}
        due = [item for item in known.values() if item.get("lifespan") in {"until", "review"}
               and item.get("date") and date.fromisoformat(item["date"]) <= today]
        unclassified = [text for key, text in entry_keys.items() if key not in known]
        orphaned = [item for key, item in known.items() if key not in entry_keys]
        for heading, rows, describe in (
            ("DUE", due, lambda item: f"{item['date']} {item['lifespan']}: {item['text']}"),
            ("UNCLASSIFIED", unclassified, lambda text: text),
            ("ORPHANED", orphaned, lambda item: f"{item.get('key')}: {item.get('text', '')}"),
        ):
            for row in rows:
                print(f"{heading}: {describe(row)}")
        # Standing preferences live outside USER.md (e.g. the communication style personality): never
        # injected into USER.md, never pruned; only flag when the live source drifted from the tracked copy.
        for item in metadata.get("standing", []):
            source = str(item.get("source", "")) if isinstance(item, dict) else ""
            if source.startswith("personality:"):
                live = _personality_text(home, source.split(":", 1)[1])
            elif source.startswith("channel_prompt:") and source.count(":") == 2:
                live = _channel_prompt_text(home, *source.split(":")[1:])
            else:
                continue
            if live is None:
                print(f"STANDING MISSING: {item.get('type')} ({item['source']})")
            elif sha256_text(live) != item.get("sha256"):
                print(f"STANDING DRIFT: {item.get('type')} ({item['source']}) differs from USER.json")
        return
    if args.lifespan_command == "prune":
        keep = [item for item in metadata["items"] if isinstance(item, dict) and item.get("key") in entry_keys]
        if len(keep) != len(metadata["items"]):
            metadata["items"] = keep
            _write_metadata(home, metadata)
        return
    matches = [text for text in entries if text.startswith(args.entry_prefix)]
    if len(matches) != 1:
        raise ReviewError(f"Entry prefix must match exactly one USER.md entry; matched {len(matches)}.")
    due = args.date
    if args.lifespan == "lasting" and due:
        raise ReviewError("lifespan 'lasting' does not accept --date.")
    if args.lifespan == "until" and not due:
        raise ReviewError("lifespan 'until' requires --date.")
    text = matches[0]
    new_item = _lifespan_item(text, args.lifespan, due, today, "set")
    metadata["items"] = [item for item in metadata["items"] if not isinstance(item, dict) or item.get("key") != new_item["key"]]
    metadata["items"].append(new_item)
    _write_metadata(home, metadata)


def forward_request(args: argparse.Namespace) -> Path:
    if not args.profile or not args.subsystem or not args.pending_id or not args.expected_record_sha256:
        raise ReviewError("Forward requires the reviewed profile, subsystem, pending id, and record hash.")
    if args.subsystem != "memory":
        raise ReviewError("Forward applies only to memory write requests.")
    project_dir = args.project_dir
    if not project_dir.is_absolute() or not project_dir.is_dir():
        raise ReviewError("--project-dir must be an absolute path to an existing project folder.")
    path = args.home_root / "pending" / args.subsystem / f"{args.pending_id}.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReviewError(f"Cannot read pending request: {exc}") from exc
    if sha256_text(raw) != args.expected_record_sha256:
        raise StaleRequestError("The pending request changed after review; inspect it again before acting.")
    try:
        request = _parse_pending_file(path, args.profile, args.subsystem, args.home_root)
    except (json.JSONDecodeError, ReviewError) as exc:
        raise ReviewError(f"Cannot parse pending request: {exc}") from exc
    target = "USER" if request.payload.get("target") == "user" else "MEMORY"
    created_at = float(request.record.get("created_at", 0) or 0)
    created = time.strftime("%Y-%m-%d", time.localtime(created_at)) if created_at else "unknown"
    destination = project_dir / "wiki" / "raw" / f"{date.today().isoformat()}-memory-request-{args.pending_id}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ReviewError(f"Refusing to overwrite existing file: {destination}")
    chunks = [
        "# Forwarded Hermes memory write request",
        f"Instance/profile: {args.profile}",
        f"Pending id: {args.pending_id}",
        f"Request created: {created}",
        f"Target file: {target}",
        f"Forwarded: {date.today().isoformat()}",
    ]
    for index, operation in enumerate(_payload_operations(request.payload), 1):
        if not isinstance(operation, dict):
            raise ReviewError("Pending request contains a non-object operation; refusing incomplete forwarding.")
        action = str(operation.get("action", "unknown"))
        chunks.extend((f"## Operation {index}: {action}", ""))
        for key in ("content", "old_text"):
            value = operation.get(key)
            if isinstance(value, str):
                chunks.extend((f"### {key}", "", value, ""))
    content = "\n".join(chunks) + "\n"
    try:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ReviewError(f"Refusing to overwrite existing file: {destination}") from exc
    print(f"Forwarded to {destination}")
    print("Reject next with decide --rule R9.")
    return destination


def review_skill_proposals(args: argparse.Namespace) -> None:
    queue = args.home_root / "curate-memory" / "skill-requests.jsonl"
    latest: dict[str, dict[str, Any]] = {}
    try:
        rows = queue.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        rows = []
    for line in rows:
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict) and row.get("request_id"):
            latest[row["request_id"]] = row
    if args.proposal_command == "list":
        proposals = []
        for request_id, row in latest.items():
            proposal = row.get("proposal")
            if not isinstance(proposal, dict) or row.get("proposal_status") != "prepared-not-opened":
                continue
            proposals.append({
                "id": request_id, "skill": row.get("skill_key"),
                "title": proposal.get("title"), "label": proposal.get("label"),
                "files": proposal.get("files"), "description": proposal.get("description"),
                "status": row.get("proposal_status"),
            })
        print(json.dumps({"proposals": proposals}, ensure_ascii=False, indent=2))
        return
    if args.decision not in ("approve", "reject") or not args.request_id:
        raise ReviewError("skill-proposals decide requires --request-id and --decision approve|reject.")
    row = latest.get(args.request_id)
    if not row or not isinstance(row.get("proposal"), dict) or row.get("proposal_status") != "prepared-not-opened":
        raise ReviewError("Shared-skill proposal is unavailable or already decided; list proposals again.")
    decision_row = {
        **row, "proposal_status": "human-approved" if args.decision == "approve" else "human-rejected",
        "proposal_decision": args.decision, "proposal_decided_at": time.time(),
    }
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(decision_row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    print(json.dumps({"id": args.request_id, "decision": args.decision, "opened": False}, ensure_ascii=False))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    if argv and argv[0] == "skill-proposals":
        parser = argparse.ArgumentParser(description="Review prepared shared-skill proposals; never open pull requests.")
        subparsers = parser.add_subparsers(dest="proposal_command", required=True)
        list_parser = subparsers.add_parser("list")
        list_parser.add_argument("--home-root", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        decide_parser = subparsers.add_parser("decide")
        decide_parser.add_argument("--home-root", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        decide_parser.add_argument("--request-id", required=True)
        decide_parser.add_argument("--decision", choices=("approve", "reject"), required=True)
        args = parser.parse_args(argv[1:])
        args.command = "skill-proposals"
        return args
    if argv and argv[0] == "forward":
        parser = argparse.ArgumentParser(description="Forward a reviewed memory request to project wiki sources.")
        parser.add_argument("--profile", choices=PROFILES, required=True)
        parser.add_argument("--subsystem", choices=SUBSYSTEMS, required=True)
        parser.add_argument("--pending-id", required=True)
        parser.add_argument("--expected-record-sha256", required=True)
        parser.add_argument("--project-dir", type=Path, required=True)
        parser.add_argument("--home-root", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        args = parser.parse_args(argv[1:])
        args.command = "forward"
        return args
    if argv and argv[0] == "lifespan":
        parser = argparse.ArgumentParser(description="Manage USER.md entry lifespan metadata.")
        subparsers = parser.add_subparsers(dest="lifespan_command", required=True)
        init_parser = subparsers.add_parser("init")
        init_parser.add_argument("--classify", type=Path, required=True)
        init_parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        check_parser = subparsers.add_parser("check")
        check_parser.add_argument("--today", type=date.fromisoformat)
        check_parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        set_parser = subparsers.add_parser("set")
        set_parser.add_argument("--entry-prefix", required=True)
        set_parser.add_argument("--lifespan", choices=("lasting", "until", "review"), required=True)
        set_parser.add_argument("--date", type=date.fromisoformat)
        set_parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        prune_parser = subparsers.add_parser("prune")
        prune_parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
        args = parser.parse_args(argv[1:])
        args.command = "lifespan"
        return args
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "show", "decide", "learn", "forward", "native-apply", "sweep", "shadow"))
    parser.add_argument("--home-root", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
    parser.add_argument("--hermes-home", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--instance", default="default")
    parser.add_argument("--catalog", type=Path, default=_default_catalog_path())
    parser.add_argument("--position", type=int, default=1)
    parser.add_argument("--profile", choices=PROFILES)
    parser.add_argument("--subsystem", choices=SUBSYSTEMS)
    parser.add_argument("--pending-id")
    parser.add_argument("--model", default=None)
    parser.add_argument("--decision", choices=DECISION_OPTIONS)
    parser.add_argument("--proposal", choices=DECISION_OPTIONS)
    parser.add_argument("--proposal-rule")
    parser.add_argument("--decision-type")
    parser.add_argument("--why")
    parser.add_argument("--text", help="new-only text to stage for a trim decision")
    parser.add_argument("--proposed-text", help="system-proposed trimmed text, for edit matching")
    parser.add_argument("--lifespan", choices=("lasting", "until", "review"))
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--expected-record-sha256")
    parser.add_argument("--human-decision", action="store_true")
    parser.add_argument("--rule", choices=("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"),
                        help="decide by a human-approved rule instead of an explicit human decision")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.command == "native-apply":
        if not args.subsystem or not args.pending_id or not args.expected_record_sha256 or args.decision not in {"approve", "reject"}:
            raise ReviewError("Native Hermes decision requires subsystem, pending id, decision, and reviewed record hash.")
        print(json.dumps(
            _apply_native_decision_at_home(
                args.home_root, args.subsystem, args.pending_id, args.decision, args.expected_record_sha256,
            ),
            ensure_ascii=False,
        ))
        return 0
    if args.command == "lifespan":
        manage_lifespan(args)
        return 0
    if args.command == "skill-proposals":
        review_skill_proposals(args)
        return 0
    if args.command == "forward":
        forward_request(args)
        return 0
    if args.command == "learn":
        print(json.dumps(learn_decisions(load_review_state(args.home_root)), ensure_ascii=False, indent=2))
        return 0
    inventory = inventory_pending(args.hermes_home if args.command == "shadow" else args.home_root)
    if args.command == "shadow":
        rows = shadow(inventory, args.workspace, args.instance)
        print(json.dumps({"instance": args.instance, "routed": len(rows), "ids": [row["request_id"] for row in rows]}, ensure_ascii=False))
        return 0
    if args.command == "inventory":
        output = {
            "counts": inventory.counts,
            "requests": [{"profile": item.profile, "subsystem": item.subsystem, "id": item.pending_id,
                          "record_sha256": item.record_sha256, "payload_sha256": item.payload_sha256}
                         for item in inventory.requests],
            "unreadable": list(inventory.unreadable),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    if not inventory.requests:
        print("No pending requests in the authorized profiles.")
        return 0
    if args.command == "sweep":
        print(json.dumps({"auto_rejected": sweep(inventory, args.home_root)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "show":
        if args.position < 1 or args.position > len(inventory.requests):
            raise ReviewError(f"position must be 1..{len(inventory.requests)}")
        request = inventory.requests[args.position - 1]
        catalog = load_catalog(args.catalog)
        state = load_review_state(args.home_root)
        evaluation = evaluate_one(request, catalog, args.model, state)
        flags = staleness(request)
        save_review_state(args.home_root, state)
        print(render_panel(request, evaluation, args.position, len(inventory.requests), catalog, flags))
        print(f"\nrecord_sha256: {request.record_sha256}")
        return 0
    if (not args.human_decision and not args.rule) or args.decision not in DECISION_OPTIONS:
        raise ReviewError("A native decision requires --human-decision or --rule, and --decision approve|reject|trim.")
    if args.rule and args.decision == "trim":
        raise ReviewError("Trim is a human decision, not an automatic rule action.")
    if args.decision == "trim" and (not args.human_decision or not args.text):
        raise ReviewError("Trim requires --human-decision and --text containing only the new part.")
    if args.decision == "trim" and args.proposal == "trim" and args.proposed_text is None:
        raise ReviewError("A trim proposal requires --proposed-text for edit matching.")
    if not args.expected_record_sha256:
        raise ReviewError("A native decision requires --expected-record-sha256 from the reviewed inventory.")
    if not args.profile or not args.subsystem or not args.pending_id:
        raise ReviewError("A native decision requires the reviewed profile, subsystem, and pending id.")
    request = next(
        (
            item for item in inventory.requests
            if (item.profile, item.subsystem, item.pending_id) == (args.profile, args.subsystem, args.pending_id)
        ),
        None,
    )
    if request is None:
        raise StaleRequestError("The reviewed pending request is no longer available; inspect the inventory again.")
    edited_trim = args.decision == "trim" and args.proposed_text is not None and args.text != args.proposed_text
    if args.human_decision and ((args.proposal is not None and args.decision != args.proposal) or edited_trim) and not args.why:
        raise ReviewError("When overriding the proposal or editing its trim, --why is required.")
    is_user = request.subsystem == "memory" and request.payload.get("target") == "user"
    if args.date and args.lifespan == "lasting":
        raise ReviewError("--date cannot be combined with --lifespan lasting.")
    if args.date and not is_user:
        raise ReviewError("--date and --lifespan apply only to approvals targeting user.")
    if args.lifespan and not is_user:
        raise ReviewError("--lifespan applies only to approvals targeting user.")
    if is_user and args.decision == "approve" and not args.lifespan:
        # The lifespan is decided in the review session, with the decision; no silent default.
        raise ReviewError("Approvals targeting user require --lifespan (agreed with the human during review).")
    if is_user and args.decision == "approve" and args.lifespan == "until" and not args.date:
        raise ReviewError("--lifespan until requires --date.")
    before_entries = set(_user_entries(request.home)) if is_user and args.decision == "approve" else set()
    staged = None
    original_text = "\n".join(
        str(operation.get("content", operation.get("new_text", "")) or "")
        for operation in _payload_operations(request.payload) if isinstance(operation, dict)
    )
    native_decision = "reject" if args.decision == "trim" else args.decision
    if args.decision == "trim":
        pending_path = request.home / "pending" / request.subsystem / f"{request.pending_id}.json"
        try:
            current_raw = pending_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StaleRequestError("The reviewed pending request is no longer available; inspect the inventory again.") from exc
        if sha256_text(current_raw) != args.expected_record_sha256:
            raise StaleRequestError("The pending request changed after review; inspect it again before staging a trim.")
        staged = stage_trimmed_request(request, args.text)
    result = apply_native_decision(request, native_decision, args.expected_record_sha256)
    if staged is not None:
        result = {**result, "decision": "trim", "staged_pending_id": staged["id"],
                  "staged_text": args.text, "original_text": original_text}
    if is_user and args.decision == "approve" and result.get("success"):
        try:
            today = date.today()
            after_entries = set(_user_entries(request.home))
            metadata_path = _metadata_path(request.home)
            metadata = _read_metadata(request.home) if metadata_path.exists() else {"version": 1, "items": []}
            added = after_entries - before_entries
            metadata["items"] = [item for item in metadata["items"]
                                 if isinstance(item, dict) and item.get("text") in after_entries]
            lifespan = args.lifespan
            for text in sorted(added):
                metadata["items"].append(_lifespan_item(text, lifespan, args.date, today, "approved-request"))
            _write_metadata(request.home, metadata)
        except Exception as exc:
            result["metadata_error"] = f"{type(exc).__name__}: {exc}"
    state = load_review_state(args.home_root)
    matched = None if args.proposal is None else (args.decision == args.proposal and not edited_trim)
    decision_row = {
        "at": time.time(), "profile": request.profile, "subsystem": request.subsystem,
        "pending_id": request.pending_id, "record_sha256": request.record_sha256,
        "payload_sha256": request.payload_sha256, "decision": args.decision,
        "success": bool(result.get("success")),
        "decided_by": "human" if args.human_decision else "rule",
        "proposal": args.proposal, "proposal_rule": args.proposal_rule,
        "decision_type": args.decision_type, "why": args.why,
        "matched": matched,
    }
    if args.rule:
        decision_row["reason"] = args.rule
    if staged is not None:
        decision_row.update({"original_text": original_text, "trimmed_text": args.text,
                             "proposed_text": args.proposed_text, "edited_proposal": edited_trim})
    state.setdefault("decisions", []).append(decision_row)
    save_review_state(args.home_root, state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    try:
        ensure_review_runtime()
        load_checkout_env()
        raise SystemExit(main())
    except ReviewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
