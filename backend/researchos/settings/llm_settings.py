from __future__ import annotations

from typing import Any

from backend.researchos.llm.gateway import check_llm_connection

from .secret_store import delete_llm_settings, load_llm_settings_summary, redact_secrets_in_obj, save_llm_settings


def get_llm_settings_summary() -> dict[str, Any]:
    return load_llm_settings_summary()


def update_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:
    return save_llm_settings(payload)


def resolve_llm_mode() -> str:
    return str(load_llm_settings_summary().get("mode") or "not_configured")


def test_llm_settings(target: str | dict[str, Any] = "both") -> dict[str, Any]:
    if isinstance(target, dict):
        target = str(target.get("target") or "brain_agent")
    if target == "subscription":
        summary = load_llm_settings_summary()
        subscription = summary.get("subscription") or {}
        return {"ok": bool(subscription.get("enabled")), "target": "subscription", "status": subscription.get("status") or "inactive"}
    if target == "both":
        brain = check_llm_connection("brain_agent")
        execution = check_llm_connection("execution_agent")
        return {"ok": bool(brain.get("ok") and execution.get("ok")), "brain_agent": brain, "execution_agent": execution}
    if target not in {"brain_agent", "execution_agent"}:
        return {"ok": False, "error": "invalid_target"}
    return redact_secrets_in_obj(check_llm_connection(target))


def delete_settings() -> dict[str, Any]:
    return delete_llm_settings()
