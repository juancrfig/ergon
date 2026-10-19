"""ergon <node|profile> <command>. The project is the current folder unless --project is given."""
import argparse
import json
import sys
from pathlib import Path

from ergon import gate
from ergon.intake import Intake


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ergon")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="project folder (holds wiki/)")
    groups = parser.add_subparsers(dest="group", required=True)

    intake = groups.add_parser("intake", help="the Intake node").add_subparsers(dest="cmd", required=True)
    intake.add_parser("submit", help="check a request file and put it in the inbox").add_argument("file", type=Path)
    intake.add_parser("run", help="process the inbox (stops while too many proposals wait)")
    intake.add_parser("status", help="count requests per state")
    for name in ("show", "approve"):
        intake.add_parser(name).add_argument("id")
    rej = intake.add_parser("reject")
    rej.add_argument("id")
    rej.add_argument("reason")

    profile = groups.add_parser("profile", help="node agent profiles").add_subparsers(dest="cmd", required=True)
    for name in ("install", "check"):
        profile.add_parser(name).add_argument("name")

    args = parser.parse_args(argv)
    try:
        if args.group == "profile":
            if args.cmd == "install":
                gate.install(args.name)
                print(f"{args.name}: installed and matches the ergon repo")
            else:
                problems = gate.drift(args.name)
                print("\n\n".join(problems) if problems else f"{args.name}: matches the ergon repo")
                return 1 if problems else 0
            return 0
        node = Intake(args.project)
        if args.cmd == "submit":
            print(node.submit(json.loads(args.file.read_text())))
        elif args.cmd == "run":
            node.run()
        elif args.cmd == "status":
            print(node.status())
        elif args.cmd == "show":
            print(node.show(args.id))
        elif args.cmd == "approve":
            print(node.approve(args.id))
        elif args.cmd == "reject":
            node.reject(args.id, args.reason)
        return 0
    except (ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
