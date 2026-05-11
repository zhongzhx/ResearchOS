from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def runtime_skill_dir() -> Path:
    return repo_root() / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime"


def scripts_dir() -> Path:
    return runtime_skill_dir() / "scripts"


def import_research_os_mvp() -> Any:
    path = scripts_dir()
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    import research_os_mvp  # type: ignore

    return research_os_mvp


def default_agent_root() -> Path:
    return Path(os.environ.get("RESEARCHOS_AGENT_ROOT") or repo_root() / "agent_data")
