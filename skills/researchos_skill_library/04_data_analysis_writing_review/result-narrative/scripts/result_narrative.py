from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research-agent-runtime" / "scripts"))
from lab_agent_features import parse_scientific_data, result_narrative  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ResultNarrativeSkill")
    parser.add_argument("--data-summary", default="")
    parser.add_argument("--parsed-table-json", default="")
    parser.add_argument("--csv-text", default="")
    parser.add_argument("--experiment-type", default="")
    parser.add_argument("--research-field", default="")
    parser.add_argument("--statistical-method", default="")
    parser.add_argument("--target-style", choices=["thesis", "journal", "presentation"], default="journal")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    args = parser.parse_args()
    parsed = {}
    if args.parsed_table_json:
        path = Path(args.parsed_table_json)
        parsed = json.loads(path.read_text(encoding="utf-8")) if path.exists() else json.loads(args.parsed_table_json)
    elif args.csv_text:
        parsed = parse_scientific_data({"csv_text": args.csv_text, "file_name": "pasted.csv"})
    result = result_narrative(vars(args) | {"parsed_table": parsed})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
