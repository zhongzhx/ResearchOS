from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.execution.runtime_adapter import is_sensitive_path, redact_payload, redact_text


SUPPORTED_TOOLS = ["rag_query", "pdf_parser", "file_reader", "file_writer", "csv_writer", "data_parser", "script_runner", "report_writer", "context_lookup"]
DEFAULT_ALLOWED_SCRIPT_MODULES = {"py_compile", "unittest", "pytest"}
DEFAULT_FORBIDDEN_COMMAND_PATTERNS = [
    "rm -rf",
    "del /f",
    "format ",
    "curl | bash",
    "curl -fs",
    "wget | sh",
    "wget -q",
    "invoke-webrequest",
    "iex",
    "invoke-expression",
    "git config",
]


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
    base = Path(task_spec.input_data.get("workspace_dir") or task_spec.input_data.get("workspace_base_dir") or Path.cwd() / "data" / "execution_tasks" / task_spec.task_id)
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _declared_inputs(task_spec: TaskSpec) -> set[str]:
    return {str(Path(item).resolve()) for item in task_spec.input_files or []}


def _validate_read_path(path: Path, task_spec: TaskSpec) -> list[str]:
    errors: list[str] = []
    workspace = _workspace(task_spec)
    resolved = path.resolve()
    if is_sensitive_path(resolved):
        errors.append(f"forbidden sensitive file access: {resolved}")
    if str(resolved) not in _declared_inputs(task_spec) and not _is_under(resolved, workspace):
        errors.append(f"file not declared in TaskSpec.input_files or task workspace: {resolved}")
    return errors


def _validate_write_path(path: Path, task_spec: TaskSpec) -> list[str]:
    errors: list[str] = []
    workspace = _workspace(task_spec)
    resolved = path.resolve()
    if is_sensitive_path(resolved):
        errors.append(f"forbidden sensitive file write: {resolved}")
    if not _is_under(resolved, workspace):
        errors.append("output path escapes task workspace")
    if str(resolved) in _declared_inputs(task_spec):
        errors.append(f"output attempts to overwrite input file: {resolved}")
    raw_data_dir = str(task_spec.input_data.get("raw_data_dir") or "").strip()
    if raw_data_dir and _is_under(resolved, Path(raw_data_dir).resolve()) and not bool(task_spec.input_data.get("allow_raw_data_modification")):
        errors.append("raw data modification is not allowed by TaskSpec")
    if "/data/raw/" in str(resolved).replace("\\", "/").lower() and not bool(task_spec.input_data.get("allow_raw_data_modification")):
        errors.append("raw data modification is not allowed by TaskSpec")
    return errors


def _safe_filename(value: str, default: str) -> str:
    filename = str(value or default).strip() or default
    return filename.replace("\\", "/")


def _not_connected_parser(tool_name: str) -> dict[str, Any]:
    if tool_name == "pdf_parser":
        message = "pdf_parser is not connected. Use compliant-literature-access or ingest-research-evidence pipeline."
    else:
        message = "data_parser is not connected. Use parse-scientific-data or data_analysis_to_narrative pipeline."
    return {
        "ok": False,
        "tool_name": tool_name,
        "status": "not_connected",
        "message": message,
        "error": message,
        "logs": [f"tool:{tool_name} status:not_connected"],
    }


def _script_cwd(inputs: dict[str, Any], task_spec: TaskSpec, workspace: Path) -> tuple[Path | None, str]:
    cwd = Path(str(inputs.get("cwd") or workspace)).resolve()
    if not _is_under(cwd, workspace):
        return None, f"script_runner cwd must stay inside task workspace: {cwd}"
    cwd.mkdir(parents=True, exist_ok=True)
    return cwd, ""


def _path_arg_under_workspace(arg: str, cwd: Path, workspace: Path) -> bool:
    if not arg or arg.startswith("-"):
        return True
    path = Path(arg)
    if not path.suffix:
        return True
    resolved = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
    return _is_under(resolved, workspace)


def _matches_explicit_allowed(joined: str, allowed_commands: list[str]) -> bool:
    if not allowed_commands:
        return False
    normalized = " ".join(joined.casefold().split())
    return any(normalized.startswith(" ".join(str(command).casefold().split())) for command in allowed_commands)


