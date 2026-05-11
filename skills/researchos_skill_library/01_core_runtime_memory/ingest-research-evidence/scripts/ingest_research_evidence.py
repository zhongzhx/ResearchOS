from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def open_kb(kb_root: Path) -> sqlite3.Connection:
    kb_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(kb_root / "research_kb.sqlite")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS research_evidence (
            evidence_id TEXT PRIMARY KEY,
            project_name TEXT,
            source_kind TEXT,
            title TEXT,
            source_path TEXT,
            content_text TEXT,
            content_json TEXT,
            tags_json TEXT,
            credibility TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_decisions (
            decision_id TEXT PRIMARY KEY,
            project_name TEXT,
            decision_type TEXT,
            title TEXT,
            decision_text TEXT,
            linked_evidence_json TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def read_source_file(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return text, json.dumps(data, ensure_ascii=False)
    if suffix == ".csv":
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append({clean(k): clean(v) for k, v in row.items()})
        text_parts = []
        for row in rows[:200]:
            text_parts.append("; ".join(f"{k}: {v}" for k, v in row.items() if v))
        return "\n".join(text_parts), json.dumps(rows, ensure_ascii=False)
    text = path.read_text(encoding="utf-8", errors="replace")
    return text, ""


def split_tags(values: list[str] | None) -> list[str]:
    tags: list[str] = []
    for value in values or []:
        for item in value.split(","):
            item = clean(item)
            if item and item not in tags:
                tags.append(item)
    return tags


def insert_evidence(
    conn: sqlite3.Connection,
    project_name: str,
    source_kind: str,
    title: str,
    source_path: str,
    content_text: str,
    content_json: str,
    tags: list[str],
    credibility: str,
) -> str:
    content_hash = hashlib.sha1((content_text + content_json).encode("utf-8")).hexdigest()[:16]
    evidence_id = stable_id(project_name, source_kind, title or source_path, content_hash)
    timestamp = now()
    conn.execute(
        """
        INSERT INTO research_evidence(
            evidence_id, project_name, source_kind, title, source_path, content_text,
            content_json, tags_json, credibility, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(evidence_id) DO UPDATE SET
            source_kind=excluded.source_kind,
            title=excluded.title,
            source_path=excluded.source_path,
            content_text=excluded.content_text,
            content_json=excluded.content_json,
            tags_json=excluded.tags_json,
            credibility=excluded.credibility,
            updated_at=excluded.updated_at
        """,
        (
            evidence_id,
            project_name,
            source_kind,
            title,
            source_path,
            content_text,
            content_json,
            json.dumps(tags, ensure_ascii=False),
            credibility,
            timestamp,
            timestamp,
        ),
    )
    return evidence_id


def insert_decision(conn: sqlite3.Connection, project_name: str, title: str, decision_text: str, linked_ids: list[str]) -> str:
    decision_id = stable_id(project_name, title, decision_text, now())
    conn.execute(
        """
        INSERT INTO research_decisions(
            decision_id, project_name, decision_type, title, decision_text, linked_evidence_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            project_name,
            "ingested_decision",
            title,
            decision_text,
            json.dumps(linked_ids, ensure_ascii=False),
            now(),
        ),
    )
    return decision_id


def export_evidence(conn: sqlite3.Connection, kb_root: Path) -> None:
    export_dir = kb_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    rows = conn.execute("SELECT * FROM research_evidence ORDER BY updated_at DESC").fetchall()
    with (export_dir / "research_evidence.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [desc[0] for desc in conn.execute("SELECT * FROM research_evidence LIMIT 1").description]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest project evidence into a research KB.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--source-file", action="append", default=None)
    parser.add_argument("--source-text", default="")
    parser.add_argument("--source-kind", default="project_note")
    parser.add_argument("--title", default="")
    parser.add_argument("--tag", action="append", default=None)
    parser.add_argument("--credibility", default="user_provided")
    parser.add_argument("--decision-note", default="")
    args = parser.parse_args()

    kb_root = Path(args.kb_root)
    conn = open_kb(kb_root)
    tags = split_tags(args.tag)
    evidence_ids: list[str] = []

    for source in args.source_file or []:
        path = Path(source)
        content_text, content_json = read_source_file(path)
        title = clean(args.title) or path.stem
        evidence_ids.append(
            insert_evidence(
                conn,
                clean(args.project_name),
                clean(args.source_kind),
                title,
                str(path.resolve()),
                content_text,
                content_json,
                tags,
                clean(args.credibility),
            )
        )

    if clean(args.source_text):
        title = clean(args.title) or f"{args.source_kind} {now()}"
        evidence_ids.append(
            insert_evidence(
                conn,
                clean(args.project_name),
                clean(args.source_kind),
                title,
                "",
                clean(args.source_text),
                "",
                tags,
                clean(args.credibility),
            )
        )

    decision_id = ""
    if clean(args.decision_note):
        decision_id = insert_decision(conn, clean(args.project_name), clean(args.title) or "Ingested decision", clean(args.decision_note), evidence_ids)

    conn.commit()
    export_evidence(conn, kb_root)
    conn.close()
    print(json.dumps({"ingested_evidence": evidence_ids, "decision_id": decision_id, "kb_root": str(kb_root)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
