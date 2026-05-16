from __future__ import annotations

from typing import Any, Callable

from backend.researchos.settings.secret_store import redact_secrets_in_obj


def ok_response(**payload: Any) -> dict[str, Any]:
    return redact_secrets_in_obj({"ok": True, **payload})


def disabled_response(reason: str) -> dict[str, Any]:
    return {"ok": False, "status": "disabled", "error": reason, "reason": reason}


def not_connected_response(reason: str, **payload: Any) -> dict[str, Any]:
    return redact_secrets_in_obj({"ok": False, "status": "not_connected", "error": reason, "reason": reason, **payload})


def partial_response(reason: str, **payload: Any) -> dict[str, Any]:
    return redact_secrets_in_obj({"ok": True, "status": "partial", "warning": reason, **payload})


def safe_call(callback: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = callback()
        return redact_secrets_in_obj(result)
    except Exception as exc:  # noqa: BLE001
        return redact_secrets_in_obj({"ok": False, "status": "error", "error": str(exc)})
