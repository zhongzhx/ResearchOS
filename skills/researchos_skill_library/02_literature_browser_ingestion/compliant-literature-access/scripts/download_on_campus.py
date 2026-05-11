from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import resolve_fulltext_access


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simplified DOI full-text downloader for current campus IP/VPN access."
    )
    parser.add_argument("--doi", action="append", help="DOI to download. Can be passed more than once.")
    parser.add_argument("--input-csv", help="CSV file containing DOI records.")
    parser.add_argument("--doi-column", default="DOI", help="DOI column name for --input-csv.")
    parser.add_argument("--output-root", required=True, help="Parent folder for the run output.")
    parser.add_argument("--run-name", default="campus_network_download", help="Run folder prefix.")
    parser.add_argument("--email", default="", help="Optional contact email for polite API identification.")
    parser.add_argument(
        "--also-open-access",
        action="store_true",
        help="Also try open-access resolvers. Default focuses on current-network/publisher access.",
    )
    parser.add_argument(
        "--no-crossref",
        action="store_true",
        help="Skip Crossref full-text/TDM link discovery and use only DOI landing pages.",
    )
    parser.add_argument("--keep-trying", action="store_true", help="Try all candidate URLs instead of stopping after success.")
    args = parser.parse_args()

    config = {
        "email": args.email,
        "run_name": args.run_name,
        "access_modes": {
            "open_access": args.also_open_access,
            "crossref_tdm": not args.no_crossref,
            "campus_ip": True,
            "ezproxy": {"enabled": False},
        },
        "request": {
            "timeout_seconds": 45,
            "delay_seconds": 0.5,
            "user_agent": (
                f"CampusNetworkLiteratureDownload/0.1 (mailto:{args.email})"
                if args.email
                else "CampusNetworkLiteratureDownload/0.1"
            ),
        },
        "download": {
            "save_html": True,
            "max_bytes": 104857600,
            "stop_after_first_success": not args.keep_trying,
        },
        "publisher_headers": {},
    }

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
        json.dump(config, f, indent=2)
        config_path = f.name

    forwarded = ["resolve_fulltext_access.py", "--config", config_path, "--output-root", args.output_root]
    if args.doi:
        for doi in args.doi:
            forwarded.extend(["--doi", doi])
    if args.input_csv:
        forwarded.extend(["--input-csv", args.input_csv, "--doi-column", args.doi_column])
    if args.keep_trying:
        forwarded.append("--keep-trying")

    old_argv = sys.argv
    try:
        sys.argv = forwarded
        return resolve_fulltext_access.main()
    finally:
        sys.argv = old_argv
        try:
            Path(config_path).unlink()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
