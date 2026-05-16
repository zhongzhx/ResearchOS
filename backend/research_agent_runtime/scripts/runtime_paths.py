from __future__ import annotations

import warnings
from pathlib import Path


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "skills" / "researchos_skill_library").exists():
            return candidate
    return Path(__file__).resolve().parents[3]


def skill_library_root() -> Path:
    return repo_root() / "skills" / "researchos_skill_library"


def core_runtime_memory_root() -> Path:
    return skill_library_root() / "01_core_runtime_memory"


def legacy_runtime_skill_root() -> Path:
    return core_runtime_memory_root() / "research-agent-runtime"


def runtime_skill_root() -> Path:
    return backend_runtime_root()


def backend_runtime_root() -> Path:
    return repo_root() / "backend" / "research_agent_runtime"


def runtime_scripts_root() -> Path:
    return backend_runtime_root() / "scripts"


def backend_prompt_root() -> Path:
    return backend_runtime_root() / "prompts"


def legacy_prompt_root() -> Path:
    return legacy_runtime_skill_root() / "prompts"


def prompt_root() -> Path:
    prompts = backend_prompt_root()
    if prompts.exists():
        return prompts
    legacy = legacy_prompt_root()
    if legacy.exists():
        warnings.warn(
            f"Deprecated ResearchOS prompt path fallback in use: {legacy}. "
            f"Move prompts to {prompts}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy
    return prompts
