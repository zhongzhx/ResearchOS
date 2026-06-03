from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROJECT_DIRECTORIES = (
    "inbox",
    "papers",
    "papers/pdfs",
    "papers/manual_queue",
    "kb",
    "rag",
    "chats",
    "workflows",
    "runs",
    "artifacts",
    "artifacts/markdown",
    "artifacts/pptx",
    "artifacts/figures",
    "artifacts/tables",
    "artifacts/data",
    "logs",
    "tmp",
    "manifests",
)

# Keep these directories for older adapters while all new writes use the canonical layout.
COMPATIBILITY_DIRECTORIES = (
    "uploads",
    "knowledge",
    "artifacts/presentations",
    "artifacts/other",
)

ARTIFACT_KINDS = ("markdown", "pptx", "figures", "tables", "data", "presentations", "other")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_segment(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", _clean(value)).strip("._-")
    return normalized or fallback


class ProjectWorkspace:
    def __init__(self, agent_root: Path, project_id: str) -> None:
        self.agent_root = Path(agent_root)
        self.project_id = _safe_segment(project_id, "unnamed_project")
        self.root = self.agent_root / "projects" / self.project_id

    def paths(self) -> dict[str, str]:
        artifacts = self.root / "artifacts"
        paths = {
            "root_path": str(self.root),
            "inbox_path": str(self.root / "inbox"),
            "papers_path": str(self.root / "papers"),
            "pdf_path": str(self.root / "papers" / "pdfs"),
            "manual_queue_path": str(self.root / "papers" / "manual_queue"),
            "kb_path": str(self.root / "kb"),
            "rag_path": str(self.root / "rag"),
            "chats_path": str(self.root / "chats"),
            "workflows_path": str(self.root / "workflows"),
            "runs_path": str(self.root / "runs"),
            "artifact_path": str(artifacts),
            "markdown_artifacts_path": str(artifacts / "markdown"),
            "pptx_artifacts_path": str(artifacts / "pptx"),
            "figures_artifacts_path": str(artifacts / "figures"),
            "tables_artifacts_path": str(artifacts / "tables"),
            "data_artifacts_path": str(artifacts / "data"),
            "logs_path": str(self.root / "logs"),
            "tmp_path": str(self.root / "tmp"),
            "manifests_path": str(self.root / "manifests"),
            "manifest_path": str(self.root / "project_manifest.json"),
            "debug_log_path": str(self.root / "logs" / "project_debug.log"),
        }
        # Compatibility aliases used by the MVP schema and earlier UI code.
        paths.update(
            {
                "root_dir": paths["root_path"],
                "uploads_dir": paths["inbox_path"],
                "papers_dir": paths["pdf_path"],
                "pdf_dir": paths["pdf_path"],
                "knowledge_dir": paths["kb_path"],
                "kb_dir": paths["kb_path"],
                "rag_dir": paths["rag_path"],
                "artifacts_dir": paths["artifact_path"],
                "runs_dir": paths["runs_path"],
                "markdown_artifacts_dir": paths["markdown_artifacts_path"],
                "pptx_artifacts_dir": paths["pptx_artifacts_path"],
                "figures_artifacts_dir": paths["figures_artifacts_path"],
                "tables_artifacts_dir": paths["tables_artifacts_path"],
                "data_artifacts_dir": paths["data_artifacts_path"],
                "presentations_artifacts_dir": str(artifacts / "presentations"),
                "other_artifacts_dir": str(artifacts / "other"),
            }
        )
        return paths

    def ensure(self) -> dict[str, str]:
        for relative in (*PROJECT_DIRECTORIES, *COMPATIBILITY_DIRECTORIES):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        return self.paths()

    def write_manifest(self, project: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state or {}
        paths = self.ensure()
        literature = state.get("literature") if isinstance(state.get("literature"), dict) else {}
        data = state.get("data") if isinstance(state.get("data"), dict) else {}
        artifacts = state.get("artifact_summary") if isinstance(state.get("artifact_summary"), dict) else {}
        workflow_run_count = int(state.get("workflow_run_count") or 0)
        updated_at = _clean(state.get("updated_at") or project.get("updated_at") or project.get("created_at"))
        manifest = {
            "display_name": _clean(project.get("display_name") or project.get("project_name") or project.get("title")),
            "project_id": _clean(project.get("project_id") or project.get("id")),
            "created_at": _clean(project.get("created_at")),
            "updated_at": updated_at,
            "root_path": paths["root_path"],
            "kb_path": paths["kb_path"],
            "rag_path": paths["rag_path"],
            "artifact_path": paths["artifact_path"],
            "file_count": int(state.get("file_count") or data.get("data_files_count") or 0),
            "reference_count": int(state.get("reference_count") or literature.get("references_count") or 0),
            "kb_entry_count": int(state.get("kb_entry_count") or literature.get("kb_entries_count") or 0),
            "rag_chunk_count": int(state.get("rag_chunk_count") or literature.get("chunks_count") or 0),
            "workflow_run_count": workflow_run_count,
            "last_activity_at": _clean(state.get("last_activity_at") or updated_at),
        }
        manifest_path = Path(paths["manifest_path"])
        pending_path = manifest_path.with_suffix(".json.tmp")
        pending_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        pending_path.replace(manifest_path)
        # Earlier local builds used workspace.json. Keep a read-only compatibility copy.
        (self.root / "workspace.json").write_text(json.dumps({**manifest, "paths": paths}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return {**manifest, "paths": paths, "manifest_path": str(manifest_path)}


def canonical_project_paths(agent_root: Path, display_name: str = "", project_id: str = "") -> dict[str, str]:
    del display_name
    return ProjectWorkspace(Path(agent_root), project_id).paths()


def ensure_project_workspace(agent_root: Path, project: dict[str, Any]) -> dict[str, str]:
    return ProjectWorkspace(Path(agent_root), _clean(project.get("project_id") or project.get("id"))).ensure()


def _artifact_kind(filename: str, requested_kind: str = "") -> str:
    requested_kind = _clean(requested_kind)
    if requested_kind in ARTIFACT_KINDS:
        return requested_kind
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".txt", ".rst"}:
        return "markdown"
    if suffix in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".pdf"}:
        return "figures"
    if suffix in {".pptx", ".ppt"}:
        return "pptx"
    if suffix in {".csv", ".tsv", ".xlsx", ".xls"}:
        return "tables"
    if suffix in {".json"}:
        return "data"
    return "other"


def _safe_filename(value: str, fallback: str = "artifact.bin") -> str:
    name = Path(_clean(value) or fallback).name
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(" .-_")
    return normalized or fallback


def archive_workspace_file(
    agent_root: Path,
    project: dict[str, Any],
    *,
    filename: str,
    content: str | bytes,
    artifact_kind: str = "",
) -> dict[str, str]:
    paths = ensure_project_workspace(agent_root, project)
    kind = _artifact_kind(filename, artifact_kind)
    directory = Path(paths[f"{kind}_artifacts_dir"])
    content_bytes = content if isinstance(content, bytes) else str(content).encode("utf-8")
    safe_name = _safe_filename(filename)
    path = directory / safe_name
    if path.exists() and path.read_bytes() != content_bytes:
        digest = hashlib.sha256(content_bytes).hexdigest()[:10]
        path = directory / f"{path.stem}-{digest}{path.suffix}"
    path.write_bytes(content_bytes)
    return {"path": str(path), "filename": path.name, "artifact_kind": kind}


def _ingest_summary(state: dict[str, Any]) -> dict[str, Any]:
    literature = state.get("literature") if isinstance(state.get("literature"), dict) else {}
    tasks = state.get("tasks") if isinstance(state.get("tasks"), dict) else {}
    all_tasks = [*(tasks.get("running") or []), *(tasks.get("failed") or []), *(tasks.get("completed") or [])]
    harvests = [item for item in all_tasks if item.get("task_type") == "literature_harvest"]
    current = harvests[0] if harvests else {}
    progress = current.get("progress") if isinstance(current.get("progress"), dict) else {}
    if current.get("status") in {"running", "pending", "waiting_approval"}:
        status = "running"
    elif int(literature.get("kb_entries_count") or 0) > 0:
        status = "indexed"
    elif current.get("status") == "failed":
        status = "failed"
    else:
        status = "not_started"
    return {
        "status": status,
        "current_stage": progress.get("current_stage") or "",
        "downloaded_count": int(progress.get("downloaded") or 0),
        "indexed_count": int(progress.get("indexed") or 0),
        "failed_count": int(progress.get("failed") or 0),
    }


def write_project_workspace_manifest(agent_root: Path, project: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    manifest = ProjectWorkspace(Path(agent_root), _clean(project.get("project_id") or project.get("id"))).write_manifest(project, state)
    literature = state.get("literature") if isinstance(state.get("literature"), dict) else {}
    rag = state.get("rag") if isinstance(state.get("rag"), dict) else {}
    manifest.update(
        {
            "status": _clean(project.get("status")) or "active",
            "kb": {
                "ready": int(manifest["kb_entry_count"]) > 0,
                "references_count": int(manifest["reference_count"]),
                "chunks_count": int(manifest["rag_chunk_count"]),
                "entries_count": int(manifest["kb_entry_count"]),
            },
            "ingest": _ingest_summary(state),
            "rag": {
                "available": bool(rag.get("available")),
                "default_scope": "current_project",
                "cross_project_requires_explicit_opt_in": True,
            },
            "counts": {
                "files": int(manifest["file_count"]),
                "artifacts": int((state.get("artifact_summary") or {}).get("total_count") or 0),
                "workflow_runs": int(manifest["workflow_run_count"]),
            },
            "literature": literature,
        }
    )
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    Path(manifest["manifest_path"]).write_text(serialized, encoding="utf-8")
    Path(manifest["paths"]["root_path"], "workspace.json").write_text(serialized, encoding="utf-8")
    return manifest
