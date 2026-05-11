from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_")
    return text[:80] or "project"


def stable_id(*parts: str) -> str:
    joined = "|".join(str(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def script_path(skill: str, script_name: str) -> Path:
    path = workspace_root() / skill / "scripts" / script_name
    if not path.exists():
        raise FileNotFoundError(f"Required script not found: {path}")
    return path


def state_db(agent_root: Path) -> Path:
    agent_root.mkdir(parents=True, exist_ok=True)
    return agent_root / "runtime_state.sqlite"


def open_state(agent_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(state_db(agent_root), timeout=30)
    conn.row_factory = sqlite3.Row
    ensure_state_schema(conn)
    return conn


def ensure_state_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            query TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            agent_root TEXT NOT NULL,
            job_root TEXT NOT NULL,
            kb_root TEXT NOT NULL,
            run_root TEXT,
            max_results INTEGER,
            source TEXT,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS job_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            level TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL,
            data_json TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            article_id TEXT,
            doi TEXT,
            title TEXT,
            relevance TEXT,
            notes TEXT,
            tags_json TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def create_or_update_job(
    agent_root: Path,
    job_id: str,
    project_name: str,
    query: str,
    status: str,
    job_root: Path,
    kb_root: Path,
    max_results: int,
    source: str,
    run_root: Path | None = None,
    error: str = "",
) -> None:
    conn = open_state(agent_root)
    timestamp = now()
    existing = conn.execute("SELECT job_id FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE jobs SET
                status=?, updated_at=?, run_root=COALESCE(?, run_root), error=?
            WHERE job_id=?
            """,
            (status, timestamp, str(run_root) if run_root else None, error, job_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO jobs(
                job_id, project_name, query, status, created_at, updated_at,
                agent_root, job_root, kb_root, run_root, max_results, source, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                project_name,
                query,
                status,
                timestamp,
                timestamp,
                str(agent_root),
                str(job_root),
                str(kb_root),
                str(run_root) if run_root else "",
                max_results,
                source,
                error,
            ),
        )
    conn.commit()
    conn.close()


def add_event(agent_root: Path, job_id: str, stage: str, message: str, level: str = "info", data: dict[str, Any] | None = None) -> None:
    conn = open_state(agent_root)
    conn.execute(
        """
        INSERT INTO job_events(job_id, created_at, level, stage, message, data_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, now(), level, stage, message, json.dumps(data or {}, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def job_row(agent_root: Path, job_id: str) -> dict[str, Any] | None:
    conn = open_state(agent_root)
    row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def job_events(agent_root: Path, job_id: str) -> list[dict[str, Any]]:
    conn = open_state(agent_root)
    rows = conn.execute("SELECT * FROM job_events WHERE job_id=? ORDER BY event_id", (job_id,)).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["data"] = json.loads(item.pop("data_json") or "{}")
        except json.JSONDecodeError:
            item["data"] = {}
        result.append(item)
    return result


def run_command(agent_root: Path, job_id: str, stage: str, command: list[str], cwd: Path) -> tuple[int, str]:
    add_event(agent_root, job_id, stage, "Starting command", data={"command": command})
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        text = line.rstrip()
        output_lines.append(text)
        if text:
            add_event(agent_root, job_id, stage, text)
    code = process.wait()
    add_event(agent_root, job_id, stage, f"Command finished with exit code {code}", data={"exit_code": code})
    return code, "\n".join(output_lines)


def parse_run_folder(output: str) -> Path | None:
    for line in output.splitlines():
        if line.lower().startswith("run folder:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return Path(value)
    return None


def project_kb_root(agent_root: Path, project_name: str) -> Path:
    return agent_root / "kbs" / slug(project_name)


def article_rows(kb_root: Path, search: str = "", limit: int = 100) -> list[dict[str, Any]]:
    db = kb_root / "research_kb.sqlite"
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    if search:
        pattern = f"%{search}%"
        rows = conn.execute(
            """
            SELECT DISTINCT a.*
            FROM articles a
            LEFT JOIN article_sections s ON s.article_id = a.article_id
            LEFT JOIN terms t ON t.article_id = a.article_id
            WHERE a.title LIKE ? OR a.abstract LIKE ? OR s.section_text LIKE ? OR t.term LIKE ?
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM articles ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def browser_learning_rows(kb_root: Path, search: str = "", limit: int = 100) -> list[dict[str, Any]]:
    db = kb_root / "research_kb.sqlite"
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='browser_learning_pages'").fetchone()
    if not exists:
        conn.close()
        return []
    if search:
        pattern = f"%{search}%"
        rows = conn.execute(
            """
            SELECT *
            FROM browser_learning_pages
            WHERE query LIKE ? OR source_site LIKE ? OR url LIKE ? OR title LIKE ? OR extracted_text LIKE ?
            ORDER BY ingested_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, limit),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM browser_learning_pages ORDER BY ingested_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def article_detail(kb_root: Path, article_id: str) -> dict[str, Any] | None:
    db = kb_root / "research_kb.sqlite"
    if not db.exists():
        return None
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    article = conn.execute("SELECT * FROM articles WHERE article_id=?", (article_id,)).fetchone()
    if not article:
        conn.close()
        return None
    sections = conn.execute("SELECT * FROM article_sections WHERE article_id=?", (article_id,)).fetchall()
    terms = conn.execute("SELECT * FROM terms WHERE article_id=? LIMIT 100", (article_id,)).fetchall()
    snippets = conn.execute("SELECT * FROM evidence_snippets WHERE article_id=? LIMIT 50", (article_id,)).fetchall()
    conn.close()
    return {
        "article": dict(article),
        "sections": [dict(row) for row in sections],
        "terms": [dict(row) for row in terms],
        "evidence_snippets": [dict(row) for row in snippets],
    }


def write_feedback(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_name = payload.get("project_name", "")
    doi = payload.get("doi", "")
    article_id = payload.get("article_id", "")
    title = payload.get("title", "")
    feedback_id = stable_id(project_name, doi, article_id, title, now())
    row = {
        "feedback_id": feedback_id,
        "project_name": project_name,
        "article_id": article_id,
        "doi": doi,
        "title": title,
        "relevance": payload.get("relevance", ""),
        "notes": payload.get("notes", ""),
        "tags_json": json.dumps(payload.get("tags", []), ensure_ascii=False),
        "created_at": now(),
    }
    conn = open_state(agent_root)
    conn.execute(
        """
        INSERT INTO feedback(feedback_id, project_name, article_id, doi, title, relevance, notes, tags_json, created_at)
        VALUES (:feedback_id, :project_name, :article_id, :doi, :title, :relevance, :notes, :tags_json, :created_at)
        """,
        row,
    )
    conn.commit()
    conn.close()

    feedback_csv = agent_root / "feedback.csv"
    exists = feedback_csv.exists()
    with feedback_csv.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    mirror_feedback_to_kb(agent_root, row)
    return row


def mirror_feedback_to_kb(agent_root: Path, row: dict[str, Any]) -> None:
    kb_db = project_kb_root(agent_root, row["project_name"]) / "research_kb.sqlite"
    if not kb_db.exists():
        return
    conn = sqlite3.connect(kb_db)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_feedback (
            feedback_id TEXT PRIMARY KEY,
            article_id TEXT,
            doi TEXT,
            title TEXT,
            relevance TEXT,
            notes TEXT,
            tags_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO article_feedback(
            feedback_id, article_id, doi, title, relevance, notes, tags_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["feedback_id"],
            row.get("article_id", ""),
            row.get("doi", ""),
            row.get("title", ""),
            row.get("relevance", ""),
            row.get("notes", ""),
            row.get("tags_json", "[]"),
            row["created_at"],
        ),
    )
    conn.commit()
    conn.close()
