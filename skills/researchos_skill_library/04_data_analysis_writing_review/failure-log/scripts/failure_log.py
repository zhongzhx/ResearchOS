from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research-agent-runtime" / "scripts"))
from lab_agent_features import create_failure_record, delete_failure_record, match_failure_records, search_failure_records, update_failure_record  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="FailureLogSkill")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["create", "edit"]:
        p = sub.add_parser(name)
        p.add_argument("--agent-root", required=True)
        p.add_argument("--id", default="")
        p.add_argument("--title", default="")
        p.add_argument("--project", default="")
        p.add_argument("--research-field", default="")
        p.add_argument("--experiment-type", default="")
        p.add_argument("--observed-failure", default="")
        p.add_argument("--protocol-summary", default="")
        p.add_argument("--confirmed-cause", default="")
        p.add_argument("--solution-attempted", default="")
        p.add_argument("--tag", action="append", default=None)
    p = sub.add_parser("delete")
    p.add_argument("--agent-root", required=True)
    p.add_argument("--id", required=True)
    p = sub.add_parser("search")
    p.add_argument("--agent-root", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--project", default="")
    p = sub.add_parser("match")
    p.add_argument("--agent-root", required=True)
    p.add_argument("--project", default="")
    p.add_argument("--experimental-plan", required=True)
    args = parser.parse_args()
    root = Path(args.agent_root)
    if args.command == "create":
        result = create_failure_record(root, vars(args) | {"tags": args.tag or []})
    elif args.command == "edit":
        if not args.id:
            raise SystemExit("--id is required for edit")
        result = update_failure_record(root, args.id, vars(args) | {"tags": args.tag or []})
    elif args.command == "delete":
        result = delete_failure_record(root, args.id)
    elif args.command == "search":
        result = {"failure_records": search_failure_records(root, query=args.query, project=args.project)}
    else:
        result = match_failure_records(root, {"project": args.project, "experimental_plan": args.experimental_plan})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
