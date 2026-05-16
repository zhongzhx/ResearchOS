"""Prompt adapters that reuse the MVP ResearchOS prompt stack."""

from .mvp_prompt_adapter import (
    build_brain_agent_prompt_extension,
    build_execution_agent_prompt_extension,
    build_user_facing_prompt_context,
    load_mvp_prompt_router_config,
    load_mvp_system_prompt,
    locate_mvp_prompt_sources,
)

__all__ = [
    "build_brain_agent_prompt_extension",
    "build_execution_agent_prompt_extension",
    "build_user_facing_prompt_context",
    "load_mvp_prompt_router_config",
    "load_mvp_system_prompt",
    "locate_mvp_prompt_sources",
]
