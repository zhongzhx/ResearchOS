from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


STOPWORDS = {"what", "which", "where", "when", "who", "does", "with", "from", "that", "this", "have", "used", "using", "the", "and", "are", "for"}


def tokens(question: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9-]{3,}", question) if token.lower() not in STOPWORDS]


def answer(kb_root: Path, question: str, limit: int = 8) -> str:
    db = kb_root / "research_kb.sqlite"
    if not db.exists():
        return f"Knowledge base not found: {db}"
    terms = tokens(question)
    if not terms:
        terms = [question]

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    scored: dict[str, int] = {}
    browser_scored: dict[str, int] = {}
    for term in terms:
        pattern = f"%{term}%"
        rows = conn.execute(
            """
            SELECT DISTINCT a.article_id
            FROM articles a
            LEFT JOIN article_sections s ON s.article_id = a.article_id
            LEFT JOIN terms t ON t.article_id = a.article_id
            LEFT JOIN evidence_snippets e ON e.article_id = a.article_id
            WHERE a.title LIKE ? OR a.abstract LIKE ? OR s.section_text LIKE ? OR t.term LIKE ? OR e.snippet LIKE ?
            """,
            (pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
        for row in rows:
            scored[row["article_id"]] = scored.get(row["article_id"], 0) + 1
        if table_exists(conn, "browser_learning_pages"):
            browser_rows = conn.execute(
                """
                SELECT DISTINCT page_id
                FROM browser_learning_pages
                WHERE query LIKE ? OR source_site LIKE ? OR url LIKE ? OR title LIKE ? OR extracted_text LIKE ?
                """,
                (pattern, pattern, pattern, pattern, pattern),
            ).fetchall()
            for row in browser_rows:
                browser_scored[row["page_id"]] = browser_scored.get(row["page_id"], 0) + 1

    ranked = sorted(scored.items(), key=lambda item: item[1], reverse=True)[:limit]
    ranked_browser = sorted(browser_scored.items(), key=lambda item: item[1], reverse=True)[:limit]
    if not ranked and not ranked_browser:
        conn.close()
        return "No matching evidence found in the knowledge base."

    lines = ["# Knowledge Base Answer", "", f"Question: {question}", ""]
    if ranked:
        lines.extend(["## Article Evidence", ""])
    for index, (article_id, score) in enumerate(ranked, 1):
        article = conn.execute("SELECT * FROM articles WHERE article_id=?", (article_id,)).fetchone()
        sections = conn.execute(
            """
            SELECT section_name, section_text
            FROM article_sections
            WHERE article_id=?
            ORDER BY CASE section_name
                WHEN 'background' THEN 1
                WHEN 'methods' THEN 2
                WHEN 'results' THEN 3
                WHEN 'conclusion' THEN 4
                ELSE 5
            END
            """,
            (article_id,),
        ).fetchall()
        snippets = conn.execute("SELECT section_name, snippet FROM evidence_snippets WHERE article_id=? LIMIT 4", (article_id,)).fetchall()
        lines.append(f"{index}. {article['title'] or '(untitled)'}")
        lines.append(f"   DOI: {article['doi'] or 'not available'}")
        lines.append(f"   Journal/date: {article['journal'] or 'not available'} / {article['publication_date'] or 'not available'}")
        lines.append(f"   Match score: {score}")
        feedback = conn.execute(
            """
            SELECT relevance, notes, tags_json
            FROM article_feedback
            WHERE article_id=? OR (doi IS NOT NULL AND doi != '' AND doi=?)
            ORDER BY created_at DESC
            LIMIT 3
            """,
            (article_id, article["doi"] or ""),
        ).fetchall() if table_exists(conn, "article_feedback") else []
        for item in feedback:
            lines.append(f"   User feedback: {item['relevance'] or 'unrated'} - {item['notes'] or ''}")
        for section in sections:
            text = section["section_text"] or ""
            if text:
                lines.append(f"   {section['section_name']}: {text[:500]}")
        if snippets:
            lines.append("   Evidence snippets:")
            for snippet in snippets:
                lines.append(f"   - [{snippet['section_name']}] {snippet['snippet'][:300]}")
        lines.append("")
    if ranked_browser:
        lines.extend(["## Browser Learning Records", ""])
        for index, (page_id, score) in enumerate(ranked_browser, 1):
            page = conn.execute("SELECT * FROM browser_learning_pages WHERE page_id=?", (page_id,)).fetchone()
            if not page:
                continue
            lines.append(f"{index}. {page['title'] or '(untitled page)'}")
            lines.append(f"   URL: {page['url'] or 'not available'}")
            lines.append(f"   Source site: {page['source_site'] or 'not available'}")
            lines.append(f"   Status: {page['status'] or 'not available'}")
            lines.append(f"   Match score: {score}")
            text = page["extracted_text"] or page["error"] or ""
            if text:
                lines.append(f"   Browser note: {text[:700]}")
            lines.append("")
    conn.close()
    return "\n".join(lines)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Answer a question using a local research KB.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    print(answer(Path(args.kb_root), args.question, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
