from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.researchos.memory.memory_config import append_jsonl, ensure_memoryos_dirs, read_jsonl, safe_project_id, utc_now_iso, write_jsonl
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories, load_semantic_memory, update_semantic_memory


def _path(project_id: str) -> Path:
    return ensure_memoryos_dirs()["conflicts"] / safe_project_id(project_id) / "conflicts.jsonl"


def _has_opposition(a: str, b: str) -> bool:
    la = a.lower()
    lb = b.lower()
    positive = {"increase", "increases", "upregulate", "activates", "improves"}
    negative = {"decrease", "decreases", "downregulate", "inhibits", "worsens"}
    return (any(word in la for word in positive) and any(word in lb for word in negative)) or (any(word in la for word in negative) and any(word in lb for word in positive))


def detect_conflicts(project_id: str) -> list[dict[str, Any]]:
    claims = [item for item in list_semantic_memories(project_id, memory_type="claim", status="") if item.get("status") in {"active", "needs_review"}]
    conflicts = []
    for index, a in enumerate(claims):
        for b in claims[index + 1 :]:
            shared = set(str(a.get("content", "")).lower().split()).intersection(str(b.get("content", "")).lower().split())
            if len(shared) >= 2 and _has_opposition(str(a.get("content")), str(b.get("content"))):
                conflicts.append({"memory_a": a["memory_id"], "memory_b": b["memory_id"], "reason": "opposing claim direction", "status": "detected"})
    return conflicts


def mark_conflict(memory_a: str, memory_b: str, reason: str) -> dict[str, Any]:
    a = load_semantic_memory(memory_a)
    conflict = {"conflict_id": f"conf_{uuid4().hex[:12]}", "project_id": a.get("project_id"), "memory_a": memory_a, "memory_b": memory_b, "reason": reason, "status": "needs_review", "created_at": utc_now_iso()}
    append_jsonl(_path(str(a.get("project_id"))), conflict)
    update_semantic_memory(memory_a, {"status": "needs_review"})
    update_semantic_memory(memory_b, {"status": "needs_review"})
    return conflict


def resolve_conflict(conflict_id: str, resolution: str) -> dict[str, Any]:
    for path in ensure_memoryos_dirs()["conflicts"].glob("*/conflicts.jsonl"):
        rows = read_jsonl(path)
        for row in rows:
            if row.get("conflict_id") == conflict_id:
                row["status"] = "resolved"
                row["resolution"] = resolution
                row["resolved_at"] = utc_now_iso()
                write_jsonl(path, rows)
                return row
    raise KeyError(f"conflict not found: {conflict_id}")

