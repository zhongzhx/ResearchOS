from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
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
        CREATE TABLE IF NOT EXISTS experiment_designs (
            design_id TEXT PRIMARY KEY,
            project_name TEXT,
            objective TEXT,
            field TEXT,
            design_json TEXT,
            run_table_json TEXT,
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


def parse_factor(value: str) -> tuple[str, list[str]]:
    if ":" not in value:
        raise ValueError(f"Factor must use name:level1,level2 format: {value}")
    name, levels = value.split(":", 1)
    parsed = [clean(item) for item in levels.split(",") if clean(item)]
    if not parsed:
        raise ValueError(f"Factor has no levels: {value}")
    return clean(name), parsed


def parse_metric(value: str) -> dict[str, str]:
    if ":" in value:
        name, direction = value.split(":", 1)
    else:
        name, direction = value, "max"
    direction = direction.lower().strip()
    if direction not in {"max", "min"}:
        direction = "max"
    return {"metric": clean(name), "direction": direction}


def default_factors(field: str) -> list[tuple[str, list[str]]]:
    if field == "bio":
        return [("treatment_dose", ["low", "medium", "high"]), ("time_point", ["24h", "48h"]), ("model", ["primary_model"])]
    if field == "chem":
        return [("catalyst", ["baseline", "candidate_A"]), ("solvent", ["solvent_1", "solvent_2"]), ("temperature", ["low", "medium"])]
    if field == "materials":
        return [("composition", ["baseline", "variant_A"]), ("synthesis_temperature", ["low", "medium", "high"]), ("annealing_time", ["short", "long"])]
    return [("factor_A", ["low", "high"]), ("factor_B", ["baseline", "variant"])]


def default_metrics(field: str) -> list[dict[str, str]]:
    if field == "bio":
        return [{"metric": "effect_size", "direction": "max"}, {"metric": "toxicity", "direction": "min"}]
    if field == "chem":
        return [{"metric": "yield", "direction": "max"}, {"metric": "impurity", "direction": "min"}]
    if field == "materials":
        return [{"metric": "performance", "direction": "max"}, {"metric": "stability_loss", "direction": "min"}]
    return [{"metric": "primary_outcome", "direction": "max"}]


def safety_check(field: str) -> list[str]:
    checks = ["Qualified human review is required before execution.", "Record deviations and failures as project evidence."]
    if field == "bio":
        checks.append("Confirm biosafety, cell/animal/human-subject approval, and clinical-data permissions where applicable.")
    elif field == "chem":
        checks.append("Confirm chemical hazard, waste, pressure, temperature, toxicity, and ventilation requirements.")
    elif field == "materials":
        checks.append("Confirm nanoparticle, high-temperature, solvent, and instrument safety requirements.")
    return checks


def build_run_table(factors: list[tuple[str, list[str]]], controls: list[str], max_runs: int) -> list[dict[str, Any]]:
    names = [name for name, _ in factors]
    level_sets = [levels for _, levels in factors]
    table: list[dict[str, Any]] = []
    for control in controls:
        row = {"run_id": f"control_{len(table) + 1:03d}", "run_type": "control", "control": control}
        for name in names:
            row[name] = "control"
        table.append(row)
    for index, combo in enumerate(itertools.product(*level_sets), 1):
        if len(table) >= max_runs:
            break
        row = {"run_id": f"run_{index:03d}", "run_type": "candidate", "control": ""}
        row.update(dict(zip(names, combo)))
        table.append(row)
    return table


def pilot_subset(run_table: list[dict[str, Any]], max_pilot: int = 6) -> list[str]:
    controls = [row["run_id"] for row in run_table if row.get("run_type") == "control"]
    candidates = [row["run_id"] for row in run_table if row.get("run_type") == "candidate"]
    return (controls + candidates[: max(0, max_pilot - len(controls))])[:max_pilot]


def markdown(design: dict[str, Any]) -> str:
    lines = ["# Experiment Matrix", "", f"Objective: {design['objective']}", f"Field: {design['field']}", "", "## Factors", ""]
    for factor in design["factors"]:
        lines.append(f"- {factor['name']}: {', '.join(factor['levels'])}")
    lines.extend(["", "## Controls", ""])
    lines.extend(f"- {item}" for item in design["controls"])
    lines.extend(["", "## Metrics", ""])
    for metric in design["metrics"]:
        lines.append(f"- {metric['metric']} ({metric['direction']})")
    lines.extend(["", "## Pilot Runs", ""])
    lines.extend(f"- {run_id}" for run_id in design["pilot_subset"])
    lines.extend(["", "## Safety and Feasibility Checks", ""])
    lines.extend(f"- {item}" for item in design["safety_checks"])
    lines.extend(["", "## Decision Rule", "", design["decision_rule"]])
    return "\n".join(lines)


def write_outputs(output_root: Path, design: dict[str, Any], run_table: list[dict[str, Any]]) -> Path:
    run_dir = output_root / f"experiment_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "experiment_design.json").write_text(json.dumps(design, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "experiment_design.md").write_text(markdown(design), encoding="utf-8")
    with (run_dir / "experiment_run_table.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = sorted({key for row in run_table for key in row.keys()})
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in run_table:
            writer.writerow(row)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Design a controlled experiment matrix.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--field", choices=["bio", "chem", "materials", "general"], default="general")
    parser.add_argument("--factor", action="append", default=None)
    parser.add_argument("--control", action="append", default=None)
    parser.add_argument("--metric", action="append", default=None)
    parser.add_argument("--constraint", action="append", default=None)
    parser.add_argument("--max-runs", type=int, default=24)
    parser.add_argument("--replicates", default="pilot:1; confirmation:3")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    factors = [parse_factor(value) for value in args.factor] if args.factor else default_factors(args.field)
    controls = [clean(item) for item in args.control or [] if clean(item)] or ["baseline", "negative_or_blank_control"]
    metrics = [parse_metric(value) for value in args.metric] if args.metric else default_metrics(args.field)
    run_table = build_run_table(factors, controls, max(1, args.max_runs))
    design = {
        "project_name": clean(args.project_name),
        "objective": clean(args.objective),
        "field": args.field,
        "factors": [{"name": name, "levels": levels} for name, levels in factors],
        "controls": controls,
        "metrics": metrics,
        "constraints": [clean(item) for item in args.constraint or [] if clean(item)],
        "replicates": clean(args.replicates),
        "pilot_subset": pilot_subset(run_table),
        "safety_checks": safety_check(args.field),
        "decision_rule": "Proceed only if controls behave as expected and the primary metric improves without unacceptable secondary-metric collapse.",
        "created_at": now(),
    }
    run_dir = write_outputs(Path(args.output_root), design, run_table)

    kb_root = Path(args.kb_root)
    conn = open_kb(kb_root)
    design_id = stable_id(args.project_name, args.objective, now())
    conn.execute(
        "INSERT INTO experiment_designs(design_id, project_name, objective, field, design_json, run_table_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (design_id, clean(args.project_name), clean(args.objective), args.field, json.dumps(design, ensure_ascii=False), json.dumps(run_table, ensure_ascii=False), now()),
    )
    evidence_id = stable_id(args.project_name, "experiment_design", design_id)
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
            "experiment_design",
            clean(args.objective),
            str(run_dir),
            markdown(design),
            json.dumps({"design": design, "run_table": run_table}, ensure_ascii=False),
            json.dumps([args.field, "experiment_matrix"], ensure_ascii=False),
            "agent_generated_plan",
            now(),
            now(),
        ),
    )
    conn.commit()
    conn.close()
    print(json.dumps({"design_id": design_id, "run_count": len(run_table), "run_dir": str(run_dir)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
