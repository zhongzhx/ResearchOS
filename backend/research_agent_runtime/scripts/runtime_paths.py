from __future__ import annotations

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


def runtime_skill_root() -> Path:
    return core_runtime_memory_root() / "research-agent-runtime"


def runtime_scripts_root() -> Path:
    return repo_root() / "backend" / "research_agent_runtime" / "scripts"


def prompt_root() -> Path:
    return runtime_skill_root() / "prompts"
