from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from pathlib import Path
from typing import Any

from .project_workspace import ProjectWorkspace


SOURCE_DIRECTORIES = {
    "upload": "inbox_path",
    "literature_pdf": "pdf_path",
    "manual_pdf": "manual_queue_path",
    "generated_markdown": "markdown_artifacts_path",
    "generated_pptx": "pptx_artifacts_path",
    "generated_figure": "figures_artifacts_path",
    "generated_table": "tables_artifacts_path",
    "generated_data": "data_artifacts_path",
    "workflow_run_artifact": "data_artifacts_path",
    "kb_index": "kb_path",
    "rag_chunk": "rag_path",
    "report": "markdown_artifacts_path",
}

PREVIEW_TYPES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".csv": "table",
    ".tsv": "table",
    ".xlsx": "table",
    ".xls": "table",
    ".svg": "figure",
    ".png": "figure",
    ".jpg": "figure",
    ".jpeg": "figure",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".json": "data",
}


def _ros() -> Any:
    from backend.researchos.execution.runtime_adapter import import_research_os_mvp

    return import_research_os_mvp()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_filename(value: str) -> str:
    raw = _clean(value)
    if not raw or Path(raw).name != raw or raw in {".", ".."} or ".." in Path(raw).parts:
        raise ValueError("safe filename is required")
    normalized = "".join(char if char.isalnum() or char in "._-" else "-" for char in raw).strip(" .-_")
    if not normalized:
        raise ValueError("safe filename is required")
    return normalized


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _artifact_id(project_id: str, source_type: str, sha256: str, display_name: str) -> str:
    digest = hashlib.sha256(f"{project_id}|{source_type}|{sha256}|{display_name}".encode("utf-8")).hexdigest()
    return f"artifact_{digest[:24]}"


