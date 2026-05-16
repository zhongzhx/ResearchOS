from __future__ import annotations

import os
from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    path = Path(value) if value else default
    return path if path.is_absolute() else get_repo_root() / path


def get_agent_data_dir() -> Path:
    return _path_from_env("RESEARCHOS_AGENT_DATA_DIR", get_repo_root() / "agent_data")


def get_runtime_dir() -> Path:
    return _path_from_env("RESEARCHOS_RUNTIME_DIR", get_repo_root() / "runtime")


def get_research_brain_dir() -> Path:
    return _path_from_env("RESEARCH_BRAIN_ROOT", get_agent_data_dir() / "research_brain")


def get_memoryos_dir() -> Path:
    return _path_from_env("RESEARCHOS_MEMORYOS_DIR", get_agent_data_dir() / "memoryos")


def get_research_tasks_dir() -> Path:
    return _path_from_env("RESEARCHOS_TASKS_ROOT", get_repo_root() / "data" / "research_tasks")


def get_generated_outputs_dir() -> Path:
    return _path_from_env("RESEARCHOS_GENERATED_OUTPUTS_DIR", get_repo_root() / "generated_outputs")


def ensure_runtime_dirs() -> dict[str, Path]:
    dirs = {
        "agent_data": get_agent_data_dir(),
        "runtime": get_runtime_dir(),
        "research_brain": get_research_brain_dir(),
        "memoryos": get_memoryos_dir(),
        "research_tasks": get_research_tasks_dir(),
        "generated_outputs": get_generated_outputs_dir(),
        "secrets": get_agent_data_dir() / "secrets",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
