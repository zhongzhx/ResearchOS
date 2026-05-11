from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
SECTION_NAMES = ("background", "methods", "results", "conclusion")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean_text(value: str | None) -> str:
    value = value or ""
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def safe_key(*parts: str) -> str:
    joined = "|".join(clean_text(part).lower() for part in parts if part)
    if not joined:
        joined = "unknown"
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def open_db(kb_root: Path) -> sqlite3.Connection:
    kb_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(kb_root / "research_kb.sqlite")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            run_root TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            candidate_count INTEGER DEFAULT 0,
            downloaded_count INTEGER DEFAULT 0,
            analyzed_count INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            doi TEXT,
            title TEXT,
            abstract TEXT,
            journal TEXT,
            publication_date TEXT,
            keyword_query TEXT,
            landing_url TEXT,
            download_status TEXT,
            output_path TEXT,
            text_mode TEXT,
            source_run_id TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(project_id),
            FOREIGN KEY(source_run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS article_sections (
            article_id TEXT NOT NULL,
            section_name TEXT NOT NULL,
            section_text TEXT,
            source TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(article_id, section_name),
            FOREIGN KEY(article_id) REFERENCES articles(article_id)
        );

        CREATE TABLE IF NOT EXISTS terms (
            term_id TEXT PRIMARY KEY,
            article_id TEXT NOT NULL,
            term_kind TEXT NOT NULL,
            term TEXT NOT NULL,
            count INTEGER,
            score REAL,
            source TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES articles(article_id)
        );

        CREATE TABLE IF NOT EXISTS evidence_snippets (
            snippet_id TEXT PRIMARY KEY,
            article_id TEXT NOT NULL,
            section_name TEXT NOT NULL,
            snippet TEXT NOT NULL,
            source TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES articles(article_id)
        );

        CREATE TABLE IF NOT EXISTS source_files (
            source_id TEXT PRIMARY KEY,
            run_id TEXT,
            article_id TEXT,
            path TEXT NOT NULL,
            source_type TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id),
            FOREIGN KEY(article_id) REFERENCES articles(article_id)
        );

        CREATE TABLE IF NOT EXISTS query_history (
            query_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            query TEXT NOT NULL,
            run_id TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            count INTEGER NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(project_id),
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS article_feedback (
            feedback_id TEXT PRIMARY KEY,
            article_id TEXT,
            doi TEXT,
            title TEXT,
            relevance TEXT,
            notes TEXT,
            tags_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_articles_project ON articles(project_id);
        CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
        CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
        CREATE INDEX IF NOT EXISTS idx_snippets_article ON evidence_snippets(article_id);
        """
    )
    conn.commit()


def project_id(project_name: str) -> str:
    return safe_key("project", project_name)


def upsert_project(conn: sqlite3.Connection, project_name: str) -> str:
    pid = project_id(project_name)
    timestamp = now()
    conn.execute(
        """
        INSERT INTO projects(project_id, project_name, created_at, updated_at, schema_version)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
            project_name=excluded.project_name,
            updated_at=excluded.updated_at,
            schema_version=excluded.schema_version
        """,
        (pid, project_name, timestamp, timestamp, SCHEMA_VERSION),
    )
    return pid


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def article_id_from(doi: str, title: str) -> str:
    if clean_text(doi):
        return safe_key("doi", doi)
    return safe_key("title", title)


def merge_article_values(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if clean_text(str(value)) and not clean_text(str(merged.get(key, ""))):
            merged[key] = value
        elif key in {"abstract", "output_path", "text_mode", "download_status"} and clean_text(str(value)):
            current = clean_text(str(merged.get(key, "")))
            incoming = clean_text(str(value))
            if len(incoming) > len(current) or key in {"download_status", "output_path", "text_mode"}:
                merged[key] = value
    return merged


def collect_articles(run_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    articles: dict[str, dict[str, Any]] = {}
    terms: dict[str, list[dict[str, Any]]] = {}

    for row in read_csv(run_root / "keyword_candidates.csv"):
        aid = article_id_from(row.get("doi", ""), row.get("title", ""))
        articles[aid] = merge_article_values(
            articles.get(aid, {}),
            {
                "article_id": aid,
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "abstract": row.get("abstract", ""),
                "journal": row.get("journal", ""),
                "publication_date": row.get("publication_date", ""),
                "keyword_query": row.get("query", ""),
                "landing_url": row.get("landing_url", ""),
                "download_status": "candidate",
                "source_file": str(run_root / "keyword_candidates.csv"),
            },
        )

    for row in read_csv(run_root / "access_log.csv"):
        aid = article_id_from(row.get("doi", ""), row.get("title", ""))
        articles[aid] = merge_article_values(
            articles.get(aid, {}),
            {
                "article_id": aid,
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "abstract": row.get("abstract", ""),
                "journal": row.get("journal", ""),
                "publication_date": row.get("publication_date", ""),
                "keyword_query": row.get("keyword_query", ""),
                "download_status": row.get("status", ""),
                "output_path": row.get("output_path", ""),
                "source_file": str(run_root / "access_log.csv"),
            },
        )

    for record_path in sorted((run_root / "article_records").glob("*.json")):
        record = read_json(record_path)
        aid = article_id_from(record.get("doi", ""), record.get("title", ""))
        articles[aid] = merge_article_values(
            articles.get(aid, {}),
            {
                "article_id": aid,
                "doi": record.get("doi", ""),
                "title": record.get("title", ""),
                "abstract": record.get("abstract", ""),
                "journal": record.get("journal", ""),
                "publication_date": record.get("publication_date", ""),
                "keyword_query": record.get("keyword_query", ""),
                "landing_url": record.get("landing_url", ""),
                "download_status": record.get("status", ""),
                "output_path": record.get("output_path", ""),
                "source_file": str(record_path),
            },
        )

    for analysis_path in sorted((run_root / "article_abstracts").glob("article_abstract_*/article_abstract_analysis.json")):
        payload = read_json(analysis_path)
        source = payload.get("source", {})
        result = payload.get("result", {})
        aid = article_id_from(source.get("doi", ""), source.get("title", ""))
        articles[aid] = merge_article_values(
            articles.get(aid, {}),
            {
                "article_id": aid,
                "doi": source.get("doi", ""),
                "title": source.get("title", ""),
                "abstract": source.get("abstract", ""),
                "journal": source.get("journal", ""),
                "publication_date": source.get("publication_date", ""),
                "keyword_query": source.get("keyword_query", ""),
                "output_path": source.get("path", ""),
                "text_mode": payload.get("text_mode", ""),
                "source_file": str(analysis_path),
                "sections": result.get("abstract_summary", {}),
            },
        )
        terms.setdefault(aid, []).extend(terms_from_analysis(result, str(analysis_path)))

    for row in read_csv(run_root / "article_abstracts" / "article_abstracts.csv"):
        aid = article_id_from(row.get("doi", ""), row.get("title", ""))
        articles[aid] = merge_article_values(
            articles.get(aid, {}),
            {
                "article_id": aid,
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "journal": row.get("journal", ""),
                "publication_date": row.get("publication_date", ""),
                "keyword_query": row.get("keyword_query", ""),
                "text_mode": row.get("text_mode", ""),
                "source_file": str(run_root / "article_abstracts" / "article_abstracts.csv"),
                "sections": {
                    "background": row.get("background", ""),
                    "methods": row.get("methods", ""),
                    "results": row.get("results", ""),
                    "conclusion": row.get("conclusion", ""),
                },
            },
        )
        terms.setdefault(aid, []).extend(terms_from_summary_row(row, str(run_root / "article_abstracts" / "article_abstracts.csv")))

    return articles, terms


def split_semicolon(value: str) -> list[str]:
    return [clean_text(part) for part in value.split(";") if clean_text(part)]


def split_queries(value: str) -> list[str]:
    return [clean_text(part) for part in value.split("|") if clean_text(part)]


def terms_from_summary_row(row: dict[str, str], source: str) -> list[dict[str, Any]]:
    items = []
    for term in split_semicolon(row.get("top_keywords", "")):
        items.append({"kind": "keyword", "term": term, "count": None, "score": None, "source": source})
    for phrase in split_semicolon(row.get("top_keyphrases", "")):
        items.append({"kind": "keyphrase", "term": phrase, "count": None, "score": None, "source": source})
    for query in split_queries(row.get("top_search_queries", "")):
        items.append({"kind": "search_query", "term": query, "count": None, "score": None, "source": source})
    return items


def terms_from_analysis(result: dict[str, Any], source: str) -> list[dict[str, Any]]:
    items = []
    for row in result.get("primary_keywords", []):
        items.append({"kind": "keyword", "term": row.get("term", ""), "count": row.get("count"), "score": row.get("score"), "source": source})
    for row in result.get("keyphrases", []):
        items.append({"kind": "keyphrase", "term": row.get("phrase", ""), "count": row.get("count"), "score": row.get("score"), "source": source})
    for query in result.get("search_queries", []):
        items.append({"kind": "search_query", "term": query, "count": None, "score": None, "source": source})
    for term in result.get("include_terms", []):
        items.append({"kind": "include_term", "term": term, "count": None, "score": None, "source": source})
    for term in result.get("exclude_terms", []):
        items.append({"kind": "exclude_term", "term": term, "count": None, "score": None, "source": source})
    return [item for item in items if clean_text(item["term"])]


def upsert_run(conn: sqlite3.Connection, project_id: str, run_root: Path, articles: dict[str, dict[str, Any]]) -> str:
    run_id = safe_key("run", str(run_root.resolve()))
    candidate_count = len(read_csv(run_root / "keyword_candidates.csv"))
    downloaded_count = sum(1 for row in read_csv(run_root / "access_log.csv") if row.get("status") == "downloaded")
    analyzed_count = len(read_csv(run_root / "article_abstracts" / "article_abstracts.csv"))
    conn.execute(
        """
        INSERT INTO runs(run_id, project_id, run_root, ingested_at, candidate_count, downloaded_count, analyzed_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            ingested_at=excluded.ingested_at,
            candidate_count=excluded.candidate_count,
            downloaded_count=excluded.downloaded_count,
            analyzed_count=excluded.analyzed_count
        """,
        (run_id, project_id, str(run_root.resolve()), now(), candidate_count, downloaded_count, analyzed_count),
    )
    return run_id


def upsert_articles(conn: sqlite3.Connection, project_id: str, run_id: str, articles: dict[str, dict[str, Any]]) -> None:
    for article in articles.values():
        conn.execute(
            """
            INSERT INTO articles(
                article_id, project_id, doi, title, abstract, journal, publication_date,
                keyword_query, landing_url, download_status, output_path, text_mode, source_run_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
                doi=COALESCE(NULLIF(excluded.doi, ''), articles.doi),
                title=COALESCE(NULLIF(excluded.title, ''), articles.title),
                abstract=CASE WHEN length(COALESCE(excluded.abstract, '')) > length(COALESCE(articles.abstract, '')) THEN excluded.abstract ELSE articles.abstract END,
                journal=COALESCE(NULLIF(excluded.journal, ''), articles.journal),
                publication_date=COALESCE(NULLIF(excluded.publication_date, ''), articles.publication_date),
                keyword_query=COALESCE(NULLIF(excluded.keyword_query, ''), articles.keyword_query),
                landing_url=COALESCE(NULLIF(excluded.landing_url, ''), articles.landing_url),
                download_status=COALESCE(NULLIF(excluded.download_status, ''), articles.download_status),
                output_path=COALESCE(NULLIF(excluded.output_path, ''), articles.output_path),
                text_mode=COALESCE(NULLIF(excluded.text_mode, ''), articles.text_mode),
                source_run_id=excluded.source_run_id,
                updated_at=excluded.updated_at
            """,
            (
                article["article_id"],
                project_id,
                clean_text(article.get("doi")),
                clean_text(article.get("title")),
                clean_text(article.get("abstract")),
                clean_text(article.get("journal")),
                clean_text(article.get("publication_date")),
                clean_text(article.get("keyword_query")),
                clean_text(article.get("landing_url")),
                clean_text(article.get("download_status")),
                clean_text(article.get("output_path")),
                clean_text(article.get("text_mode")),
                run_id,
                now(),
            ),
        )

        sections = article.get("sections") or {}
        for section_name in SECTION_NAMES:
            text = clean_text(sections.get(section_name, ""))
            if not text:
                continue
            conn.execute(
                """
                INSERT INTO article_sections(article_id, section_name, section_text, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(article_id, section_name) DO UPDATE SET
                    section_text=excluded.section_text,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (article["article_id"], section_name, text, clean_text(article.get("source_file")), now()),
            )
            for snippet in split_sentences(text)[:5]:
                snippet_id = safe_key(article["article_id"], section_name, snippet)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evidence_snippets(snippet_id, article_id, section_name, snippet, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (snippet_id, article["article_id"], section_name, snippet, clean_text(article.get("source_file")), now()),
                )


def upsert_terms(conn: sqlite3.Connection, terms_by_article: dict[str, list[dict[str, Any]]]) -> None:
    for article_id, terms in terms_by_article.items():
        for item in terms:
            term = clean_text(item.get("term"))
            if not term:
                continue
            term_id = safe_key(article_id, item.get("kind", ""), term)
            conn.execute(
                """
                INSERT INTO terms(term_id, article_id, term_kind, term, count, score, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(term_id) DO UPDATE SET
                    count=excluded.count,
                    score=excluded.score,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (term_id, article_id, item.get("kind", ""), term, item.get("count"), item.get("score"), item.get("source", ""), now()),
            )


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", clean_text(text))
    return [part for part in parts if len(part) >= 30]


def upsert_source_files(conn: sqlite3.Connection, run_id: str, articles: dict[str, dict[str, Any]], run_root: Path) -> None:
    paths = [
        (run_root / "keyword_candidates.csv", "candidate_table", None),
        (run_root / "access_log.csv", "access_log", None),
        (run_root / "article_abstracts" / "article_abstracts.csv", "article_abstract_summary", None),
    ]
    for article in articles.values():
        if article.get("source_file"):
            paths.append((Path(article["source_file"]), "article_source", article["article_id"]))
        if article.get("output_path"):
            paths.append((Path(article["output_path"]), "downloaded_file", article["article_id"]))

    for path, source_type, article_id in paths:
        if not clean_text(str(path)):
            continue
        source_id = safe_key(run_id, str(path), source_type, article_id or "")
        conn.execute(
            """
            INSERT OR REPLACE INTO source_files(source_id, run_id, article_id, path, source_type, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, run_id, article_id, str(path), source_type, now()),
        )


def upsert_query_history(conn: sqlite3.Connection, project_id: str, run_id: str, articles: dict[str, dict[str, Any]]) -> None:
    counts = Counter(clean_text(article.get("keyword_query")) for article in articles.values() if clean_text(article.get("keyword_query")))
    for query, count in counts.items():
        query_id = safe_key(project_id, query)
        existing = conn.execute("SELECT count FROM query_history WHERE query_id=?", (query_id,)).fetchone()
        old_count = int(existing["count"]) if existing else 0
        timestamp = now()
        conn.execute(
            """
            INSERT INTO query_history(query_id, project_id, query, run_id, first_seen_at, last_seen_at, count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(query_id) DO UPDATE SET
                run_id=excluded.run_id,
                last_seen_at=excluded.last_seen_at,
                count=excluded.count
            """,
            (query_id, project_id, query, run_id, timestamp, timestamp, old_count + count),
        )


def export_table(conn: sqlite3.Connection, table: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(dict(row) for row in rows)
        else:
            f.write("")


def export_kb(conn: sqlite3.Connection, kb_root: Path) -> None:
    exports = kb_root / "exports"
    for table in ["articles", "article_sections", "terms", "search_queries", "evidence_snippets", "query_history", "article_feedback"]:
        if table == "search_queries":
            path = exports / "search_queries.csv"
            rows = conn.execute("SELECT * FROM terms WHERE term_kind='search_query'").fetchall()
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(dict(row) for row in rows)
                else:
                    f.write("")
        else:
            export_table(conn, table, exports / f"{table}.csv")


def write_summary(conn: sqlite3.Connection, kb_root: Path, project_name: str) -> None:
    article_count = conn.execute("SELECT COUNT(*) AS n FROM articles").fetchone()["n"]
    analyzed_count = conn.execute("SELECT COUNT(DISTINCT article_id) AS n FROM article_sections").fetchone()["n"]
    downloaded_count = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE download_status='downloaded'").fetchone()["n"]
    top_terms = conn.execute(
        """
        SELECT term, term_kind, COUNT(*) AS n
        FROM terms
        WHERE term_kind IN ('keyword', 'keyphrase')
        GROUP BY term, term_kind
        ORDER BY n DESC, term ASC
        LIMIT 25
        """
    ).fetchall()
    queries = conn.execute(
        """
        SELECT query, count
        FROM query_history
        ORDER BY count DESC, last_seen_at DESC
        LIMIT 20
        """
    ).fetchall()

    lines = [
        "# Research Knowledge Base Summary",
        "",
        f"- Project: {project_name}",
        f"- Articles: {article_count}",
        f"- Articles with abstract sections: {analyzed_count}",
        f"- Downloaded articles: {downloaded_count}",
        "",
        "## Query Memory",
        "",
    ]
    lines.extend(f"- {row['query']} ({row['count']})" for row in queries)
    lines.extend(["", "## Recurring Terms", ""])
    lines.extend(f"- {row['term']} [{row['term_kind']}] ({row['n']})" for row in top_terms)
    (kb_root / "knowledge_base_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ingest_run(conn: sqlite3.Connection, project_id: str, run_root: Path) -> tuple[int, int]:
    articles, terms = collect_articles(run_root)
    run_id = upsert_run(conn, project_id, run_root, articles)
    upsert_articles(conn, project_id, run_id, articles)
    upsert_terms(conn, terms)
    upsert_source_files(conn, run_id, articles, run_root)
    upsert_query_history(conn, project_id, run_id, articles)
    conn.commit()
    return len(articles), sum(len(items) for items in terms.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or update a layered user research knowledge base.")
    parser.add_argument("--kb-root", required=True, help="Knowledge base output folder.")
    parser.add_argument("--project-name", required=True, help="User/project name for this KB.")
    parser.add_argument("--run-root", action="append", required=True, help="Search/download run folder to ingest. Repeatable.")
    args = parser.parse_args()

    kb_root = Path(args.kb_root)
    conn = open_db(kb_root)
    pid = upsert_project(conn, args.project_name)

    total_articles = 0
    total_terms = 0
    for run_root_arg in args.run_root:
        run_root = Path(run_root_arg)
        if not run_root.exists():
            print(f"Skipping missing run root: {run_root}")
            continue
        articles, terms = ingest_run(conn, pid, run_root)
        total_articles += articles
        total_terms += terms

    export_kb(conn, kb_root)
    write_summary(conn, kb_root, args.project_name)
    conn.close()

    print(f"KB root: {kb_root}")
    print(f"SQLite DB: {kb_root / 'research_kb.sqlite'}")
    print(f"Articles ingested/updated this run: {total_articles}")
    print(f"Terms ingested/updated this run: {total_terms}")
    print(f"Summary: {kb_root / 'knowledge_base_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