def _mime_type(filename: str, requested: str = "") -> str:
    return _clean(requested) or mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _decode(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else json.loads(row.get("metadata_json") or "{}")
    path = _clean(row.get("absolute_path") or row.get("path"))
    display_name = _clean(row.get("display_name") or row.get("title") or Path(path).name)
    extension = _clean(row.get("extension") or Path(display_name).suffix.lower())
    return {
        **row,
        "artifact_id": _clean(row.get("artifact_id")),
        "project_id": _clean(row.get("project_id")),
        "run_id": _clean(row.get("run_id") or row.get("skill_run_id")),
        "source_type": _clean(row.get("registry_source_type") or row.get("source_object_type")),
        "display_name": display_name,
        "original_name": _clean(row.get("original_name") or display_name),
        "mime_type": _clean(row.get("mime_type") or _mime_type(display_name)),
        "extension": extension,
        "relative_path": _clean(row.get("relative_path")),
        "absolute_path": path,
        "path": path,
        "sha256": _clean(row.get("sha256")),
        "size_bytes": int(row.get("size_bytes") or 0),
        "status": _clean(row.get("status")) or "registered",
        "ingest_status": _clean(row.get("ingest_status")) or "registered",
        "kb_status": _clean(row.get("kb_status")) or "not_indexed",
        "rag_status": _clean(row.get("rag_status")) or "not_indexed",
        "source_reference_id": _clean(row.get("source_reference_id")),
        "metadata": metadata,
        "preview_type": PREVIEW_TYPES.get(extension, "file"),
    }


class FileArtifactRegistry:
    def __init__(self, agent_root: Path) -> None:
        self.agent_root = Path(agent_root).resolve()

    def _project(self, project_id: str) -> tuple[dict[str, Any], ProjectWorkspace]:
        ros = _ros()
        project_id = ros.require_project_id(project_id)
        project = ros.require_existing_project(self.agent_root, project_id)
        workspace = ProjectWorkspace(self.agent_root, project_id)
        workspace.ensure()
        return project, workspace

    def _target_dir(self, workspace: ProjectWorkspace, source_type: str) -> Path:
        paths = workspace.paths()
        key = SOURCE_DIRECTORIES.get(source_type, "data_artifacts_path")
        directory = Path(paths[key]).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        if not _is_under(directory, workspace.root):
            raise ValueError("artifact directory escapes project workspace")
        return directory

    def _stored_path(self, directory: Path, display_name: str, content: bytes) -> Path:
        safe_name = _safe_filename(display_name)
        candidate = directory / safe_name
        if candidate.exists() and candidate.read_bytes() != content:
            digest = _sha256(content)[:10]
            candidate = directory / f"{candidate.stem}-{digest}{candidate.suffix}"
        return candidate.resolve()

    def register_content(
        self,
        *,
        project_id: str,
        source_type: str,
        display_name: str,
        content: str | bytes,
        run_id: str = "",
        status: str = "registered",
        ingest_status: str = "registered",
        kb_status: str = "not_indexed",
        rag_status: str = "not_indexed",
        source_reference_id: str = "",
        metadata: dict[str, Any] | None = None,
        mime_type: str = "",
    ) -> dict[str, Any]:
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8")
        _, workspace = self._project(project_id)
        directory = self._target_dir(workspace, _clean(source_type))
        stored_path = self._stored_path(directory, display_name, raw)
        if not _is_under(stored_path, workspace.root):
            raise ValueError("artifact path escapes project workspace")
        if not stored_path.exists():
            stored_path.write_bytes(raw)
        return self._register_row(
            project_id=project_id,
            source_type=source_type,
            display_name=display_name,
            absolute_path=stored_path,
            content=raw,
            run_id=run_id,
            status=status,
            ingest_status=ingest_status,
            kb_status=kb_status,
            rag_status=rag_status,
            source_reference_id=source_reference_id,
            metadata=metadata,
            mime_type=mime_type,
        )

    def register_file(
        self,
        *,
        project_id: str,
        source_type: str,
        file_path: str | Path,
        display_name: str = "",
        run_id: str = "",
        status: str = "registered",
        ingest_status: str = "registered",
        kb_status: str = "not_indexed",
        rag_status: str = "not_indexed",
        source_reference_id: str = "",
        metadata: dict[str, Any] | None = None,
        mime_type: str = "",
        copy_into_registry: bool = True,
        allow_external_source: bool = False,
    ) -> dict[str, Any]:
        source = Path(file_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"artifact file not found: {source}")
        _, workspace = self._project(project_id)
        if not allow_external_source and not _is_under(source, workspace.root):
            raise ValueError("artifact source path must stay inside the project workspace")
        content = source.read_bytes()
        name = display_name or source.name
        if copy_into_registry:
            target = self._stored_path(self._target_dir(workspace, _clean(source_type)), name, content)
            if not target.exists():
                shutil.copyfile(source, target)
        else:
            target = source
        if not _is_under(target, workspace.root):
            raise ValueError("artifact path escapes project workspace")
        return self._register_row(
            project_id=project_id,
            source_type=source_type,
            display_name=name,
            absolute_path=target,
            content=content,
            run_id=run_id,
            status=status,
            ingest_status=ingest_status,
            kb_status=kb_status,
            rag_status=rag_status,
            source_reference_id=source_reference_id,
            metadata=metadata,
            mime_type=mime_type,
        )

    def _register_row(
        self,
        *,
        project_id: str,
        source_type: str,
        display_name: str,
        absolute_path: Path,
        content: bytes,
        run_id: str,
        status: str,
        ingest_status: str,
        kb_status: str,
        rag_status: str,
        source_reference_id: str,
        metadata: dict[str, Any] | None,
        mime_type: str,
    ) -> dict[str, Any]:
        ros = _ros()
        _, workspace = self._project(project_id)
        digest = _sha256(content)
        conn = ros.connect(self.agent_root)
        duplicate = conn.execute(
            "SELECT * FROM artifacts WHERE project_id=? AND sha256=? AND registry_source_type=? AND status!='deleted' LIMIT 1",
            (project_id, digest, source_type),
        ).fetchone()
        if duplicate:
            conn.close()
            return _decode(dict(duplicate))
        safe_name = _safe_filename(display_name)
        relative_path = str(absolute_path.resolve().relative_to(workspace.root.resolve())).replace("\\", "/")
        artifact_id = _artifact_id(project_id, source_type, digest, relative_path)
        timestamp = ros.now()
        row = {
            "artifact_id": artifact_id,
            "project_id": project_id,
            "task_id": "",
            "skill_run_id": run_id,
            "run_id": run_id,
            "type": source_type,
            "title": safe_name,
            "path": str(absolute_path),
            "source_skill_run_id": run_id,
            "source_object_type": source_type,
            "source_object_id": source_reference_id or artifact_id,
            "status": status,
            "metadata_json": ros.json_dumps(metadata or {}),
            "created_at": timestamp,
            "updated_at": timestamp,
            "registry_source_type": source_type,
            "display_name": safe_name,
            "original_name": display_name,
            "mime_type": _mime_type(safe_name, mime_type),
            "extension": Path(safe_name).suffix.lower(),
            "relative_path": relative_path,
            "absolute_path": str(absolute_path),
            "sha256": digest,
            "size_bytes": len(content),
            "ingest_status": ingest_status,
            "kb_status": kb_status,
            "rag_status": rag_status,
            "source_reference_id": source_reference_id,
        }
        conn.execute(
            """
            INSERT INTO artifacts(
              artifact_id, project_id, task_id, skill_run_id, run_id, type, title, path,
              source_skill_run_id, source_object_type, source_object_id, status, metadata_json,
              created_at, updated_at, registry_source_type, display_name, original_name,
              mime_type, extension, relative_path, absolute_path, sha256, size_bytes,
              ingest_status, kb_status, rag_status, source_reference_id
            ) VALUES (
              :artifact_id, :project_id, :task_id, :skill_run_id, :run_id, :type, :title, :path,
              :source_skill_run_id, :source_object_type, :source_object_id, :status, :metadata_json,
              :created_at, :updated_at, :registry_source_type, :display_name, :original_name,
              :mime_type, :extension, :relative_path, :absolute_path, :sha256, :size_bytes,
              :ingest_status, :kb_status, :rag_status, :source_reference_id
            )
            """,
            row,
        )
        conn.commit()
        saved = conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        conn.close()
        return _decode(dict(saved) if saved else row)

    def list(self, project_id: str, *, source_type: str = "", include_deleted: bool = False) -> list[dict[str, Any]]:
        ros = _ros()
        self._project(project_id)
        clauses = ["project_id=?"]
        params: list[Any] = [project_id]
        if source_type:
            clauses.append("registry_source_type=?")
            params.append(source_type)
        if not include_deleted:
            clauses.append("status!='deleted'")
        conn = ros.connect(self.agent_root)
        rows = conn.execute(f"SELECT * FROM artifacts WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC", params).fetchall()
        conn.close()
        return [_decode(dict(row)) for row in rows]

    def get(self, project_id: str, artifact_id: str, *, include_deleted: bool = True) -> dict[str, Any]:
        ros = _ros()
        self._project(project_id)
        clauses = ["project_id=?", "artifact_id=?"]
        if not include_deleted:
            clauses.append("status!='deleted'")
        conn = ros.connect(self.agent_root)
        row = conn.execute(f"SELECT * FROM artifacts WHERE {' AND '.join(clauses)}", (project_id, artifact_id)).fetchone()
        conn.close()
        if not row:
            raise KeyError("artifact not found")
        return _decode(dict(row))

    def update_ingest_status(
        self,
        project_id: str,
        artifact_id: str,
        ingest_status: str,
        *,
        kb_status: str | None = None,
        rag_status: str | None = None,
    ) -> dict[str, Any]:
        ros = _ros()
        self.get(project_id, artifact_id)
        updates = ["ingest_status=?", "status=?", "updated_at=?"]
        params: list[Any] = [ingest_status, ingest_status, ros.now()]
        if kb_status is not None:
            updates.append("kb_status=?")
            params.append(kb_status)
        if rag_status is not None:
            updates.append("rag_status=?")
            params.append(rag_status)
        params.extend([project_id, artifact_id])
        conn = ros.connect(self.agent_root)
        conn.execute(f"UPDATE artifacts SET {', '.join(updates)} WHERE project_id=? AND artifact_id=?", params)
        conn.commit()
        conn.close()
        return self.get(project_id, artifact_id)

    def delete(self, project_id: str, artifact_id: str, *, physical_delete: bool = False) -> dict[str, Any]:
        ros = _ros()
        artifact = self.get(project_id, artifact_id)
        conn = ros.connect(self.agent_root)
        conn.execute("UPDATE artifacts SET status='deleted', updated_at=? WHERE project_id=? AND artifact_id=?", (ros.now(), project_id, artifact_id))
        conn.commit()
        conn.close()
        if physical_delete:
            _, workspace = self._project(project_id)
            path = Path(artifact["absolute_path"])
            if path.exists() and _is_under(path, workspace.root):
                path.unlink()
        return self.get(project_id, artifact_id)

    def open_info(self, project_id: str, artifact_id: str) -> dict[str, Any]:
        artifact = self.get(project_id, artifact_id)
        return {
            "artifact_id": artifact["artifact_id"],
            "project_id": artifact["project_id"],
            "display_name": artifact["display_name"],
            "path": artifact["absolute_path"],
            "mime_type": artifact["mime_type"],
            "preview_type": artifact["preview_type"],
            "open_hint": "Use the local desktop client to preview or open this project artifact.",
            "status": artifact["status"],
        }
