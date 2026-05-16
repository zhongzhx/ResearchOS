from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from .agent_prompt_rules import HIDDEN_CONTEXT_KEYS, USER_VISIBLE_ALLOWED_KEYS


def _repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root:
        return Path(repo_root).resolve()
    return Path(__file__).resolve().parents[3]


def _runtime_root(repo_root: str | Path | None = None) -> Path:
    return _repo_root(repo_root) / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime"


def _scripts_root(repo_root: str | Path | None = None) -> Path:
    return _repo_root(repo_root) / "backend" / "research_agent_runtime" / "scripts"


def _import_from_mvp(module_name: str, repo_root: str | Path | None = None) -> Any:
    scripts = _scripts_root(repo_root)
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module(module_name)


def locate_mvp_prompt_sources(repo_root: str | Path | None = None) -> dict[str, Any]:
    runtime = _runtime_root(repo_root)
    scripts = _scripts_root(repo_root)
    prompts = runtime / "prompts"
    zh = prompts / "zh"
    system_prompt = prompts / "researchos_agent_system_prompt.md"
    return {
        "runtime_root": str(runtime),
        "scripts_root": str(scripts),
        "prompt_root": str(prompts),
        "system_prompt_path": str(system_prompt),
        "system_prompt_exists": system_prompt.exists(),
        "zh_prompt_root": str(zh),
        "zh_prompt_files": [str(path) for path in sorted(zh.glob("*.md"))] if zh.exists() else [],
        "prompt_loader": str(scripts / "researchos_agent_prompt.py"),
        "prompt_router": str(scripts / "researchos_prompt_router.py"),
        "context_compiler": str(scripts / "research_context_compiler.py"),
    }


def load_mvp_system_prompt(repo_root: str | Path | None = None) -> str:
    module = _import_from_mvp("researchos_agent_prompt", repo_root)
    return str(module.load_researchos_system_prompt())


def load_mvp_prompt_router_config(repo_root: str | Path | None = None) -> dict[str, Any]:
    agent_prompt = _import_from_mvp("researchos_agent_prompt", repo_root)
    router = _import_from_mvp("researchos_prompt_router", repo_root)
    supported = sorted(set(getattr(router, "SUPPORTED_PROMPT_POLICIES", set()) or set(getattr(agent_prompt, "PROMPT_POLICY_STACKS", {}).keys())))
    return {
        "supported_policies": supported,
        "policy_aliases": dict(getattr(agent_prompt, "PROMPT_POLICY_ALIASES", {})),
        "policy_stacks": dict(getattr(agent_prompt, "PROMPT_POLICY_STACKS", {})),
        "task_prompt_policy": dict(getattr(router, "TASK_PROMPT_POLICY", {})),
        "skill_task_map": dict(getattr(router, "SKILL_TASK_MAP", {})),
        "core_skill_task_map": dict(getattr(router, "CORE_SKILL_TASK_MAP", {})),
    }


def _is_hidden_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in HIDDEN_CONTEXT_KEYS or any(marker in lowered for marker in HIDDEN_CONTEXT_KEYS)


def build_user_facing_prompt_context(**context: Any) -> dict[str, Any]:
    visible: dict[str, Any] = {}
    for key, value in context.items():
        if _is_hidden_key(str(key)):
            continue
        if key in USER_VISIBLE_ALLOWED_KEYS or isinstance(value, (str, int, float, bool, list, dict, type(None))):
            visible[key] = value
    return visible


def build_brain_agent_prompt_extension() -> str:
    return ""


def build_execution_agent_prompt_extension() -> str:
    return ""