def _validate_script_command(args: list[str], inputs: dict[str, Any], task_spec: TaskSpec, cwd: Path, workspace: Path) -> list[str]:
    errors: list[str] = []
    joined = " ".join(args)
    joined_lower = joined.casefold()
    forbidden_commands = [*DEFAULT_FORBIDDEN_COMMAND_PATTERNS, *[str(item) for item in inputs.get("forbidden_commands") or []]]
    for pattern in forbidden_commands:
        if str(pattern).casefold() in joined_lower:
            errors.append(f"forbidden command pattern: {pattern}")
    if any(is_sensitive_path(arg) for arg in args):
        errors.append("script_runner command references a forbidden sensitive path")
    if not bool(inputs.get("allow_network")) and any(str(arg).startswith(("http://", "https://")) for arg in args):
        errors.append("script_runner command references an unknown remote endpoint")
    allowed_commands = [str(item) for item in inputs.get("allowed_commands") or []]
    if _matches_explicit_allowed(joined, allowed_commands):
        return errors

    python_names = {"python", "python.exe", "python3", "python3.exe", Path(sys.executable).name.casefold()}
    executable = Path(args[0]).name.casefold()
    if executable not in python_names:
        errors.append("script_runner only allows Python commands by default")
        return errors
    if len(args) < 2:
        errors.append("script_runner Python command requires a script or -m module")
        return errors
    if args[1] == "-c":
        errors.append("script_runner rejects inline Python code; provide a workspace script.py")
        return errors
    if args[1] == "-m":
        module = args[2] if len(args) > 2 else ""
        if module not in DEFAULT_ALLOWED_SCRIPT_MODULES:
            errors.append(f"python -m module is not allowed: {module}")
        for arg in args[3:]:
            if not _path_arg_under_workspace(arg, cwd, workspace):
                errors.append(f"script_runner path argument escapes task workspace: {arg}")
        return errors

    script = Path(args[1])
    resolved_script = (cwd / script).resolve() if not script.is_absolute() else script.resolve()
    if script.suffix != ".py":
        errors.append("script_runner only allows Python script files by default")
    if not _is_under(resolved_script, workspace):
        errors.append(f"script_runner script must stay inside task workspace: {resolved_script}")
    if not resolved_script.exists():
        errors.append(f"script_runner script does not exist: {resolved_script}")
    for arg in args[2:]:
        if not _path_arg_under_workspace(arg, cwd, workspace):
            errors.append(f"script_runner path argument escapes task workspace: {arg}")
    return errors


def call_tool(tool_name: str, inputs: dict[str, Any], task_spec: TaskSpec) -> dict[str, Any]:
    allowed = validate_allowed_tool(tool_name, task_spec)
    if not allowed["valid"]:
        return {"ok": False, "tool_name": tool_name, "error": "; ".join(allowed["errors"]), "logs": [f"tool:{tool_name} rejected"]}
    try:
        if tool_name == "file_reader":
            path = Path(str(inputs.get("path") or "")).resolve()
            path_errors = _validate_read_path(path, task_spec)
            if path_errors:
                return {"ok": False, "tool_name": tool_name, "error": "; ".join(path_errors), "logs": ["forbidden file access"]}
            content = redact_text(path.read_text(encoding=inputs.get("encoding") or "utf-8"))
            return {"ok": True, "tool_name": tool_name, "content": content, "logs": [f"tool:file_reader path:{path}"]}

        if tool_name in {"file_writer", "report_writer"}:
            workspace = _workspace(task_spec)
            filename = _safe_filename(str(inputs.get("filename") or ""), "report.md" if tool_name == "report_writer" else "output.txt")
            path = (workspace / filename).resolve()
            path_errors = _validate_write_path(path, task_spec)
            if path_errors:
                return {"ok": False, "tool_name": tool_name, "error": "; ".join(path_errors), "logs": ["blocked unsafe file write"]}
            path.write_text(str(inputs.get("content") or ""), encoding=inputs.get("encoding") or "utf-8")
            return {"ok": True, "tool_name": tool_name, "output_files": [str(path)], "logs": [f"tool:{tool_name} path:{path}"]}

        if tool_name == "csv_writer":
            workspace = _workspace(task_spec)
            path = (workspace / _safe_filename(str(inputs.get("filename") or ""), "output.csv")).resolve()
            path_errors = _validate_write_path(path, task_spec)
            if path_errors:
                return {"ok": False, "tool_name": tool_name, "error": "; ".join(path_errors), "logs": ["blocked unsafe csv write"]}
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
            workspace = _workspace(task_spec)
            cwd_path, cwd_error = _script_cwd(inputs, task_spec, workspace)
            if cwd_error or cwd_path is None:
                return {"ok": False, "tool_name": tool_name, "error": cwd_error, "logs": ["script_runner cwd rejected"]}
            command_errors = _validate_script_command(args, inputs, task_spec, cwd_path, workspace)
            if command_errors:
                return {"ok": False, "tool_name": tool_name, "error": "; ".join(command_errors), "logs": ["script_runner command rejected"]}
            timeout_seconds = max(1, min(int(inputs.get("timeout_seconds") or inputs.get("timeout") or 30), 120))
            max_output_chars = max(100, min(int(inputs.get("max_output_chars") or 4000), 100000))
            completed = subprocess.run(args, cwd=str(cwd_path), capture_output=True, text=True, timeout=timeout_seconds, check=False)
            return {
                "ok": completed.returncode == 0,
                "tool_name": tool_name,
                "command": args,
                "cwd": str(cwd_path),
                "stdout": redact_text(completed.stdout, max_chars=max_output_chars),
                "stderr": redact_text(completed.stderr, max_chars=max_output_chars),
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
            return _not_connected_parser(tool_name)
        return {"ok": False, "tool_name": tool_name, "error": f"unsupported tool: {tool_name}", "logs": []}
    except Exception as exc:  # noqa: BLE001
        return redact_payload({"ok": False, "tool_name": tool_name, "error": str(exc), "logs": [f"tool:{tool_name} failed"]})
