from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Search a local research knowledge base.")
    parser.add_argument("--kb-root", required=True, help="Knowledge base folder containing research_kb.sqlite.")
    parser.add_argument("--search", required=True, help="Text to search in title, abstract sections, terms, and snippets.")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    db_path = Path(args.kb_root) / "research_kb.sqlite"
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    pattern = f"%{args.search}%"
    rows = conn.execute(
        """
        SELECT DISTINCT
            a.doi,
            a.title,
            a.journal,
            a.publication_date,
            a.keyword_query,
            a.download_status,
            a.output_path
        FROM articles a
        LEFT JOIN article_sections s ON s.article_id = a.article_id
        LEFT JOIN terms t ON t.article_id = a.article_id
        LEFT JOIN evidence_snippets e ON e.article_id = a.article_id
        WHERE
            a.title LIKE ?
            OR a.abstract LIKE ?
            OR s.section_text LIKE ?
            OR t.term LIKE ?
            OR e.snippet LIKE ?
        LIMIT ?
        """,
        (pattern, pattern, pattern, pattern, pattern, args.limit),
    ).fetchall()

    if not rows:
        print("No matching records.")
        return 0

    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['title'] or '(untitled)'}")
        print(f"   DOI: {row['doi'] or 'not available'}")
        print(f"   Journal/date: {row['journal'] or 'not available'} / {row['publication_date'] or 'not available'}")
        print(f"   Query: {row['keyword_query'] or 'not available'}")
        print(f"   Download: {row['download_status'] or 'not available'}")
        if row["output_path"]:
            print(f"   File: {row['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
