from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec


SUPPORTED_TOOLS = ["rag_query", "pdf_parser", "file_reader", "file_writer", "csv_writer", "data_parser", "script_runner", "report_writer", "context_lookup"]


def list_available_tools() -> list[str]:
    return list(SUPPORTED_TOOLS)


def validate_allowed_tool(tool_name: str, task_spec: TaskSpec) -> dict[str, Any]:
    errors: list[str] = []
    if tool_name not in SUPPORTED_TOOLS:
        errors.append(f"unsupported tool: {tool_name}")
    if tool_name in set(task_spec.forbidden_tools or []):
        errors.append(f"forbidden tool requested: {tool_name}")
    if tool_name not in set(task_spec.allowed_tools or []):
        errors.append(f"tool not allowed by TaskSpec: {tool_name}")
    return {"valid": not errors, "errors": errors}


def _workspace(task_spec: TaskSpec) -> Path:
    base = Path(task_spec.input_data.get("workspace_dir") or Path.cwd() / "data" / "execution_tasks" / task_spec.task_id)
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def call_tool(tool_name: str, inputs: dict[str, Any], task_spec: TaskSpec) -> dict[str, Any]:
    allowed = validate_allowed_tool(tool_name, task_spec)
    if not allowed["valid"]:
        return {"ok": False, "tool_name": tool_name, "error": "; ".join(allowed["errors"]), "logs": [f"tool:{tool_name} rejected"]}
    try:
        if tool_name == "file_reader":
            path = Path(str(inputs.get("path") or "")).resolve()
            declared = {str(Path(item).resolve()) for item in task_spec.input_files}
            if str(path) not in declared:
                return {"ok": False, "tool_name": tool_name, "error": f"file not declared in TaskSpec.input_files: {path}", "logs": ["forbidden file access"]}
            return {"ok": True, "tool_name": tool_name, "content": path.read_text(encoding=inputs.get("encoding") or "utf-8"), "logs": [f"tool:file_reader path:{path}"]}

        if tool_name in {"file_writer", "report_writer"}:
            workspace = _workspace(task_spec)
            filename = str(inputs.get("filename") or ("report.md" if tool_name == "report_writer" else "output.txt"))
            path = (workspace / filename).resolve()
            if not _is_under(path, workspace):
                return {"ok": False, "tool_name": tool_name, "error": "output path escapes task workspace", "logs": ["blocked path traversal"]}
            path.write_text(str(inputs.get("content") or ""), encoding=inputs.get("encoding") or "utf-8")
            return {"ok": True, "tool_name": tool_name, "output_files": [str(path)], "logs": [f"tool:{tool_name} path:{path}"]}

        if tool_name == "csv_writer":
            workspace = _workspace(task_spec)
            path = (workspace / str(inputs.get("filename") or "output.csv")).resolve()
            if not _is_under(path, workspace):
                return {"ok": False, "tool_name": tool_name, "error": "output path escapes task workspace", "logs": ["blocked path traversal"]}
            rows = inputs.get("rows") if isinstance(inputs.get("rows"), list) else []
            with path.open("w", newline="", encoding="utf-8") as handle:
                if rows and isinstance(rows[0], dict):
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    writer = csv.writer(handle)
                    writer.writerows(rows)
            return {"ok": True, "tool_name": tool_name, "output_files": [str(path)], "logs": [f"tool:csv_writer path:{path}"]}

        if tool_name == "script_runner":
            command = inputs.get("command")
            if isinstance(command, str):
                return {"ok": False, "tool_name": tool_name, "error": "script_runner requires command as argv list", "logs": ["string command rejected"]}
            args = [str(item) for item in (command or [])]
            if not args:
                return {"ok": False, "tool_name": tool_name, "error": "missing command", "logs": ["missing command"]}
            cwd = str(inputs.get("cwd") or _workspace(task_spec))
            completed = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=int(inputs.get("timeout") or 30), check=False)
            return {
                "ok": completed.returncode == 0,
                "tool_name": tool_name,
                "command": args,
                "cwd": cwd,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "exit_code": completed.returncode,
                "logs": [f"tool:script_runner exit_code:{completed.returncode}"],
            }

        if tool_name == "context_lookup":
            return {"ok": True, "tool_name": tool_name, "context": task_spec.context_package, "logs": ["tool:context_lookup"]}

        if tool_name == "rag_query":
            return {
                "ok": True,
                "tool_name": tool_name,
                "sources": task_spec.context_package.get("relevant_sources", []),
                "chunks": task_spec.context_package.get("relevant_chunks", []),
                "logs": ["tool:rag_query adapter:context_package"],
            }

        if tool_name in {"pdf_parser", "data_parser"}:
            return {"ok": False, "tool_name": tool_name, "error": f"{tool_name} adapter is not connected yet", "logs": [f"tool:{tool_name} not_connected"]}
        return {"ok": False, "tool_name": tool_name, "error": f"unsupported tool: {tool_name}", "logs": []}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool_name": tool_name, "error": str(exc), "logs": [f"tool:{tool_name} failed"]}
