from __future__ import annotations

import argparse
import json

from .db import init_database
from .workflow import ScenarioWorkflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Qunar hotel refund Mock backend")
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init-db", help="Create and seed the SQLite database")
    init_parser.add_argument("--reset", action="store_true")
    run_parser = sub.add_parser("run-scenario", help="Execute one A-L workflow")
    run_parser.add_argument("scenario", choices=list("ABCDEFGHIJKL"))
    run_parser.add_argument("--reset", action="store_true")
    run_all = sub.add_parser("run-all", help="Execute all A-L workflows")
    run_all.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.command == "init-db":
        print(init_database(reset=args.reset))
        return
    if args.reset:
        init_database(reset=True)
    workflow = ScenarioWorkflow()
    if args.command == "run-scenario":
        print(json.dumps(workflow.run(args.scenario).as_dict(), ensure_ascii=False, indent=2))
    else:
        output = [workflow.run(scenario).as_dict() for scenario in "ABCDEFGHIJKL"]
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
