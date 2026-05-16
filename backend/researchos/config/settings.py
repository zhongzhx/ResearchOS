from __future__ import annotations

from dataclasses import dataclass

from .env_loader import get_bool_env, get_env, get_int_env, load_env_file


@dataclass(frozen=True)
class ResearchOSSettings:
    host: str
    port: int
    dual_agent_api_enabled: bool
    product_api_enabled: bool
    memoryos_enabled: bool
    task_lifecycle_enabled: bool
    log_level: str


def load_settings() -> ResearchOSSettings:
    load_env_file()
    return ResearchOSSettings(
        host=str(get_env("RESEARCHOS_HOST", "127.0.0.1")),
        port=get_int_env("RESEARCHOS_PORT", 8765),
        dual_agent_api_enabled=get_bool_env("RESEARCHOS_DUAL_AGENT_API_ENABLED", False),
        product_api_enabled=get_bool_env("RESEARCHOS_PRODUCT_API_ENABLED", True),
        memoryos_enabled=get_bool_env("RESEARCHOS_MEMORYOS_ENABLED", True),
        task_lifecycle_enabled=get_bool_env("RESEARCHOS_TASK_LIFECYCLE_ENABLED", True),
        log_level=str(get_env("LOG_LEVEL", "INFO")),
    )
