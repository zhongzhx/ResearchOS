from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "backend" / "research_agent_runtime" / "scripts"))
from lab_agent_features import generate_sop  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SOPGenerationSkill")
    parser.add_argument("--experiment-goal", required=True)
    parser.add_argument("--protocol-json", default="")
    parser.add_argument("--lab-constraint", action="append", default=None)
    parser.add_argument("--available-equipment", action="append", default=None)
    parser.add_argument("--safety-level", default="")
    parser.add_argument("--target-format", choices=["word", "markdown", "json"], default="json")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    args = parser.parse_args()
    protocol = {}
    if args.protocol_json:
        path = Path(args.protocol_json)
        protocol = json.loads(path.read_text(encoding="utf-8")) if path.exists() else json.loads(args.protocol_json)
    result = generate_sop(
        {
            "experiment_goal": args.experiment_goal,
            "protocol_json": protocol,
            "lab_constraints": args.lab_constraint or [],
            "available_equipment": args.available_equipment or [],
            "safety_level": args.safety_level,
            "target_format": args.target_format,
            "language": args.language,
        }
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
