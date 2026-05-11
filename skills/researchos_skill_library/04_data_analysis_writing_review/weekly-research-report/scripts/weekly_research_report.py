from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS weekly_reports (
            report_id TEXT PRIMARY KEY,
            project_name TEXT,
            week_start TEXT,
            week_end TEXT,
            report_text TEXT,
            report_json TEXT,
            created_at TEXT NOT NULL
        );

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
        """
    )
    conn.commit()


def open_kb(kb_root: Path) -> sqlite3.Connection:
    kb_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(kb_root / "research_kb.sqlite")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def pick_week(start: str, end: str) -> tuple[str, str]:
    if start and end:
        return start, end
    today = date.today()
    week_start = today - timedelta(days=6)
    return week_start.isoformat(), today.isoformat()


def collect(conn: sqlite3.Connection, project_name: str, week_start: str, week_end: str) -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {}
    if table_exists(conn, "research_evidence"):
        data["evidence"] = rows(
            conn,
            """
            SELECT source_kind, title, source_path, substr(content_text, 1, 500) AS content_text, updated_at
            FROM research_evidence
            WHERE project_name=? AND date(updated_at) BETWEEN date(?) AND date(?)
            ORDER BY updated_at DESC
            LIMIT 40
            """,
            (project_name, week_start, week_end),
        )
    if table_exists(conn, "articles"):
        data["articles"] = rows(conn, "SELECT title, doi, journal, publication_date FROM articles ORDER BY updated_at DESC LIMIT 20", ())
    if table_exists(conn, "domain_entities"):
        data["entities"] = rows(
            conn,
            "SELECT field, entity_type, entity_text, confidence FROM domain_entities WHERE project_name=? ORDER BY created_at DESC LIMIT 30",
            (project_name,),
        )
    if table_exists(conn, "experiment_designs"):
        data["designs"] = rows(conn, "SELECT objective, field, created_at FROM experiment_designs WHERE project_name=? ORDER BY created_at DESC LIMIT 10", (project_name,))
    if table_exists(conn, "experiment_results"):
        data["results"] = rows(conn, "SELECT result_file, next_action, created_at FROM experiment_results WHERE project_name=? ORDER BY created_at DESC LIMIT 10", (project_name,))
    if table_exists(conn, "bottleneck_diagnoses"):
        data["diagnoses"] = rows(conn, "SELECT problem, priority_actions_json, created_at FROM bottleneck_diagnoses WHERE project_name=? ORDER BY created_at DESC LIMIT 10", (project_name,))
    if table_exists(conn, "research_decisions"):
        data["decisions"] = rows(conn, "SELECT decision_type, title, decision_text, created_at FROM research_decisions WHERE project_name=? ORDER BY created_at DESC LIMIT 20", (project_name,))
    if table_exists(conn, "browser_learning_pages"):
        data["browser_learning"] = rows(conn, "SELECT title, url, source_site, status, ingested_at FROM browser_learning_pages ORDER BY ingested_at DESC LIMIT 20", ())
    return data


def bullet_or_empty(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- No new record found."]


def build_report(project_name: str, week_start: str, week_end: str, data: dict[str, list[dict[str, Any]]]) -> tuple[str, dict[str, Any]]:
    evidence = data.get("evidence", [])
    designs = data.get("designs", [])
    results = data.get("results", [])
    diagnoses = data.get("diagnoses", [])
    decisions = data.get("decisions", [])
    entities = data.get("entities", [])
    articles = data.get("articles", [])
    browser_learning = data.get("browser_learning", [])

    summary = f"This week, project '{project_name}' added {len(evidence)} evidence records, {len(designs)} experiment designs, {len(results)} result analyses, and {len(decisions)} decisions."
    literature_items = [f"{row.get('title') or '(untitled)'} {row.get('doi') or ''}".strip() for row in articles[:8]]
    evidence_items = [f"{row.get('source_kind')}: {row.get('title') or row.get('content_text') or '(untitled)'}" for row in evidence[:10]]
    design_items = [f"{row.get('field')}: {row.get('objective')}" for row in designs[:8]]
    result_items = [f"{Path(row.get('result_file') or '').name}: next action {row.get('next_action')}" for row in results[:8]]
    entity_items = [f"{row.get('field')}/{row.get('entity_type')}: {row.get('entity_text')}" for row in entities[:12]]
    diagnosis_items = [f"{row.get('problem')}: {row.get('priority_actions_json')}" for row in diagnoses[:5]]
    decision_items = [f"{row.get('title')}: {row.get('decision_text')}" for row in decisions[:8]]
    browser_items = [f"{row.get('source_site')}: {row.get('title') or row.get('url')}" for row in browser_learning[:8]]

    next_plan = []
    if diagnoses:
        next_plan.append("Validate the top bottleneck diagnosis before broad redesign.")
    if results:
        next_plan.append("Run the next action recommended by the latest result analysis.")
    if not evidence:
        next_plan.append("Ingest this week's notes, results, and advisor feedback into the KB.")
    if not next_plan:
        next_plan.append("Continue literature reading, entity extraction, and one small validation task.")

    report_json = {
        "project_name": project_name,
        "week_start": week_start,
        "week_end": week_end,
        "summary": summary,
        "literature_progress": literature_items,
        "knowledge_base_additions": evidence_items,
        "browser_learning": browser_items,
        "experiment_progress": design_items + result_items,
        "entities": entity_items,
        "bottlenecks": diagnosis_items,
        "decisions": decision_items,
        "questions_for_advisor": [
            "Is the current route narrow enough for the next validation cycle?",
            "Which result or bottleneck should be prioritized next week?",
        ],
        "next_week_plan": next_plan,
    }

    lines = [
        "# Weekly Research Report",
        "",
        f"Project: {project_name}",
        f"Period: {week_start} to {week_end}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Literature Progress",
        "",
        *bullet_or_empty(literature_items),
        "",
        "## Knowledge Base Additions",
        "",
        *bullet_or_empty(evidence_items),
        "",
        "## Browser Learning",
        "",
        *bullet_or_empty(browser_items),
        "",
        "## Experiment, Design, and Result Progress",
        "",
        *bullet_or_empty(design_items + result_items),
        "",
        "## Domain Entities Added",
        "",
        *bullet_or_empty(entity_items),
        "",
        "## Bottlenecks and Risks",
        "",
        *bullet_or_empty(diagnosis_items),
        "",
        "## Decisions Made",
        "",
        *bullet_or_empty(decision_items),
        "",
        "## Questions for Advisor",
        "",
        *bullet_or_empty(report_json["questions_for_advisor"]),
        "",
        "## Next Week Plan",
        "",
        *bullet_or_empty(next_plan),
    ]
    return "\n".join(lines), report_json


def write_outputs(output_root: Path, report_text: str, report_json: dict[str, Any]) -> Path:
    run_dir = output_root / f"weekly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "weekly_report.md").write_text(report_text, encoding="utf-8")
    (run_dir / "weekly_report.json").write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an advisor-ready weekly research report from the project KB.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--week-start", default="")
    parser.add_argument("--week-end", default="")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    week_start, week_end = pick_week(args.week_start, args.week_end)
    kb_root = Path(args.kb_root)
    conn = open_kb(kb_root)
    data = collect(conn, clean(args.project_name), week_start, week_end)
    report_text, report_json = build_report(clean(args.project_name), week_start, week_end, data)
    run_dir = write_outputs(Path(args.output_root), report_text, report_json)
    report_id = stable_id(args.project_name, week_start, week_end, now())
    conn.execute(
        "INSERT INTO weekly_reports(report_id, project_name, week_start, week_end, report_text, report_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (report_id, clean(args.project_name), week_start, week_end, report_text, json.dumps(report_json, ensure_ascii=False), now()),
    )
    evidence_id = stable_id(args.project_name, "weekly_report", report_id)
    conn.execute(
        """
        INSERT OR REPLACE INTO research_evidence(
            evidence_id, project_name, source_kind, title, source_path, content_text, content_json,
            tags_json, credibility, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            clean(args.project_name),
            "weekly_report",
            f"Weekly report {week_start} to {week_end}",
            str(run_dir),
            report_text,
            json.dumps(report_json, ensure_ascii=False),
            json.dumps(["weekly_report"], ensure_ascii=False),
            "agent_generated_report",
            now(),
            now(),
        ),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"report_id": report_id, "run_dir": str(run_dir)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
