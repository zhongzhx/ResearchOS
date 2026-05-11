from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
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
        CREATE TABLE IF NOT EXISTS experiment_results (
            result_id TEXT PRIMARY KEY,
            project_name TEXT,
            result_file TEXT,
            metrics_json TEXT,
            analysis_json TEXT,
            best_condition_json TEXT,
            next_action TEXT,
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


def parse_metric(value: str) -> dict[str, str]:
    if ":" in value:
        name, direction = value.split(":", 1)
    else:
        name, direction = value, "max"
    direction = direction.lower().strip()
    if direction not in {"max", "min"}:
        direction = "max"
    return {"metric": clean(name), "direction": direction}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(f)]


def to_float(value: str) -> float | None:
    try:
        if value == "":
            return None
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except ValueError:
        return None


def infer_metrics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    metrics = []
    for key in rows[0].keys():
        values = [to_float(row.get(key, "")) for row in rows]
        numeric = [value for value in values if value is not None]
        if len(numeric) >= max(2, len(rows) // 2):
            direction = "min" if any(term in key.lower() for term in ["loss", "error", "impurity", "toxicity", "size", "cost"]) else "max"
            metrics.append({"metric": key, "direction": direction})
    return metrics


def normalize(values: list[float], direction: str) -> list[float]:
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return [0.5 for _ in values]
    scores = [(value - min_value) / (max_value - min_value) for value in values]
    if direction == "min":
        scores = [1 - score for score in scores]
    return scores


def analyze(rows: list[dict[str, str]], metrics: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {"ranked_rows": [], "best_row": {}, "failure_signals": ["Result table is empty."], "next_action": "repeat"}
    if not metrics:
        return {"ranked_rows": [], "best_row": rows[0], "failure_signals": ["No numeric metrics found."], "next_action": "redesign"}

    scores = [0.0 for _ in rows]
    metric_notes = []
    failure_signals = []
    for metric in metrics:
        name = metric["metric"]
        numeric_values = [to_float(row.get(name, "")) for row in rows]
        missing = sum(1 for value in numeric_values if value is None)
        if missing:
            failure_signals.append(f"Metric '{name}' has {missing} missing/non-numeric values.")
        present_pairs = [(idx, value) for idx, value in enumerate(numeric_values) if value is not None]
        if not present_pairs:
            continue
        normalized = normalize([value for _, value in present_pairs], metric["direction"])
        for (idx, _), score in zip(present_pairs, normalized):
            scores[idx] += score
        metric_notes.append({"metric": name, "direction": metric["direction"], "missing": missing})

    ranked = sorted(
        [
            {"rank": 0, "score": round(scores[idx], 4), "row_index": idx + 1, "condition": rows[idx]}
            for idx in range(len(rows))
        ],
        key=lambda item: item["score"],
        reverse=True,
    )
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
    best = ranked[0] if ranked else {"condition": rows[0], "score": 0}
    if len(ranked) > 1 and best["score"] - ranked[1]["score"] < 0.1:
        failure_signals.append("Best condition is only marginally better than the next alternative.")
        next_action = "repeat"
    elif failure_signals:
        next_action = "narrow"
    else:
        next_action = "continue"
    return {
        "metrics": metric_notes,
        "ranked_rows": ranked,
        "best_row": best,
        "failure_signals": failure_signals,
        "next_action": next_action,
    }


def markdown(result_file: str, analysis: dict[str, Any]) -> str:
    lines = ["# Experiment Result Analysis", "", f"Result file: {result_file}", "", "## Decision", "", f"Recommended next action: {analysis['next_action']}", ""]
    lines.extend(["## Best Condition", "", json.dumps(analysis.get("best_row", {}), ensure_ascii=False, indent=2), "", "## Top Ranked Conditions", ""])
    for item in analysis.get("ranked_rows", [])[:10]:
        lines.append(f"- Rank {item['rank']}: score {item['score']} row {item['row_index']} {item['condition']}")
    lines.extend(["", "## Failure Signals", ""])
    signals = analysis.get("failure_signals") or ["No major failure signal detected from the provided table."]
    lines.extend(f"- {signal}" for signal in signals)
    lines.extend(["", "## Boundary", "", "This analysis ranks the provided table only. Confirm with replicates and valid controls before claiming success."])
    return "\n".join(lines)


def write_outputs(output_root: Path, result_file: str, analysis: dict[str, Any]) -> Path:
    run_dir = output_root / f"result_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "result_analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "result_analysis.md").write_text(markdown(result_file, analysis), encoding="utf-8")
    with (run_dir / "ranked_results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["rank", "score", "row_index", "condition_json"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in analysis.get("ranked_rows", []):
            writer.writerow({"rank": item["rank"], "score": item["score"], "row_index": item["row_index"], "condition_json": json.dumps(item["condition"], ensure_ascii=False)})
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze an experiment result CSV.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--result-file", required=True)
    parser.add_argument("--metric", action="append", default=None)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    result_path = Path(args.result_file)
    rows = read_rows(result_path)
    metrics = [parse_metric(value) for value in args.metric] if args.metric else infer_metrics(rows)
    analysis = analyze(rows, metrics)
    run_dir = write_outputs(Path(args.output_root), str(result_path), analysis)

    kb_root = Path(args.kb_root)
    conn = open_kb(kb_root)
    result_id = stable_id(args.project_name, str(result_path.resolve()), now())
    conn.execute(
        """
        INSERT INTO experiment_results(
            result_id, project_name, result_file, metrics_json, analysis_json, best_condition_json, next_action, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result_id,
            clean(args.project_name),
            str(result_path.resolve()),
            json.dumps(metrics, ensure_ascii=False),
            json.dumps(analysis, ensure_ascii=False),
            json.dumps(analysis.get("best_row", {}), ensure_ascii=False),
            analysis["next_action"],
            now(),
        ),
    )
    evidence_id = stable_id(args.project_name, "result_analysis", result_id)
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
            "result_analysis",
            result_path.stem,
            str(result_path.resolve()),
            markdown(str(result_path), analysis),
            json.dumps(analysis, ensure_ascii=False),
            json.dumps(["experiment_result"], ensure_ascii=False),
            "agent_analysis",
            now(),
            now(),
        ),
    )
    decision_id = stable_id(args.project_name, "result_decision", result_id)
    conn.execute(
        "INSERT INTO research_decisions(decision_id, project_name, decision_type, title, decision_text, linked_evidence_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            decision_id,
            clean(args.project_name),
            "experiment_result_decision",
            f"Result decision for {result_path.name}",
            f"Recommended next action: {analysis['next_action']}",
            json.dumps([evidence_id], ensure_ascii=False),
            now(),
        ),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"result_id": result_id, "decision_id": decision_id, "next_action": analysis["next_action"], "run_dir": str(run_dir)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
