from __future__ import annotations

from typing import Any


def _pages_by_type(pages: list[dict[str, Any]], page_type: str) -> list[dict[str, Any]]:
    return [page for page in pages if page.get("page_type") == page_type]


def build_memory_commit_record(
    promotion_decision: dict[str, Any],
    memory_commit: dict[str, Any],
    graph_update: dict[str, Any] | None = None,
    context_index_update: dict[str, Any] | None = None,
    pending_skill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pages = list((memory_commit or {}).get("pages") or [])
    rejected_items = []
    rejected_items.extend((promotion_decision or {}).get("rejected_items") or [])
    rejected_items.extend((memory_commit or {}).get("rejected_items") or [])
    return {
        "promoted_pages": pages,
        "promoted_claims": _pages_by_type(pages, "claim"),
        "promoted_datasets": _pages_by_type(pages, "dataset"),
        "promoted_decisions": _pages_by_type(pages, "decision"),
        "failure_memory": _pages_by_type(pages, "failure"),
        "context_index_update": context_index_update or {},
        "graph_update": graph_update or {},
        "pending_skill": pending_skill or {},
        "rejected_items": rejected_items,
        "required_human_review": bool((promotion_decision or {}).get("required_human_review") or (memory_commit or {}).get("required_human_review")),
        "promotion_decision": promotion_decision or {},
        "memory_commit": memory_commit or {},
    }
