from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: str | None) -> str:
    value = value or ""
    return re.sub(r"\s+", " ", value).strip()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS browser_learning_pages (
            page_id TEXT PRIMARY KEY,
            query TEXT,
            source_site TEXT,
            url TEXT,
            title TEXT,
            status TEXT,
            page_kind TEXT,
            extracted_text TEXT,
            error TEXT,
            ingested_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def page_id(url: str, query: str) -> str:
    import hashlib

    return hashlib.sha1(f"{query}|{url}".encode("utf-8")).hexdigest()


def ingest(kb_root: Path, learning_run: Path) -> int:
    db = kb_root / "research_kb.sqlite"
    kb_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    ensure_schema(conn)
    pages_csv = learning_run / "browser_learning_pages.csv"
    if not pages_csv.exists():
        conn.close()
        return 0
    count = 0
    with pages_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            conn.execute(
                """
                INSERT INTO browser_learning_pages(
                    page_id, query, source_site, url, title, status, page_kind, extracted_text, error, ingested_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(page_id) DO UPDATE SET
                    title=excluded.title,
                    status=excluded.status,
                    page_kind=excluded.page_kind,
                    extracted_text=excluded.extracted_text,
                    error=excluded.error,
                    ingested_at=excluded.ingested_at
                """,
                (
                    page_id(row.get("url", ""), row.get("query", "")),
                    clean(row.get("query")),
                    clean(row.get("source_site")),
                    clean(row.get("url")),
                    clean(row.get("title")),
                    clean(row.get("status")),
                    clean(row.get("page_kind")),
                    clean(row.get("extracted_text")),
                    clean(row.get("error")),
                    now(),
                ),
            )
            count += 1
    conn.commit()
    conn.close()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest browser learning records into a research KB.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--learning-run", required=True)
    args = parser.parse_args()
    count = ingest(Path(args.kb_root), Path(args.learning_run))
    print(json.dumps({"ingested_pages": count, "kb_root": args.kb_root}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
