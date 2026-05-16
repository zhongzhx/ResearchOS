from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Callable

from backend.researchos.prompts.mvp_prompt_adapter import locate_mvp_prompt_sources
from backend.researchos.settings.secret_store import redact_secrets_in_obj


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def mvp_runtime_root() -> Path:
    return repo_root() / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime"


def mvp_scripts_root() -> Path:
    return repo_root() / "backend" / "research_agent_runtime" / "scripts"


def mvp_api_entrypoint() -> Path:
    return mvp_scripts_root() / "research_agent_api.py"


def import_mvp_module(module_name: str = "research_os_mvp") -> Any:
    scripts = mvp_scripts_root()
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module(module_name)


def with_mvp_agent_root(agent_root: str | Path, callback: Callable[[], Any]) -> Any:
    previous_root = os.environ.get("RESEARCHOS_AGENT_ROOT")
    previous_data = os.environ.get("RESEARCHOS_AGENT_DATA_DIR")
    root = str(Path(agent_root).resolve())
    os.environ["RESEARCHOS_AGENT_ROOT"] = root
    os.environ["RESEARCHOS_AGENT_DATA_DIR"] = root
    try:
        return callback()
    finally:
        if previous_root is None:
            os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        else:
            os.environ["RESEARCHOS_AGENT_ROOT"] = previous_root
        if previous_data is None:
            os.environ.pop("RESEARCHOS_AGENT_DATA_DIR", None)
        else:
            os.environ["RESEARCHOS_AGENT_DATA_DIR"] = previous_data


def get_mvp_runtime_state(agent_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(agent_root or os.environ.get("RESEARCHOS_AGENT_ROOT") or repo_root() / "agent_data").resolve()
    return {
        "mvp_available": mvp_api_entrypoint().exists() and (mvp_scripts_root() / "research_os_mvp.py").exists(),
        "agent_root": str(root),
        "data_root": str(root),
        "runtime_root": str(mvp_runtime_root()),
        "scripts_root": str(mvp_scripts_root()),
        "api_entrypoint": str(mvp_api_entrypoint()),
        "prompt_sources": locate_mvp_prompt_sources(repo_root()),
    }


def list_mvp_projects(agent_root: str | Path) -> dict[str, Any]:
    mvp = import_mvp_module("research_os_mvp")
    root = Path(agent_root)
    root.mkdir(parents=True, exist_ok=True)
    return redact_secrets_in_obj({"ok": True, "projects": mvp.list_projects(root)})


def call_mvp_agent_chat(agent_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    mvp = import_mvp_module("research_os_mvp")
    return redact_secrets_in_obj(mvp.agent_chat(Path(agent_root), payload))


def call_mvp_memory_context(agent_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    canonical = import_mvp_module("research_memory_canonical")
    return redact_secrets_in_obj(canonical.build_research_memory_context(Path(agent_root), payload))


def call_mvp_rag_query(agent_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    mvp = import_mvp_module("research_os_mvp")
    return redact_secrets_in_obj(mvp.query_research_rag(Path(agent_root), payload))
