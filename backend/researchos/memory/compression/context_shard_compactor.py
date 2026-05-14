from __future__ import annotations

from typing import Any


def compact_context_shards(items: list[dict[str, Any]], max_items: int = 20) -> dict[str, Any]:
    selected = list(items or [])[:max_items]
    return {"items": selected, "omitted": max(0, len(items or []) - len(selected))}

