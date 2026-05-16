from __future__ import annotations

import sys
import os
import re
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    try:
        from backend.researchos.config.paths import get_repo_root

        return get_repo_root()
    except Exception:
        return Path(__file__).resolve().parents[3]


def runtime_skill_dir() -> Path:
    return repo_root() / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime"


def scripts_dir() -> Path:
    return repo_root() / "backend" / "research_agent_runtime" / "scripts"


def import_research_os_mvp() -> Any:
    path = scripts_dir()
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    import research_os_mvp  # type: ignore

    return research_os_mvp


def default_agent_root() -> Path:
    if os.environ.get("RESEARCHOS_AGENT_ROOT"):
        return Path(os.environ["RESEARCHOS_AGENT_ROOT"])
    from backend.researchos.config.paths import get_agent_data_dir

    return get_agent_data_dir()


SECRET_REDACTION_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{4,}"), "sk-[REDACTED]"),
    (re.compile(r"(?i)\b(api[_ -]?key|token|password|secret|cookie)\b\s*[:=]\s*['\"]?[^'\"\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/-]+=*"), r"\1 [REDACTED]"),
]

BROWSER_AUTH_PIPELINES = {"browser_research_learning"}
BROWSER_AUTH_MARKERS = ("browser", "browser-use", "remote-browser", "browser_profile", "profile")
SENSITIVE_PATH_PARTS = {".env", "secret_store", "secrets", "api_keys", "api-key", "credentials"}


def redact_text(value: Any, max_chars: int | None = None) -> str:
    text = str(value or "")
    for pattern, replacement in SECRET_REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"
    return text


def redact_payload(value: Any, max_chars: int | None = None) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item, max_chars=max_chars) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item, max_chars=max_chars) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item, max_chars=max_chars) for item in value]
    if isinstance(value, str):
        return redact_text(value, max_chars=max_chars)
    return value


def is_sensitive_path(path: str | Path) -> bool:
    value = str(path or "").replace("\\", "/").lower()
    parts = {part for part in value.split("/") if part}
    if ".env" in parts or value.endswith("/.env") or value.endswith("\\.env"):
        return True
    if "data/secrets" in value or "data\\secrets" in value:
        return True
    return bool(parts.intersection(SENSITIVE_PATH_PARTS))


def _normal_flags(user_authorization_flags: dict[str, Any] | None) -> dict[str, bool]:
    flags = user_authorization_flags if isinstance(user_authorization_flags, dict) else {}
    return {str(key): bool(value) for key, value in flags.items()}


def _has_flag(flags: dict[str, bool], keys: list[str]) -> bool:
    return any(bool(flags.get(key)) for key in keys)


def _is_browser_related(value: Any) -> bool:
    text = str(value or "").replace("_", "-").lower()
    return any(marker.replace("_", "-") in text for marker in BROWSER_AUTH_MARKERS)


def _skill_requires_authorization(skill_id: str) -> tuple[bool, str]:
    try:
        from backend.researchos.skills.skill_catalog_loader import get_skill_by_id

        row = get_skill_by_id(skill_id)
        if bool(row.get("requires_user_authorization")):
            return True, "skill_catalog"
    except Exception:  # noqa: BLE001
        pass
    if _is_browser_related(skill_id):
        return True, "browser_skill_policy"
    return False, ""


def check_skill_authorization(required_skills: list[str], user_authorization_flags: dict[str, Any] | None) -> dict[str, Any]:
    flags = _normal_flags(user_authorization_flags)
    errors: list[str] = []
    required_authorizations: list[dict[str, str]] = []
    for skill_id in required_skills or []:
        requires_auth, reason = _skill_requires_authorization(str(skill_id))
        if not requires_auth:
            continue
        required_authorizations.append({"type": "skill", "id": str(skill_id), "reason": reason})
        keys = ["authorized", "all_skills", str(skill_id), f"skill:{skill_id}"]
        if _is_browser_related(skill_id):
            keys.extend(["browser", "browser_tools", "browser_research_learning"])
        if not _has_flag(flags, keys):
            errors.append(f"skill requires user authorization: {skill_id}")
    return {
        "valid": not errors,
        "errors": errors,
        "requires_user_authorization": bool(required_authorizations),
        "missing_authorization": bool(errors),
        "required_authorizations": required_authorizations,
        "user_authorization_flags": flags,
    }


def _authorization_flags_from_task(task_spec: Any) -> dict[str, Any]:
    input_data = getattr(task_spec, "input_data", {}) or {}
    flags = dict(input_data.get("user_authorization_flags") or {})
    if input_data.get("authorized") is True:
        flags["authorized"] = True
    if input_data.get("browser_authorized") is True:
        flags["browser"] = True
    return flags


def check_pipeline_authorization(task_spec: Any, pipeline: dict[str, Any] | None) -> dict[str, Any]:
    pipeline = pipeline or {}
    input_data = getattr(task_spec, "input_data", {}) or {}
    pipeline_name = str(pipeline.get("pipeline_name") or input_data.get("pipeline_name") or getattr(task_spec, "task_type", "") or "")
    flags = _normal_flags(_authorization_flags_from_task(task_spec))
    required_skills = list(getattr(task_spec, "required_skills", []) or pipeline.get("execution_skills") or [])
    safety_constraints = set(getattr(task_spec, "safety_constraints", []) or [])
    requires_pipeline_auth = bool(pipeline.get("requires_user_authorization")) or "requires_user_authorization" in safety_constraints
    requires_browser_auth = (
        pipeline_name in BROWSER_AUTH_PIPELINES
        or _is_browser_related(pipeline_name)
        or _is_browser_related(getattr(task_spec, "user_query", ""))
        and any(_is_browser_related(skill) for skill in required_skills)
        or bool(input_data.get("browser_profile"))
    )
    required_authorizations: list[dict[str, str]] = []
    errors: list[str] = []
    if requires_pipeline_auth or requires_browser_auth:
        reason = "pipeline_registry" if requires_pipeline_auth else "browser_execution_policy"
        required_authorizations.append({"type": "pipeline", "id": pipeline_name, "reason": reason})
        keys = ["authorized", pipeline_name, f"pipeline:{pipeline_name}"]
        if requires_browser_auth:
            keys.extend(["browser", "browser_tools", "browser_research_learning"])
        if not _has_flag(flags, keys):
            errors.append(f"pipeline requires user authorization: {pipeline_name}")
    skill_report = check_skill_authorization(required_skills, flags)
    errors.extend(skill_report.get("errors") or [])
    required_authorizations.extend(skill_report.get("required_authorizations") or [])
    return {
        "valid": not errors,
        "errors": errors,
        "requires_user_authorization": bool(required_authorizations),
        "missing_authorization": bool(errors),
        "required_authorizations": required_authorizations,
        "user_authorization_flags": flags,
        "pipeline_name": pipeline_name,
    }
