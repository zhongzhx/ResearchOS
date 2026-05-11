from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_common import write_feedback


def main() -> int:
    parser = argparse.ArgumentParser(description="Record user feedback for a research article or query result.")
    parser.add_argument("--agent-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--article-id", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--relevance", choices=["relevant", "not_relevant", "uncertain", "favorite"], default="uncertain")
    parser.add_argument("--notes", default="")
    parser.add_argument("--tag", action="append", default=[])
    args = parser.parse_args()

    row = write_feedback(
        Path(args.agent_root),
        {
            "project_name": args.project_name,
            "article_id": args.article_id,
            "doi": args.doi,
            "title": args.title,
            "relevance": args.relevance,
            "notes": args.notes,
            "tags": args.tag,
        },
    )
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
