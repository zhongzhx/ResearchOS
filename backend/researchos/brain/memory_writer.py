from __future__ import annotations

from typing import Any

from backend.researchos.agents.agent_protocol import BrainDecision, ExecutionResult, TaskSpec

from .brain_page import create_brain_page, slugify
from .scientific_memory_validator import validate_memory_write
from backend.researchos.memory.compression.cognitive_state import refresh_cognitive_state_after_task
from backend.researchos.memory.events.event_store import append_event
from backend.researchos.memory.memory_event import create_memory_event
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item


def _source_ids(result: ExecutionResult) -> list[str]:
    ids = []
    if result.skillrun_id:
        ids.append(result.skillrun_id)
    ids.extend(result.output_files or [])
    for source in result.sources or []:
        if isinstance(source, dict):
            value = source.get("source_id") or source.get("id") or source.get("reference_id") or source.get("document_id")
            if value:
                ids.append(str(value))
    return sorted(set(ids))


def _write_page(page_type: str, project_id: str, title: str, truth: str, source_ids: list[str], confidence: str, tags: list[str] | None = None) -> dict[str, Any]:
    validation = validate_memory_write({"type": page_type, "text": truth, "source_ids": source_ids, "confidence": confidence})
    if not validation["valid"] and page_type == "claim":
        confidence = "low"
        if "hypothesis" not in truth.lower():
            truth = f"Hypothesis: {truth}"
    page = create_brain_page(
        page_type,
        slugify(f"{project_id}-{page_type}-{title}")[:80],
        {"title": title, "project_id": project_id, "status": "active" if confidence != "low" else "draft", "confidence": confidence, "source_ids": source_ids, "tags": tags or []},
        truth,
        [{"evidence_type": page_type, "confidence": confidence, "source_ids": source_ids, "event": "Memory written from Brain Agent evaluation.", "impact": "Created long-term brain page."}],
    )
    return {"page_type": page_type, "slug": page["frontmatter"]["slug"], "path": page["path"], "validation": validation}


