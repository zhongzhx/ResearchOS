from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "backend" / "research_agent_runtime" / "scripts"))
from lab_agent_features import extract_protocol  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ProtocolExtractionSkill")
    parser.add_argument("--paper-text", default="")
    parser.add_argument("--input-file", default="")
    parser.add_argument("--section-hint", choices=["methods", "materials", "results", "supplementary"], default="")
    parser.add_argument("--experiment-type", default="")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    args = parser.parse_args()
    text = args.paper_text
    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8", errors="replace")
    result = extract_protocol({"paper_text": text, "section_hint": args.section_hint, "experiment_type": args.experiment_type, "language": args.language})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
