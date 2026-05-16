from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab_agent_features import ingest_downloaded_pdfs_to_rag


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunk downloaded PDFs into the local ResearchOS RAG store.")
    parser.add_argument("--agent-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--pdf-dir", default="", help="Folder containing downloaded PDFs. Defaults to the whole agent root.")
    parser.add_argument("--source-type", default="paper")
    parser.add_argument("--max-files", type=int, default=200)
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--force", action="store_true", help="Rebuild chunks even if the same PDF path is already ingested.")
    args = parser.parse_args()

    payload = {
        "project_name": args.project_name,
        "source_type": args.source_type,
        "max_files": args.max_files,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "recursive": not args.no_recursive,
        "force": args.force,
    }
    if args.pdf_dir:
        payload["pdf_dir"] = args.pdf_dir

    result = ingest_downloaded_pdfs_to_rag(Path(args.agent_root).resolve(), payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
