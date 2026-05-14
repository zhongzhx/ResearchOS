from __future__ import annotations

from typing import Any


def check_context_budget(context: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    chars = len(str(context or ""))
    max_chars = max_tokens * 4
    return {"valid": chars <= max_chars, "estimated_chars": chars, "max_chars": max_chars}