def write_project_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("project", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Project Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


def write_experiment_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("experiment", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Experiment Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


def write_paper_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("paper", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Paper Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


def write_dataset_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("dataset", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Dataset Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


def write_claim_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("claim", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Claim Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


def write_failure_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("failure", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Failure Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


def write_decision_memory(reflection_or_result: dict[str, Any]) -> dict[str, Any]:
    return _write_page("decision", reflection_or_result.get("project_id", ""), reflection_or_result.get("title", "Decision Memory"), reflection_or_result.get("compiled_truth", ""), reflection_or_result.get("source_ids", []), reflection_or_result.get("confidence", "medium"))


MEMORY_WRITERS = {
    "project": write_project_memory,
    "experiment": write_experiment_memory,
    "paper": write_paper_memory,
    "dataset": write_dataset_memory,
    "claim": write_claim_memory,
    "failure": write_failure_memory,
    "decision": write_decision_memory,
}


PAGE_TO_MEMORY_TYPE = {
    "project": "project_fact",
    "experiment": "evidence",
    "paper": "evidence",
    "dataset": "dataset",
    "claim": "claim",
    "failure": "failure",
    "decision": "decision",
    "protocol": "protocol",
    "report": "report",
}


def _commit_promotion_to_memoryos(promotion_decision: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    project_id = str(promotion_decision.get("project_id") or "")
    task_id = str(promotion_decision.get("task_id") or "")
    if not project_id:
        return {"skipped": "missing_project_id", "memory_items": [], "events": []}
    memory_items = []
    events = []
    for item in promotion_decision.get("memory_items") or []:
        page_type = str(item.get("page_type") or "project")
        source_ids = list(item.get("source_ids") or [])
        memory = create_memory_item(
            project_id=project_id,
            memory_layer="semantic",
            memory_type=PAGE_TO_MEMORY_TYPE.get(page_type, "project_fact"),
            title=item.get("title") or f"{page_type.title()} Memory",
            content=item.get("compiled_truth") or "",
            source_ids=source_ids,
            task_ids=[task_id] if task_id else [],
            skillrun_ids=[source for source in source_ids if str(source).startswith("sr")],
            artifact_ids=[source for source in source_ids if "/" in str(source) or "\\" in str(source)],
            confidence=item.get("confidence") or "low",
            tags=item.get("tags") or [],
            provenance={
                "promotion_control_skill": promotion_decision.get("control_skill"),
                "pipeline_name": promotion_decision.get("pipeline_name"),
                "accepted_targets": promotion_decision.get("accepted_targets") or [],
                "brain_pages": pages,
            },
        )
        created = create_semantic_memory_item(memory)
        memory_items.append(created)
        event = append_event(
            create_memory_event(
                "evidence_promoted" if page_type != "failure" else "failure_logged",
                project_id=project_id,
                task_id=task_id or None,
                skillrun_id=(created.get("skillrun_ids") or [None])[0],
                source_id=created["memory_id"],
                source_type="brain_page",
                payload={"memory_id": created["memory_id"], "memory_type": created["memory_type"], "title": created["title"]},
                provenance={"promotion_decision": promotion_decision.get("control_skill"), "source_ids": source_ids},
            )
        )
        events.append(event)
    if task_id:
        try:
            refresh_cognitive_state_after_task(project_id, task_id)
        except Exception:
            pass
    return {"memory_items": memory_items, "events": events}


def write_memory_from_promotion_decision(promotion_decision: dict[str, Any]) -> dict[str, Any]:
    pages = []
    rejected = list(promotion_decision.get("rejected_items") or [])
    project_id = str(promotion_decision.get("project_id") or "")
    for item in promotion_decision.get("memory_items") or []:
        page_type = str(item.get("page_type") or "")
        writer = MEMORY_WRITERS.get(page_type)
        if not writer:
            rejected.append({"target": page_type or "unknown", "reason": "unsupported memory page_type"})
            continue
        payload = {
            "project_id": project_id,
            "title": item.get("title") or f"{page_type.title()} Memory",
            "compiled_truth": item.get("compiled_truth") or "",
            "source_ids": item.get("source_ids") or [],
            "confidence": item.get("confidence") or "low",
            "tags": item.get("tags") or [],
        }
        if not payload["compiled_truth"]:
            rejected.append({"target": page_type, "reason": "empty compiled truth"})
            continue
        pages.append(writer(payload))
    memoryos = _commit_promotion_to_memoryos(promotion_decision, pages)
    return {
        "control_skill": "memory_commit",
        "project_id": project_id,
        "pages": pages,
        "memoryos": memoryos,
        "rejected_items": rejected,
        "required_human_review": bool(promotion_decision.get("required_human_review")),
    }


def write_memory_from_execution_result(result: ExecutionResult, decision: BrainDecision, task_spec: TaskSpec) -> dict[str, Any]:
    project_id = task_spec.project_id or ""
    source_ids = _source_ids(result)
    pages = []
    if result.status == "failed":
        pages.append(write_failure_memory({"project_id": project_id, "title": f"Failed task {task_spec.task_id}", "compiled_truth": result.summary or "; ".join(result.errors), "source_ids": source_ids or [task_spec.task_id], "confidence": "medium"}))
        return {"pages": pages}
    if result.output_files:
        pages.append(write_dataset_memory({"project_id": project_id, "title": f"Outputs from {task_spec.task_type}", "compiled_truth": "\n".join(result.output_files), "source_ids": source_ids, "confidence": "medium"}))
    claim_text = result.structured_outputs.get("claim_text") if isinstance(result.structured_outputs, dict) else ""
    if claim_text or "claim:" in result.summary.lower():
        truth = claim_text or result.summary
        pages.append(write_claim_memory({"project_id": project_id, "title": truth[:60], "compiled_truth": truth, "source_ids": source_ids, "confidence": "medium" if source_ids else "low"}))
    elif result.summary:
        pages.append(write_project_memory({"project_id": project_id, "title": f"Brain result {task_spec.task_type}", "compiled_truth": result.summary, "source_ids": source_ids or [task_spec.task_id], "confidence": "medium"}))
    return {"pages": pages}
