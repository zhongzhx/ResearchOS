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


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS bottleneck_diagnoses (
            diagnosis_id TEXT PRIMARY KEY,
            project_name TEXT,
            problem TEXT,
            evidence_summary TEXT,
            diagnosis_json TEXT,
            priority_actions_json TEXT,
            created_at TEXT NOT NULL
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


def open_kb(kb_root: Path) -> sqlite3.Connection:
    kb_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(kb_root / "research_kb.sqlite")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".csv":
        rows = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(" ".join(clean(v) for v in row.values() if v))
        return "\n".join(rows)
    if path.suffix.lower() == ".json":
        return json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False)
    return path.read_text(encoding="utf-8", errors="replace")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def collect_kb_text(conn: sqlite3.Connection, project_name: str, limit: int = 120) -> str:
    parts: list[str] = []
    if table_exists(conn, "research_evidence"):
        for row in conn.execute(
            "SELECT source_kind, title, content_text FROM research_evidence WHERE project_name=? ORDER BY updated_at DESC LIMIT ?",
            (project_name, limit),
        ).fetchall():
            parts.append(f"{row['source_kind']} {row['title']}: {row['content_text'] or ''}")
    if table_exists(conn, "experiment_results"):
        for row in conn.execute("SELECT analysis_json FROM experiment_results WHERE project_name=? ORDER BY created_at DESC LIMIT 20", (project_name,)).fetchall():
            parts.append(row["analysis_json"] or "")
    if table_exists(conn, "articles"):
        for row in conn.execute("SELECT title, abstract FROM articles LIMIT 50").fetchall():
            parts.append(f"{row['title'] or ''}: {row['abstract'] or ''}")
    return "\n".join(parts)[:60000]


def score_causes(problem: str, evidence: str) -> list[dict[str, Any]]:
    text = f"{problem}\n{evidence}".lower()
    cause_defs = [
        (
            "Scope is too broad",
            ["broad", "unclear", "many variables", "scattered", "cannot narrow", "topic"],
            "Search results or experiments do not converge on one variable, outcome, or mechanism.",
            "Write one sentence with object, method, and outcome; remove everything else for one week.",
        ),
        (
            "Missing or weak control design",
            ["control", "baseline", "blank", "positive control", "negative control"],
            "The project cannot distinguish true effect from background or baseline behavior.",
            "Add baseline, blank/negative, and literature-standard controls before more optimization.",
        ),
        (
            "Metric does not match the hypothesis",
            ["metric", "indicator", "endpoint", "readout", "evaluation", "accuracy", "yield", "efficiency"],
            "The measured result may not validate the real research question.",
            "Define one primary metric and one secondary metric; stop treating every measurement as equal.",
        ),
        (
            "Data or sample quality is limiting signal",
            ["noise", "missing", "small sample", "batch", "contamination", "unstable", "low quality", "variance"],
            "Low-quality input may hide the effect even if the hypothesis is plausible.",
            "Run a small quality check before changing the whole method.",
        ),
        (
            "Method route is over-ambitious",
            ["complex", "failed", "plateau", "not improve", "low yield", "no effect", "time"],
            "The current route may require more time, data, equipment, or optimization than the project allows.",
            "Split the route into a thesis-safe route and an ambitious extension.",
        ),
        (
            "Novelty is not yet proven",
            ["novel", "gap", "similar", "already", "review", "literature"],
            "The work may be feasible but not sufficiently differentiated from recent studies.",
            "Build a 30-paper comparison matrix and mark the exact gap before running more experiments.",
        ),
        (
            "Compliance or safety checkpoint is unresolved",
            ["clinical", "patient", "human subject", "animal", "hazardous", "restricted", "ethics", "approval"],
            "The route may require approval, safety review, or restricted-data handling before execution.",
            "Pause execution and confirm institutional approval and safety requirements.",
        ),
    ]
    ranked = []
    for name, keywords, signal, action in cause_defs:
        score = sum(1 for keyword in keywords if keyword in text)
        if score == 0 and name in {"Scope is too broad", "Novelty is not yet proven"}:
            score = 1
        ranked.append(
            {
                "cause": name,
                "priority_score": score,
                "evidence_signal": signal,
                "quick_validation": action,
                "low_risk_fix": action,
                "medium_risk_fix": "Run a small pilot after the validation check confirms this cause.",
                "ambitious_fix": "Redesign the research route only after the low-risk check fails.",
                "decision_checkpoint": "Next advisor meeting or after one pilot cycle.",
            }
        )
    return sorted(ranked, key=lambda item: item["priority_score"], reverse=True)


def summarize_evidence(evidence: str) -> str:
    if not evidence.strip():
        return "No project KB evidence found. Diagnosis is based on the stated problem and any supplied files."
    lines = [clean(line) for line in evidence.splitlines() if clean(line)]
    return " ".join(lines[:8])[:1500]


def markdown(problem: str, diagnosis: list[dict[str, Any]], evidence_summary: str) -> str:
    lines = ["# Research Bottleneck Diagnosis", "", f"Problem: {problem}", "", "## Evidence Used", "", evidence_summary, "", "## Ranked Causes", ""]
    for index, item in enumerate(diagnosis, 1):
        lines.extend(
            [
                f"### {index}. {item['cause']}",
                f"- Priority score: {item['priority_score']}",
                f"- Evidence signal: {item['evidence_signal']}",
                f"- Quick validation: {item['quick_validation']}",
                f"- Low-risk fix: {item['low_risk_fix']}",
                f"- Medium-risk fix: {item['medium_risk_fix']}",
                f"- Ambitious fix: {item['ambitious_fix']}",
                f"- Decision checkpoint: {item['decision_checkpoint']}",
                "",
            ]
        )
    lines.extend(["## Next 7 Days", "", "- Validate the top 1-2 causes only.", "- Add missing controls or metrics before large redesign.", "- Prepare an advisor summary with evidence, not just conclusions."])
    return "\n".join(lines)


def write_outputs(output_root: Path, problem: str, diagnosis: list[dict[str, Any]], evidence_summary: str) -> Path:
    run_dir = output_root / f"bottleneck_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    payload = {"problem": problem, "evidence_summary": evidence_summary, "diagnosis": diagnosis, "created_at": now()}
    (run_dir / "bottleneck_diagnosis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "bottleneck_diagnosis.md").write_text(markdown(problem, diagnosis, evidence_summary), encoding="utf-8")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose a stalled research project from KB evidence and experiment records.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--experiment-file", action="append", default=None)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    kb_root = Path(args.kb_root)
    conn = open_kb(kb_root)
    evidence = collect_kb_text(conn, clean(args.project_name))
    for value in args.experiment_file or []:
        evidence += "\n" + read_file(Path(value))
    diagnosis = score_causes(args.problem, evidence)
    evidence_summary = summarize_evidence(evidence)
    run_dir = write_outputs(Path(args.output_root), args.problem, diagnosis, evidence_summary)
    diagnosis_id = stable_id(args.project_name, args.problem, now())
    priority_actions = [item["quick_validation"] for item in diagnosis[:3]]
    conn.execute(
        """
        INSERT INTO bottleneck_diagnoses(
            diagnosis_id, project_name, problem, evidence_summary, diagnosis_json, priority_actions_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            diagnosis_id,
            clean(args.project_name),
            clean(args.problem),
            evidence_summary,
            json.dumps(diagnosis, ensure_ascii=False),
            json.dumps(priority_actions, ensure_ascii=False),
            now(),
        ),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"diagnosis_id": diagnosis_id, "run_dir": str(run_dir), "top_cause": diagnosis[0]["cause"] if diagnosis else ""}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
