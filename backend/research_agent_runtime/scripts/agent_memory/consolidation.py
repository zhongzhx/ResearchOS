from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import connect
from .models import clean, row_to_dict, truncate
from .retrieval import retrieve_memory
from .views import upsert_memory_view


def _rows(conn: Any, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def consolidate_memory(agent_root: Path, user_id: str, group_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
    project_id = clean(project_id)
    if not project_id:
        raise ValueError("project_id is required")
    conn = connect(agent_root)
    projects = _rows(conn, "SELECT * FROM projects WHERE id=?", (project_id,))

    views = []
    for project in projects:
        pid = project["id"]
        experiments = _rows(conn, "SELECT * FROM experiments WHERE project_id=? ORDER BY COALESCE(date, created_at)", (pid,))
        samples = _rows(conn, "SELECT * FROM samples WHERE project_id=? ORDER BY sample_code", (pid,))
        data_files = _rows(conn, "SELECT * FROM data_files WHERE project_id=? ORDER BY upload_time DESC", (pid,))
        memories = retrieve_memory(agent_root, user_id=user_id, group_id=group_id, project_id=pid, max_results=200)
        conclusions = [m for m in memories if m["memory_type"] == "conclusion_memory"]
        failures = [m for m in memories if m["memory_type"] == "failure_memory"]
        decisions = [m for m in memories if m["memory_type"] == "decision_memory"]
        tasks = [m for m in memories if m["memory_type"] == "task_memory"]

        structured = {
            "project_title": project.get("title"),
            "research_question": project.get("research_question"),
            "current_stage": project.get("stage"),
            "completed_experiments": [
                {
                    "id": exp["id"],
                    "title": exp.get("title"),
                    "type": exp.get("experiment_type"),
                    "status": exp.get("status"),
                    "result_summary": exp.get("result_summary"),
                    "conclusion": exp.get("conclusion"),
                    "sample_ids": exp.get("sample_ids", []),
                }
                for exp in experiments
                if exp.get("status") in {"completed", "failed", "negative", "invalidated"}
            ],
            "available_datasets": [
                {
                    "id": data_file["id"],
                    "filename": data_file.get("filename"),
                    "file_type": data_file.get("file_type"),
                    "analysis_status": data_file.get("analysis_status"),
                    "experiment_id": data_file.get("experiment_id"),
                }
                for data_file in data_files
            ],
            "key_samples": [
                {
                    "id": sample["id"],
                    "sample_code": sample.get("sample_code"),
                    "sample_type": sample.get("sample_type"),
                    "batch": sample.get("batch"),
                    "current_status": sample.get("current_status"),
                }
                for sample in samples
            ],
            "main_findings": [truncate(m.get("content", ""), 220) for m in conclusions[:8]],
            "negative_results": [truncate(m.get("content", ""), 220) for m in failures[:8]],
            "important_decisions": [truncate(m.get("content", ""), 220) for m in decisions[:8]],
            "current_limitations": [truncate(m.get("content", ""), 180) for m in memories if "limitation" in (m.get("tags") or [])][:8],
            "next_steps": [truncate(m.get("content", ""), 180) for m in tasks[:8]],
            "target_outputs": [project.get("target_output")] + (project.get("target_journals") or []),
        }
        summary = (
            f"{project.get('title')} is at {project.get('stage') or 'unknown'} stage. "
            f"Experiments recorded: {len(experiments)}; data files: {len(data_files)}; "
            f"active conclusions: {len(conclusions)}; failure memories: {len(failures)}."
        )
        evidence_ids = [m["id"] for m in memories[:80]]
        views.append(
            upsert_memory_view(
                agent_root,
                user_id=user_id,
                group_id=group_id or project.get("group_id") or "",
                project_id=pid,
                view_type="project_current_state",
                subject=project.get("title") or pid,
                summary=summary,
                structured_summary=structured,
                evidence_memory_ids=evidence_ids,
                confidence=0.82 if memories or experiments else 0.55,
            )
        )
    conn.close()
    return {"project_count": len(projects), "views": views}
