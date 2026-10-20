"""The command line: the first adapter (ADR 0012). It only reads and writes the files on the belts.

The project is the current folder unless --project is given.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from ergon.belt import PENDING
from ergon.intake import Intake
from ergon.plan import Plan
from ergon.split import Split

NODES = (Intake, Plan, Split)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ergon")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="project folder (holds wiki/)")
    cmd = parser.add_subparsers(dest="cmd", required=True)
    cmd.add_parser("submit", help="check a request file and put it on its node's belt").add_argument("file", type=Path)
    cmd.add_parser("run", help="process a node's inbox").add_argument("node", choices=[n.name for n in NODES])
    cmd.add_parser("status", help="requests per state, per node")
    cmd.add_parser("pending", help="everything that waits for you, oldest first")
    cmd.add_parser("show", help="a request, with its questions, proposal, report or stories").add_argument("id")
    answer = cmd.add_parser("answer", help="answer a plan's questions with a JSON file")
    answer.add_argument("id")
    answer.add_argument("file", type=Path)
    cmd.add_parser("approve").add_argument("id")
    reject = cmd.add_parser("reject")
    reject.add_argument("id")
    reject.add_argument("reason")
    args = parser.parse_args(argv)

    nodes = [n(args.project) for n in NODES]
    try:
        if args.cmd == "submit":
            request = json.loads(args.file.read_text())
            node = next((n for n in nodes if request.get("type") in n.types), None)
            if not node:
                raise ValueError(f"no node accepts type {request.get('type')!r}")
            print(node.submit(request))
        elif args.cmd == "run":
            next(n for n in nodes if n.name == args.node).run()
        elif args.cmd == "status":
            print("\n".join(n.status() for n in nodes))
        elif args.cmd == "pending":
            rows = sorted((n.belt.file(s, rid).stat().st_mtime, n.name, s, rid)
                          for n in nodes for s in PENDING for rid in n.belt.ids(s))
            for since, node, state, rid in rows:
                hours = (time.time() - since) / 3600
                print(f"{hours:6.1f}h  {node:7} {'answers' if state == 'waiting' else 'approval':8}  {rid}")
            if not rows:
                print("nothing waits for you")
        else:
            node = next((n for n in nodes if n.belt.state_of(args.id)), None)
            if not node:
                raise ValueError(f"no request {args.id}")
            if args.cmd == "show":
                print(node.show(args.id))
            elif args.cmd == "answer":
                if not hasattr(node, "answer"):
                    raise ValueError(f"{node.name} asks no questions")
                print(node.answer(args.id, json.loads(args.file.read_text())))
            elif args.cmd == "approve":
                print(node.approve(args.id))
            elif args.cmd == "reject":
                node.reject(args.id, args.reason)
        return 0
    except (ValueError, KeyError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
