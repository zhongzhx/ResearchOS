from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_protocol import ExecutionResult, TaskSpec, validate_context_isolation
from backend.researchos.execution.execution_result_validator import validate_execution_result
from backend.researchos.execution.runtime_adapter import default_agent_root, import_research_os_mvp
from backend.researchos.execution.skill_dispatcher import validate_required_skills
from backend.researchos.execution.task_runner import build_execution_plan, collect_task_outputs, run_execution_plan
from backend.researchos.execution.tool_dispatcher import validate_allowed_tool
from backend.researchos.skills.runtime_skill_loader import build_execution_skill_context, load_selected_skill_docs


class ResearchExecutionAgent:
    """Minimal execution-layer scaffold.

    This class deliberately does not execute long-running tools yet. It validates
    context isolation, records a mock SkillRun id, and returns structured outputs
    so the coordinator protocol can be exercised safely.
    """

    def __init__(self, agent_root: Path | None = None) -> None:
        self.agent_root = agent_root or default_agent_root()

    def execute_task(self, task_spec: TaskSpec) -> ExecutionResult:
        started_at = datetime.now(timezone.utc)
        isolation = validate_context_isolation(task_spec)
        if not isolation["valid"]:
            return ExecutionResult(
                task_id=task_spec.task_id,
                skillrun_id=None,
                status="failed",
                summary="Execution blocked because context isolation failed.",
                logs=["validate_context_isolation failed"],
                errors=isolation["errors"],
                validation_report=isolation,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        tool_errors = []
        for tool_name in task_spec.allowed_tools or []:
            validation = validate_allowed_tool(tool_name, task_spec)
            if not validation["valid"]:
                tool_errors.extend(validation["errors"])
        if tool_errors:
            return ExecutionResult(
                task_id=task_spec.task_id,
                status="failed",
                summary="Execution blocked by tool policy.",
                logs=["tool policy failed"],
                errors=tool_errors,
                validation_report={"valid": False, "errors": tool_errors, "context_isolation": isolation},
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        skill_validation = validate_required_skills(task_spec.required_skills, agent_root=self.agent_root)
        if not skill_validation["valid"]:
            return ExecutionResult(
                task_id=task_spec.task_id,
                status="failed",
                summary="Execution blocked because one or more required skills are inactive or missing.",
                logs=["skill validation failed"],
                errors=skill_validation["errors"],
                validation_report={"valid": False, "errors": skill_validation["errors"], "context_isolation": isolation},
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        loader_logs: list[str] = []
        if task_spec.required_skills:
            try:
                selected_docs = load_selected_skill_docs(task_spec.required_skills)
                selected_context = build_execution_skill_context(task_spec.required_skills, max_tokens=min(6000, max(task_spec.max_context_tokens, 1000)))
                if selected_context:
                    existing = task_spec.context_package.get("active_skill_instructions")
                    active_skill_instructions = existing if isinstance(existing, list) else []
                    task_spec.context_package["active_skill_instructions"] = [*active_skill_instructions, selected_context]
                task_spec.input_data["loaded_skill_docs"] = sorted(selected_docs)
                loader_logs.append(f"loaded selected skill docs: {', '.join(sorted(selected_docs))}")
            except PermissionError as exc:
                return ExecutionResult(
                    task_id=task_spec.task_id,
                    status="failed",
                    summary="Execution blocked because one or more selected skills are inactive or unauthorized.",
                    logs=["runtime skill loader failed"],
                    errors=[str(exc)],
                    validation_report={"valid": False, "errors": [str(exc)], "context_isolation": isolation},
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )
            except (KeyError, FileNotFoundError, ValueError) as exc:
                loader_logs.append(f"selected skill docs unavailable: {exc}")

        plan = self.select_execution_plan(task_spec)
        if plan.get("status") != "ready":
            result = ExecutionResult(
                task_id=task_spec.task_id,
                status="failed",
                summary=str(plan.get("error") or "Execution plan could not be built."),
                logs=["execution plan failed"],
                errors=[str(plan.get("error") or "unknown task_type")],
                validation_report={"valid": False, "context_isolation": isolation},
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
            result.skillrun_id = self.write_skillrun_record(task_spec, result.structured_outputs, result.logs, "failed", result=result)
            return result

        task_spec.input_data.setdefault("workspace_base_dir", str(self.agent_root / "execution_tasks"))
        run_output = run_execution_plan(plan, task_spec, agent_root=self.agent_root)
        collected = collect_task_outputs(task_spec.task_id, task_spec.input_data.get("workspace_dir"), run_output.get("output_files", []))
        output_files = collected.get("output_files", [])
        outputs = run_output.get("outputs") if isinstance(run_output.get("outputs"), dict) else {}
        logs = list(run_output.get("logs") or [])
        errors = list(filter(None, [run_output.get("error")])) if not run_output.get("ok") else []
        status = "success" if run_output.get("ok") else "failed"
        result = ExecutionResult(
            task_id=task_spec.task_id,
            status=status,
            summary=("Execution completed." if status == "success" else "Execution failed.") + f" task_type={task_spec.task_type}",
            output_files=output_files,
            structured_outputs={**outputs, "execution_plan": plan},
            sources=run_output.get("sources") or task_spec.context_package.get("relevant_sources", []),
            logs=["context isolation passed", *loader_logs, *logs],
            errors=errors,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
        validation_report = validate_execution_result(result, task_spec)
        result.validation_report = {"context_isolation": isolation, "execution_result": validation_report}
        if status == "success" and not validation_report["valid"]:
            result.status = "partial_success"
            result.unresolved_items = validation_report["issues"]
        result.skillrun_id = self.write_skillrun_record(task_spec, result.structured_outputs, result.logs, "completed" if result.status in {"success", "partial_success"} else "failed", result=result)
        self._register_output_artifacts(task_spec, result)
        return result

    def select_execution_plan(self, task_spec: TaskSpec) -> dict[str, Any]:
        return build_execution_plan(task_spec)

    def call_skill(self, skill_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"skill_name": skill_name, "status": "not_connected", "inputs": inputs}

    def call_tool(self, tool_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"tool_name": tool_name, "status": "not_connected", "inputs": inputs}

    def collect_outputs(self, task_id: str) -> dict[str, Any]:
        return collect_task_outputs(task_id)

    def write_skillrun_record(self, task_spec: TaskSpec, outputs: dict[str, Any], logs: list[str], status: str, result: ExecutionResult | None = None) -> str:
        ros = import_research_os_mvp()
        existing = str((outputs or {}).get("skill_run_id") or "")
        if existing:
            return existing
        skill_id = "core_research_execution_agent"
        run = ros.start_service_skill_run(
            self.agent_root,
            skill_id,
            "ResearchExecutionAgent",
            task_spec.project_id or "",
            {
                "project_id": task_spec.project_id or "",
                "task_id": task_spec.task_id,
                "task_type": task_spec.task_type,
                "user_query": task_spec.user_query,
                "required_skills": task_spec.required_skills,
                "allowed_tools": task_spec.allowed_tools,
                "context_scope": task_spec.context_scope,
                "context_source_ids": task_spec.context_source_ids,
                "input_files": task_spec.input_files,
            },
        )
        output_refs = [{"type": "output_file", "id": path} for path in ((result.output_files if result else []) or [])]
        output_payload = {
            "project_id": task_spec.project_id or "",
            "task_id": task_spec.task_id,
            "task_type": task_spec.task_type,
            "structured_outputs": outputs or {},
            "sources": (result.sources if result else []),
            "errors": (result.errors if result else []),
            "unresolved_items": (result.unresolved_items if result else []),
            "status": status,
        }
        ros.update_skill_run(
            self.agent_root,
            run["id"],
            status=status,
            output_payload=output_payload,
            output_object_refs=output_refs,
            logs=logs,
            provenance=[{"type": "research_execution_agent", "task_id": task_spec.task_id, "context_scope": task_spec.context_scope}],
        )
        return run["id"]

    def _register_output_artifacts(self, task_spec: TaskSpec, result: ExecutionResult) -> None:
        if not task_spec.project_id or not result.output_files:
            return
        ros = import_research_os_mvp()
        for output_path in result.output_files:
            ros.register_artifact(
                self.agent_root,
                {
                    "project_id": task_spec.project_id,
                    "task_id": task_spec.task_id,
                    "skill_run_id": result.skillrun_id or "",
                    "source_skill_run_id": result.skillrun_id or "",
                    "type": "skill_output",
                    "title": Path(output_path).name,
                    "path": output_path,
                    "source_object_type": "output_file",
                    "source_object_id": output_path,
                    "status": "created" if result.status in {"success", "partial_success"} else "failed",
                    "metadata": {"task_type": task_spec.task_type, "provenance": {"task_id": task_spec.task_id, "skill_run_id": result.skillrun_id}},
                },
            )
