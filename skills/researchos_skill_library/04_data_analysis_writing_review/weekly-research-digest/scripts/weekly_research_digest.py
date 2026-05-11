from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research-agent-runtime" / "scripts"))
from lab_agent_features import add_research_interest, generate_weekly_digest, list_research_interests  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="WeeklyResearchDigestSkill")
    parser.add_argument("--agent-root", required=True)
    parser.add_argument("--project-name", default="")
    parser.add_argument("--interest", action="append", default=None)
    parser.add_argument("--recent-note", action="append", default=None)
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    parser.add_argument("--add-interest", action="append", default=None)
    args = parser.parse_args()
    agent_root = Path(args.agent_root)
    for keyword in args.add_interest or []:
        add_research_interest(agent_root, {"project_name": args.project_name, "keyword": keyword})
    interests = args.interest or [row["keyword"] for row in list_research_interests(agent_root, args.project_name)]
    result = generate_weekly_digest(
        agent_root,
        {
            "project_name": args.project_name,
            "research_interests": interests,
            "recent_notes": args.recent_note or [],
            "max_items": args.max_items,
            "language": args.language,
        },
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
