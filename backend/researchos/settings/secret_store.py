from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.researchos.config.env_loader import get_env, load_env_file
from backend.researchos.config.paths import get_agent_data_dir


ALLOWED_AGENTS = {"brain_agent", "execution_agent"}
SECRET_KEYS = {"api_key", "token", "subscription_token", "password", "cookie", "authorization"}


def _secrets_dir() -> Path:
    path = get_agent_data_dir() / "secrets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_path() -> Path:
    return _secrets_dir() / "llm_settings.json"


def _local_key_path() -> Path:
    return _secrets_dir() / ".llm_settings_key"


def _local_secret() -> bytes:
    path = _local_key_path()
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        _chmod_private(path)
    return path.read_text(encoding="utf-8").encode("utf-8")


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except Exception:
        pass


def _protect(value: str) -> str:
    if not value:
        return ""
    key = _local_secret()
    raw = value.encode("utf-8")
    encrypted = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(raw))
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def _unprotect(value: str) -> str:
    if not value:
        return ""
    try:
        key = _local_secret()
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        decrypted = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(raw))
        return decrypted.decode("utf-8")
    except Exception:
        return ""


def mask_secret(secret: str | None) -> str:
    text = str(secret or "")
    if not text:
        return ""
    return f"****{text[-4:]}" if len(text) > 4 else "****"


def _read() -> dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write(payload: dict[str, Any]) -> None:
    path = _settings_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _chmod_private(path)


def _agent_payload(settings: dict[str, Any], agent_name: str, existing: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "brain_agent": ("brain", "brain_agent"),
        "execution_agent": ("execution", "execution_agent"),
    }
    short, nested = aliases[agent_name]
    nested_payload = settings.get(nested) if isinstance(settings.get(nested), dict) else {}
    existing_agent = existing.get(agent_name) if isinstance(existing.get(agent_name), dict) else {}
    provider = str(nested_payload.get("provider") or settings.get(f"{short}_provider") or settings.get("provider") or existing_agent.get("provider") or "").strip()
    model = str(nested_payload.get("model") or settings.get(f"{short}_model") or settings.get("model") or existing_agent.get("model") or "").strip()
    base_url = str(nested_payload.get("base_url") or settings.get(f"{short}_base_url") or settings.get("base_url") or existing_agent.get("base_url") or "").strip()
    api_key = str(nested_payload.get("api_key") or settings.get(f"{short}_api_key") or settings.get("api_key") or "").strip()
    if settings.get(f"clear_{short}_api_key"):
        encrypted = ""
        masked = ""
    elif api_key:
        encrypted = _protect(api_key)
        masked = mask_secret(api_key)
    else:
        encrypted = str(existing_agent.get("api_key_encrypted") or "")
        masked = str(existing_agent.get("masked_key") or "")
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_encrypted": encrypted,
        "masked_key": masked,
        "key_configured": bool(masked),
    }


