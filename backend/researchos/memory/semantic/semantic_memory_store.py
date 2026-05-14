from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.researchos.brain.brain_page import brain_root, create_brain_page, read_brain_page, slugify
from backend.researchos.memory.memory_config import ensure_memoryos_dirs, read_jsonl, safe_project_id, utc_now_iso, write_jsonl
from backend.researchos.memory.memory_item import MemoryItem, create_memory_item, memory_item_from_dict, memory_item_to_dict, validate_memory_item


PAGE_TO_MEMORY_TYPE = {
    "project": "project_fact",
    "experiment": "evidence",
    "paper": "evidence",
    "dataset": "dataset",
    "protocol": "protocol",
    "claim": "claim",
    "failure": "failure",
    "decision": "decision",
    "report": "report",
    "generated_skill": "skill_knowledge",
}
MEMORY_TO_PAGE_TYPE = {
    "project_fact": "project",
    "evidence": "paper",
    "dataset": "dataset",
    "protocol": "protocol",
    "claim": "claim",
    "hypothesis": "claim",
    "decision": "decision",
    "failure": "failure",
    "report": "report",
    "skill_knowledge": "generated_skill",
}


def _path(project_id: str) -> Path:
    return ensure_memoryos_dirs()["semantic"] / safe_project_id(project_id) / "memory_items.jsonl"


def _all_paths() -> list[Path]:
    return list(ensure_memoryos_dirs()["semantic"].glob("*/memory_items.jsonl"))


def _write_project(project_id: str, rows: list[dict[str, Any]]) -> None:
    write_jsonl(_path(project_id), rows)


def create_semantic_memory_item(item: MemoryItem | dict[str, Any]) -> dict[str, Any]:
    memory = memory_item_from_dict(item) if isinstance(item, dict) else item
    validation = validate_memory_item(memory)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    rows = [row for row in read_jsonl(_path(memory.project_id)) if row.get("memory_id") != memory.memory_id]
    payload = memory_item_to_dict(memory)
    rows.append(payload)
    _write_project(memory.project_id, rows)
    return payload


def load_semantic_memory(memory_id: str) -> dict[str, Any]:
    for path in _all_paths():
        for row in read_jsonl(path):
            if row.get("memory_id") == memory_id:
                return row
    raise KeyError(f"semantic memory not found: {memory_id}")


def update_semantic_memory(memory_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    for path in _all_paths():
        rows = read_jsonl(path)
        for row in rows:
            if row.get("memory_id") != memory_id:
                continue
            patch = dict(patch or {})
            if "retrieval_count_delta" in patch:
                row["retrieval_count"] = int(row.get("retrieval_count") or 0) + int(patch.pop("retrieval_count_delta") or 0)
            if "importance_delta" in patch:
                row["importance_score"] = min(1.0, max(0.0, float(row.get("importance_score") or 0) + float(patch.pop("importance_delta") or 0)))
            if "provenance_append" in patch:
                row.setdefault("provenance", {})
                row["provenance"].update(patch.pop("provenance_append") or {})
            row.update(patch)
            row["updated_at"] = utc_now_iso()
            write_jsonl(path, rows)
            return row
    raise KeyError(f"semantic memory not found: {memory_id}")


def list_semantic_memories(project_id: str, memory_type: str | None = None, status: str = "active") -> list[dict[str, Any]]:
    rows = read_jsonl(_path(project_id))
    result = []
    for row in rows:
        if memory_type and row.get("memory_type") != memory_type:
            continue
        if status and row.get("status") != status:
            continue
        result.append(row)
    return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)


def sync_from_brain_pages(project_id: str) -> dict[str, Any]:
    created = 0
    skipped = 0
    for path in brain_root().rglob("*.md"):
        page = read_brain_page(path.stem)
        fm = page.get("frontmatter") or {}
        if fm.get("project_id") != project_id:
            continue
        existing = [
            row for row in list_semantic_memories(project_id, status="")
            if row.get("provenance", {}).get("brain_page_path") == str(path)
        ]
        if existing:
            skipped += 1
            continue
        item = create_memory_item(
            project_id=project_id,
            memory_layer="semantic",
            memory_type=PAGE_TO_MEMORY_TYPE.get(str(fm.get("type")), "project_fact"),
            title=str(fm.get("title") or path.stem),
            content=page.get("compiled_truth") or "",
            source_ids=fm.get("source_ids") or [],
            confidence=str(fm.get("confidence") or "medium"),
            status="archived" if fm.get("status") == "archived" else "active",
            tags=fm.get("tags") or [],
            provenance={"brain_page_path": str(path), "brain_page_slug": fm.get("slug")},
        )
        create_semantic_memory_item(item)
        created += 1
    return {"project_id": project_id, "created": created, "skipped": skipped}


def sync_to_brain_page(memory_item: MemoryItem | dict[str, Any]) -> dict[str, Any]:
    item = memory_item_to_dict(memory_item)
    page_type = MEMORY_TO_PAGE_TYPE.get(str(item.get("memory_type")), "project")
    page = create_brain_page(
        page_type,
        slugify(f"{item.get('project_id')}-{page_type}-{item.get('title')}-{item.get('memory_id')}")[:80],
        {
            "title": item.get("title"),
            "project_id": item.get("project_id"),
            "status": item.get("status") or "active",
            "confidence": item.get("confidence") or "medium",
            "source_ids": item.get("source_ids") or [],
            "tags": item.get("tags") or [],
        },
        item.get("content") or "",
        [
            {
                "evidence_type": page_type,
                "confidence": item.get("confidence") or "medium",
                "source_ids": item.get("source_ids") or [],
                "event": "Synced from MemoryOS semantic memory.",
                "impact": "Brain Page created from structured MemoryItem.",
            }
        ],
    )
    update_semantic_memory(str(item.get("memory_id")), {"provenance_append": {"brain_page_path": page["path"], "brain_page_slug": page["frontmatter"]["slug"]}})
    return page


def find_semantic_duplicates(project_id: str, item: MemoryItem | dict[str, Any]) -> list[dict[str, Any]]:
    target = memory_item_to_dict(item)
    title = str(target.get("title") or "").strip().lower()
    content = str(target.get("content") or "").strip().lower()
    duplicates = []
    for row in list_semantic_memories(project_id, status=""):
        if row.get("memory_id") == target.get("memory_id"):
            continue
        if title and str(row.get("title") or "").strip().lower() == title:
            duplicates.append(row)
            continue
        if content and str(row.get("content") or "").strip().lower() == content:
            duplicates.append(row)
    return duplicates

