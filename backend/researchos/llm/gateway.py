from __future__ import annotations

import urllib.request
from typing import Any

from backend.researchos.execution import runtime_adapter
from backend.researchos.settings.secret_store import load_llm_secret_for_agent, load_llm_settings_summary, redact_secrets_in_obj


ALLOWED_AGENTS = {"brain_agent", "execution_agent"}


def resolve_provider_mode() -> str:
    return str(load_llm_settings_summary().get("mode") or "not_configured")


def get_llm_config_for_agent(agent_name: str) -> dict[str, Any]:
    if agent_name not in ALLOWED_AGENTS:
        raise ValueError("agent_name must be brain_agent or execution_agent")
    config = load_llm_secret_for_agent(agent_name)
    return dict(config)


def _not_configured(agent_name: str, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "not_configured",
        "agent_name": agent_name,
        "mode": config.get("mode") or "not_configured",
        "provider": config.get("provider") or "",
        "model": config.get("model") or "",
        "error": "LLM provider is not configured for this agent.",
    }


def call_llm(agent_name: str, messages: list[dict[str, Any]], tools: Any = None, **kwargs: Any) -> dict[str, Any]:
    config = get_llm_config_for_agent(agent_name)
    provider = str(config.get("provider") or "").lower()
    if provider == "mock":
        return {
            "ok": True,
            "status": "mock",
            "agent_name": agent_name,
            "provider": "mock",
            "model": config.get("model") or "mock",
            "message": {"role": "assistant", "content": "mock_response"},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    if config.get("mode") == "subscription":
        if not config.get("subscription_token"):
            return _not_configured(agent_name, config)
        return {
            "ok": False,
            "status": "not_connected",
            "agent_name": agent_name,
            "provider": "researchos_subscription",
            "model": config.get("model") or "",
            "error": "ResearchOS subscription gateway is not connected in this local build.",
        }
    if not config.get("api_key") and provider not in {"mock"}:
        return _not_configured(agent_name, config)
    if not config.get("base_url"):
        return {
            "ok": False,
            "status": "not_connected",
            "agent_name": agent_name,
            "provider": config.get("provider") or "",
            "model": config.get("model") or "",
            "error": "LLM base_url is not configured for live calls.",
        }
    return _call_openai_compatible(agent_name, config, messages, tools=tools, **kwargs)


def _call_openai_compatible(agent_name: str, config: dict[str, Any], messages: list[dict[str, Any]], tools: Any = None, **kwargs: Any) -> dict[str, Any]:
    prompt, system_prompt = _messages_for_mvp_adapter(messages)
    try:
        mvp = runtime_adapter.import_research_os_mvp()
        adapter = mvp.LLMAdapter()
        adapter.provider = str(config.get("provider") or adapter.provider or "")
        adapter.model = str(config.get("model") or adapter.model or "")
        adapter.base_url = _mvp_base_url(config.get("base_url") or adapter.base_url or "")
        adapter.api_key = str(config.get("api_key") or adapter.api_key or "")
        content = adapter.chat_text(prompt, system_prompt=system_prompt, temperature=float(kwargs.get("temperature", 0)))
    except Exception as exc:  # noqa: BLE001
        return redact_secrets_in_obj({"ok": False, "status": "error", "agent_name": agent_name, "provider": config.get("provider") or "", "model": config.get("model") or "", "error": str(exc)})
    return redact_secrets_in_obj(
        {
            "ok": True,
            "status": "success",
            "agent_name": agent_name,
            "provider": config.get("provider") or "",
            "model": config.get("model") or "",
            "message": {"role": "assistant", "content": content},
            "usage": {},
        }
    )


def _mvp_base_url(base_url: Any) -> str:
    value = str(base_url or "").rstrip("/")
    suffix = "/chat/completions"
    if value.endswith(suffix):
        return value[: -len(suffix)]
    return value


def _messages_for_mvp_adapter(messages: list[dict[str, Any]]) -> tuple[str, str]:
    system_parts: list[str] = []
    conversational_parts: list[tuple[str, str]] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user").strip().lower() or "user"
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
        else:
            conversational_parts.append((role, content))
    if len(conversational_parts) == 1 and conversational_parts[0][0] == "user":
        prompt = conversational_parts[0][1]
    else:
        prompt = "\n\n".join(f"{role}: {content}" for role, content in conversational_parts)
    return prompt, "\n\n".join(system_parts)


def check_llm_connection(agent_name: str) -> dict[str, Any]:
    config = get_llm_config_for_agent(agent_name)
    provider = str(config.get("provider") or "").lower()
    if provider == "mock":
        return {"ok": True, "status": "ok", "agent_name": agent_name, "provider": "mock", "model": config.get("model") or "mock"}
    if config.get("mode") == "subscription":
        return {"ok": bool(config.get("subscription_token")), "status": "active" if config.get("subscription_token") else "not_configured", "agent_name": agent_name, "provider": "researchos_subscription"}
    if not config.get("api_key"):
        return _not_configured(agent_name, config)
    if not config.get("base_url"):
        return {"ok": False, "status": "not_connected", "agent_name": agent_name, "provider": config.get("provider") or "", "model": config.get("model") or "", "error": "LLM base_url is not configured for live test."}
    result = call_llm(agent_name, [{"role": "user", "content": "connection_ok"}], timeout=10)
    return redact_secrets_in_obj({key: value for key, value in result.items() if key != "message"})


test_llm_connection = check_llm_connection
test_llm_connection.__test__ = False
