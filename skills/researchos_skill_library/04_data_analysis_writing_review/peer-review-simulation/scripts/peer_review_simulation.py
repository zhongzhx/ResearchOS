from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research-agent-runtime" / "scripts"))
from lab_agent_features import peer_review_simulation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="PeerReviewSimulationSkill")
    parser.add_argument("--manuscript-text", default="")
    parser.add_argument("--input-file", default="")
    parser.add_argument("--target-journal", default="")
    parser.add_argument("--research-field", default="")
    parser.add_argument("--review-mode", choices=["mechanism", "statistics", "novelty", "methods", "hostile_reviewer", "general"], default="general")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    args = parser.parse_args()
    text = args.manuscript_text
    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8", errors="replace")
    result = peer_review_simulation(vars(args) | {"manuscript_text": text})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
