from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.researchos.brain.brain_page import brain_root
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp


def _template_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-").lower() or "workflow-template"


def templates_dir() -> Path:
    path = brain_root() / "workflows" / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def detect_repeated_workflow_patterns(project_id: str) -> list[dict[str, Any]]:
    ros = import_research_os_mvp()
    runs = [run for run in ros.list_skill_runs(default_agent_root(), project_id=project_id, status="completed", limit=200)]
    task_types = []
    for run in runs:
        payload = run.get("input_payload") if isinstance(run.get("input_payload"), dict) else {}
        task_types.append(payload.get("task_type") or run.get("skill_name"))
    counts = Counter(task_types)
    return [{"task_type": task_type, "count": count, "project_id": project_id} for task_type, count in counts.items() if task_type and count >= 2]


def build_workflow_template_from_skillruns(skillrun_ids: list[str]) -> dict[str, Any]:
    if len(skillrun_ids) < 2:
        raise ValueError("at least two similar successful skillruns are required")
    ros = import_research_os_mvp()
    runs = [ros.get_skill_run(default_agent_root(), skillrun_id) for skillrun_id in skillrun_ids]
    if any(run.get("status") != "completed" for run in runs):
        raise ValueError("failed-only workflow cannot generate template")
    project_id = runs[0].get("project_id", "")
    task_type = (runs[0].get("input_payload") or {}).get("task_type") or runs[0].get("skill_name")
    return {
        "template_name": f"{task_type} reusable workflow",
        "description": f"Reusable workflow inferred from {len(runs)} successful skillruns.",
        "stages": [{"name": "prepare_inputs"}, {"name": "run_skill"}, {"name": "validate_outputs"}],
        "required_inputs": ["project_id", "task_input"],
        "default_outputs": ["structured_outputs", "artifacts"],
        "reusable_skills": sorted({run.get("skill_id") for run in runs if run.get("skill_id")}),
        "validation_rules": ["Require provenance", "Do not promote unsupported claims"],
        "created_from_skillruns": skillrun_ids,
        "project_id": project_id,
        "status": "pending_review",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def save_workflow_template(template: dict[str, Any]) -> dict[str, Any]:
    template = dict(template)
    template.setdefault("status", "pending_review")
    path = templates_dir() / f"{_template_name(template['template_name'])}.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {**template, "path": str(path)}


def list_workflow_templates(project_id: str) -> list[dict[str, Any]]:
    rows = []
    for path in templates_dir().glob("*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if not project_id or row.get("project_id") == project_id:
            rows.append({**row, "path": str(path)})
    return rows
