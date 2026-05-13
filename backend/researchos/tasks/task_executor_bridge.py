from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec, utc_now


def _source_ids(result: ExecutionResult) -> list[str]:
    ids: list[str] = []
    for source in result.sources or []:
        if isinstance(source, dict):
            value = source.get("source_id") or source.get("id") or source.get("reference_id") or source.get("document_id")
            if value:
                ids.append(str(value))
    return sorted(set(ids))


def _sha256_if_available(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_artifacts_from_execution(result: ExecutionResult, task_spec: TaskSpec) -> list[dict[str, Any]]:
    source_ids = _source_ids(result)
    produced_by = result.skillrun_id or (task_spec.required_skills[0] if task_spec.required_skills else "execution_agent")
    created_at = utc_now().isoformat()
    artifacts: list[dict[str, Any]] = []
    for index, output_path in enumerate(result.output_files or [], start=1):
        path = str(output_path)
        suffix = Path(path).suffix.lstrip(".") or "file"
        artifacts.append(
            {
                "artifact_id": f"{task_spec.task_id}_artifact_{index}",
                "path": path,
                "type": suffix,
                "produced_by_skill": produced_by,
                "source_ids": source_ids,
                "hash": _sha256_if_available(path),
                "created_at": created_at,
            }
        )
    return artifacts


def execution_result_to_payload(result: ExecutionResult, artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "skillrun_id": result.skillrun_id,
        "status": result.status,
        "summary": result.summary,
        "output_files": list(result.output_files or []),
        "structured_outputs": dict(result.structured_outputs or {}),
        "logs_summary": {
            "count": len(result.logs or []),
            "head": list((result.logs or [])[:5]),
        },
        "errors": list(result.errors or []),
        "unresolved_items": list(result.unresolved_items or []),
        "artifacts": list(artifacts or []),
        "sources": list(result.sources or []),
        "validation_report": dict(result.validation_report or {}),
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
    }
