from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research-agent-runtime" / "scripts"))
from lab_agent_features import parse_scientific_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV and Excel Scientific Data Parser")
    parser.add_argument("--file-path", default="")
    parser.add_argument("--csv-text", default="")
    parser.add_argument("--file-name", default="")
    args = parser.parse_args()
    result = parse_scientific_data({"file_path": args.file_path, "csv_text": args.csv_text, "file_name": args.file_name})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
