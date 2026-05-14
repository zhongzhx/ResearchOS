from __future__ import annotations

from typing import Any

from backend.researchos.memory.memory_config import contains_secret


def check_secret_leakage(payload: Any) -> dict[str, Any]:
    leaked = contains_secret(payload)
    return {"valid": not leaked, "contains_sensitive_data": leaked}