def _subscription_payload(settings: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    nested = settings.get("subscription") if isinstance(settings.get("subscription"), dict) else {}
    token = str(nested.get("token") or settings.get("subscription_token") or settings.get("researchos_subscription_token") or "").strip()
    existing_sub = existing.get("subscription") if isinstance(existing.get("subscription"), dict) else {}
    encrypted = _protect(token) if token else str(existing_sub.get("token_encrypted") or "")
    masked = mask_secret(token) if token else str(existing_sub.get("masked_token") or "")
    workspace_id = str(nested.get("workspace_id") or settings.get("workspace_id") or get_env("RESEARCHOS_WORKSPACE_ID", "") or existing_sub.get("workspace_id") or "").strip()
    return {
        "enabled": bool(encrypted),
        "status": "active" if encrypted else "inactive",
        "workspace_id": workspace_id,
        "token_encrypted": encrypted,
        "masked_token": masked,
    }


def save_llm_settings(settings: dict[str, Any]) -> dict[str, Any]:
    existing = _read()
    mode = str(settings.get("mode") or existing.get("mode") or "single_key").strip()
    if mode not in {"single_key", "separate_keys", "subscription"}:
        mode = "single_key"
    brain = _agent_payload(settings, "brain_agent", existing)
    execution = _agent_payload(settings, "execution_agent", existing)
    if mode == "single_key":
        execution = {
            "provider": execution.get("provider") or brain.get("provider"),
            "model": execution.get("model") or brain.get("model"),
            "base_url": execution.get("base_url") or brain.get("base_url"),
            "api_key_encrypted": brain.get("api_key_encrypted") or execution.get("api_key_encrypted") or "",
            "masked_key": brain.get("masked_key") or execution.get("masked_key") or "",
            "key_configured": bool(brain.get("masked_key") or execution.get("masked_key")),
        }
    subscription = _subscription_payload(settings, existing)
    payload = {
        "mode": mode,
        "brain_agent": brain,
        "execution_agent": execution,
        "subscription": subscription,
        "storage_note": "TODO: replace with OS keyring/encrypted store before production.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write(payload)
    return load_llm_settings_summary()


def _env_agent(agent_name: str) -> dict[str, Any]:
    load_env_file()
    prefix = "BRAIN_AGENT" if agent_name == "brain_agent" else "EXECUTION_AGENT"
    provider = get_env(f"{prefix}_PROVIDER") or get_env("LLM_PROVIDER") or ("openai" if get_env("OPENAI_API_KEY") else "")
    api_key = get_env(f"{prefix}_API_KEY") or get_env("MINIMAX_API_KEY") or get_env("OPENAI_API_KEY") or get_env("LLM_API_KEY") or ""
    model = get_env(f"{prefix}_MODEL") or get_env("MINIMAX_MODEL") or get_env("OPENAI_MODEL") or get_env("LLM_MODEL") or ""
    base_url = get_env(f"{prefix}_BASE_URL") or get_env("MINIMAX_BASE_URL") or get_env("OPENAI_BASE_URL") or get_env("LLM_BASE_URL") or ""
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "masked_key": mask_secret(api_key),
        "key_configured": bool(api_key),
        "source": "env_fallback",
    }


def _summary_agent(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": agent.get("provider") or "",
        "model": agent.get("model") or "",
        "base_url": agent.get("base_url") or "",
        "key_configured": bool(agent.get("key_configured") or agent.get("masked_key")),
        "masked_key": agent.get("masked_key") or "",
    }


def load_llm_settings_summary() -> dict[str, Any]:
    saved = _read()
    if saved:
        mode = str(saved.get("mode") or "single_key")
        brain = _summary_agent(saved.get("brain_agent") if isinstance(saved.get("brain_agent"), dict) else {})
        execution = _summary_agent(saved.get("execution_agent") if isinstance(saved.get("execution_agent"), dict) else {})
        subscription = saved.get("subscription") if isinstance(saved.get("subscription"), dict) else {}
    else:
        brain_env = _env_agent("brain_agent")
        execution_env = _env_agent("execution_agent")
        has_env = bool(brain_env.get("api_key") or execution_env.get("api_key") or brain_env.get("provider") == "mock")
        mode = "env_fallback" if has_env else "not_configured"
        brain = _summary_agent(brain_env)
        execution = _summary_agent(execution_env)
        subscription = {
            "enabled": bool(get_env("RESEARCHOS_SUBSCRIPTION_TOKEN")),
            "status": "active" if get_env("RESEARCHOS_SUBSCRIPTION_TOKEN") else "inactive",
            "workspace_id": get_env("RESEARCHOS_WORKSPACE_ID", ""),
            "masked_token": mask_secret(get_env("RESEARCHOS_SUBSCRIPTION_TOKEN", "")),
        }
    return _legacy_aliases(
        {
            "ok": True,
            "mode": mode,
            "brain_agent": brain,
            "execution_agent": execution,
            "subscription": {
                "enabled": bool(subscription.get("enabled")),
                "status": subscription.get("status") or "inactive",
                "workspace_id": subscription.get("workspace_id") or "",
                "masked_token": subscription.get("masked_token") or "",
            },
        }
    )


def _legacy_aliases(summary: dict[str, Any]) -> dict[str, Any]:
    brain = summary.get("brain_agent") or {}
    execution = summary.get("execution_agent") or {}
    def legacy_mask(masked: str) -> str:
        suffix = str(masked or "").replace("*", "")
        return f"sk-...{suffix}" if suffix else ""

    summary.update(
        {
            "provider": brain.get("provider") or "",
            "model": brain.get("model") or "",
            "base_url": brain.get("base_url") or "",
            "masked_key": brain.get("masked_key") or "",
            "api_key_configured": brain.get("key_configured", False),
            "brain_provider": brain.get("provider") or "",
            "brain_model": brain.get("model") or "",
            "brain_base_url": brain.get("base_url") or "",
            "brain_api_key_masked": legacy_mask(brain.get("masked_key") or ""),
            "execution_provider": execution.get("provider") or "",
            "execution_model": execution.get("model") or "",
            "execution_base_url": execution.get("base_url") or "",
            "execution_api_key_masked": legacy_mask(execution.get("masked_key") or ""),
            "subscription_status": (summary.get("subscription") or {}).get("status") or "inactive",
        }
    )
    summary["settings"] = {
        key: value
        for key, value in summary.items()
        if key
        in {
            "mode",
            "provider",
            "model",
            "base_url",
            "masked_key",
            "api_key_configured",
            "brain_provider",
            "brain_model",
            "brain_base_url",
            "brain_api_key_masked",
            "execution_provider",
            "execution_model",
            "execution_base_url",
            "execution_api_key_masked",
            "subscription_status",
        }
    }
    return summary


def load_llm_secret_for_agent(agent_name: str) -> dict[str, Any]:
    if agent_name not in ALLOWED_AGENTS:
        raise ValueError("agent_name must be brain_agent or execution_agent")
    saved = _read()
    if saved:
        mode = str(saved.get("mode") or "single_key")
        if mode == "subscription":
            subscription = saved.get("subscription") if isinstance(saved.get("subscription"), dict) else {}
            return {
                "mode": "subscription",
                "agent_name": agent_name,
                "provider": "researchos_subscription",
                "model": "",
                "base_url": "",
                "api_key": "",
                "subscription_token": _unprotect(str(subscription.get("token_encrypted") or "")),
                "workspace_id": subscription.get("workspace_id") or "",
                "key_configured": bool(subscription.get("token_encrypted")),
            }
        agent = saved.get(agent_name) if isinstance(saved.get(agent_name), dict) else {}
        return {
            "mode": mode,
            "agent_name": agent_name,
            "provider": agent.get("provider") or "",
            "model": agent.get("model") or "",
            "base_url": agent.get("base_url") or "",
            "api_key": _unprotect(str(agent.get("api_key_encrypted") or "")),
            "key_configured": bool(agent.get("api_key_encrypted") or agent.get("provider") == "mock"),
        }
    env = _env_agent(agent_name)
    return {
        "mode": "env_fallback" if env.get("api_key") or env.get("provider") else "not_configured",
        "agent_name": agent_name,
        "provider": env.get("provider") or "",
        "model": env.get("model") or "",
        "base_url": env.get("base_url") or "",
        "api_key": env.get("api_key") or "",
        "key_configured": bool(env.get("api_key") or env.get("provider") == "mock"),
    }


def delete_llm_settings() -> dict[str, Any]:
    path = _settings_path()
    if path.exists():
        path.unlink()
    return {"ok": True, "deleted": True}


def redact_secrets_in_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: ("[redacted]" if str(key).lower() in SECRET_KEYS else redact_secrets_in_obj(value)) for key, value in obj.items()}
    if isinstance(obj, list):
        return [redact_secrets_in_obj(value) for value in obj]
    if isinstance(obj, tuple):
        return [redact_secrets_in_obj(value) for value in obj]
    if isinstance(obj, str):
        value = obj
        for marker in ["api_key=", "OPENAI_API_KEY=", "MINIMAX_API_KEY=", "token=", "password=", "secret="]:
            lower = value.lower()
            if marker.lower() in lower:
                prefix = value[: lower.index(marker.lower()) + len(marker)]
                return f"{prefix}[redacted]"
        if value.startswith("sk-"):
            return mask_secret(value)
    return obj
