from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Callable

from backend.researchos.execution.coding_runtime import CodingRuntimeService
from backend.researchos.execution.runtime_adapter import import_research_os_mvp, redact_payload
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent, list_pipelines, route_query_to_pipeline
from backend.researchos.workspace.file_artifact_registry import FileArtifactRegistry


EXECUTABLE_INTENTS = {
    "citation_support",
    "nature_figure_generation",
    "nature_paper_to_ppt",
    "nature_academic_polishing",
    "nature_reviewer_response",
    "nature_data_availability",
    "experiment_design",
    "protocol_to_sop",
    "failure_recovery",
    "weekly_report",
    "scientific_data_analysis",
    "paper_deep_reading",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": artifact["artifact_id"],
        "project_id": artifact["project_id"],
        "run_id": artifact.get("run_id", ""),
        "display_name": artifact["display_name"],
        "title": artifact["display_name"],
        "type": artifact["source_type"],
        "artifact_type": artifact["source_type"],
        "path": artifact["absolute_path"],
        "mime_type": artifact["mime_type"],
        "preview_type": artifact["preview_type"],
        "status": artifact["status"],
        "ingest_status": artifact["ingest_status"],
        "created_at": artifact["created_at"],
    }


class WorkflowExecutionError(RuntimeError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


class WorkflowExecutionService:
    def __init__(self, agent_root: Path) -> None:
        self.agent_root = Path(agent_root).resolve()
        self.ros = import_research_os_mvp()
        self.registry = FileArtifactRegistry(self.agent_root)
        self.runtime = CodingRuntimeService(self.agent_root)

    def workflow_registry(self) -> list[dict[str, Any]]:
        rows = []
        seen: set[str] = set()
        for pipeline in list_pipelines():
            intent = _text(pipeline.get("intent"))
            if intent in seen:
                continue
            seen.add(intent)
            rows.append(
                {
                    **pipeline,
                    "current_status": _text(pipeline.get("current_status")) or ("executable" if intent in EXECUTABLE_INTENTS else "not_connected"),
                }
            )
        return rows

    def plan(self, project_id: str, intent: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        project_id = self.ros.require_project_id(project_id)
        self.ros.require_existing_project(self.agent_root, project_id)
        pipeline = get_pipeline_for_intent(intent)
        params = dict(params or {})
        status, missing = self._readiness(pipeline, params)
        return {
            "ok": status not in {"not_connected", "failed"},
            "status": status if status != "executable" else "plan_only",
            "project_id": project_id,
            "intent": _text(pipeline.get("intent") or intent),
            "title": _text(pipeline.get("user_title") or intent),
            "message": self._plan_message(status, missing),
            "required_inputs": list(pipeline.get("required_inputs") or []),
            "missing_inputs": missing,
            "expected_artifacts": list(pipeline.get("expected_artifacts") or pipeline.get("expected_outputs") or []),
            "next_step": "Confirm execution after supplying the required project materials." if not missing else "Supply the missing project materials before execution.",
        }

    def execute(
        self,
        *,
        project_id: str,
        intent: str,
        params: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> dict[str, Any]:
        project_id = self.ros.require_project_id(project_id)
        self.ros.require_existing_project(self.agent_root, project_id)
        pipeline = get_pipeline_for_intent(intent)
        canonical_intent = _text(pipeline.get("intent") or intent)
        params = {**dict(params or {}), "project_id": project_id}
        status, missing = self._readiness(pipeline, params)
        if status != "executable":
            return {
                **self.plan(project_id, canonical_intent, params),
                "ok": False,
                "status": status,
                "run_id": "",
                "artifacts": [],
            }
        skill_id = _text((pipeline.get("execution_skills") or [canonical_intent])[0]) or canonical_intent
        run = self.ros.start_service_skill_run(
            self.agent_root,
            skill_id,
            _text(pipeline.get("user_title") or canonical_intent),
            project_id,
            {
                "project_id": project_id,
                "task_type": canonical_intent,
                "intent": canonical_intent,
                "conversation_id": conversation_id,
                "input_object_refs": self._input_refs(params),
            },
        )
        run_id = run["id"]
        try:
            artifacts, result = self._execute_handler(canonical_intent, project_id, run_id, params)
            if not artifacts:
                raise RuntimeError("workflow completed without registered artifacts")
            artifact_refs = [{"type": "artifact", "id": artifact["artifact_id"]} for artifact in artifacts]
            output = {
                "ok": True,
                "status": "completed",
                "project_id": project_id,
                "run_id": run_id,
                "intent": canonical_intent,
                "artifacts": [_artifact_view(artifact) for artifact in artifacts],
                "result": result,
            }
            self.ros.update_skill_run(
                self.agent_root,
                run_id,
                status="completed",
                output_payload=output,
                output_object_refs=artifact_refs,
                logs=[f"workflow execution completed with {len(artifacts)} registered artifact(s)"],
                provenance=[{"type": "workflow_execution_service", "intent": canonical_intent}],
            )
            return {
                **output,
                "title": _text(pipeline.get("user_title") or canonical_intent),
                "message": f"Generated {len(artifacts)} project artifact(s).",
                "next_step": "Open the project library to review the generated artifacts.",
                "developer_diagnostics": {
                    "pipeline": pipeline,
                    "skill_id": skill_id,
                    "conversation_id": conversation_id,
                },
            }
        except Exception as exc:  # noqa: BLE001
            failure_status = getattr(exc, "status", "failed")
            failed = {"ok": False, "status": failure_status, "project_id": project_id, "run_id": run_id, "intent": canonical_intent, "error": str(exc)}
            self.ros.update_skill_run(
                self.agent_root,
                run_id,
                status="failed",
                output_payload=failed,
                output_object_refs=[],
                logs=[str(exc)],
                provenance=[{"type": "workflow_execution_service", "intent": canonical_intent}],
            )
            return {
                **failed,
                "title": _text(pipeline.get("user_title") or canonical_intent),
                "message": "Workflow execution failed. No successful result was recorded.",
                "artifacts": [],
                "next_step": str(exc),
                "developer_diagnostics": redact_payload({"pipeline": pipeline, "error": str(exc)}),
            }

    def route_chat(self, project_id: str, message: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        pipeline = route_query_to_pipeline(message)
        intent = _text(pipeline.get("intent"))
        if intent in {"generic_skill_task", "unknown"}:
            return {"ok": False, "status": "not_connected", "intent": "", "message": "No executable research workflow matched this message."}
        supplied = dict(params or {})
        if intent == "nature_academic_polishing" and not supplied.get("text"):
            supplied["text"] = message
        if intent == "nature_reviewer_response" and not supplied.get("reviewer_comments"):
            supplied["reviewer_comments"] = message
        return self.plan(project_id, intent, supplied)

    def _readiness(self, pipeline: dict[str, Any], params: dict[str, Any]) -> tuple[str, list[str]]:
        intent = _text(pipeline.get("intent"))
        current_status = _text(pipeline.get("current_status")) or ("executable" if intent in EXECUTABLE_INTENTS else "not_connected")
        if current_status not in {"executable", "ready"}:
            return current_status, []
        if pipeline.get("requires_user_authorization") and params.get("authorized") is not True:
            return "needs_authorization", []
        missing = [key for key in pipeline.get("required_inputs") or [] if not self._has_input(key, params)]
        if missing:
            file_keys = {"artifact_id", "data_file", "paper_pdf", "paper_text", "source_file", "input_file"}
            return ("needs_file" if any(key in file_keys for key in missing) else "needs_input"), missing
        return "executable", []

    def _has_input(self, key: str, params: dict[str, Any]) -> bool:
        if not self._missing(params.get(key)):
            return True
        aliases = {
            "artifact_id": ["file_id", "data_file", "paper_pdf"],
            "data_file": ["artifact_id", "file_id"],
            "paper_text": ["paper_pdf", "outline"],
            "reviewer_comments": ["review_comments"],
            "method_text": ["source", "text"],
            "current_progress": ["content"],
        }
        return any(not self._missing(params.get(alias)) for alias in aliases.get(key, []))

    def _missing(self, value: Any) -> bool:
        if value is None or value == "":
            return True
        if isinstance(value, (list, dict, tuple, set)):
            return not value
        return False

    def _plan_message(self, status: str, missing: list[str]) -> str:
        if missing:
            return f"More input is required: {', '.join(missing)}."
        if status == "needs_authorization":
            return "User authorization is required before execution."
        if status in {"not_connected", "plan_only"}:
            return "This workflow is not connected for execution yet. A plan can still be reviewed."
        return "The workflow plan is ready for confirmation."

    def _input_refs(self, params: dict[str, Any]) -> list[dict[str, str]]:
        refs = []
        for key in ["artifact_id", "file_id", "data_file", "paper_pdf"]:
            value = _text(params.get(key))
            if value.startswith("artifact_"):
                refs.append({"type": "artifact", "id": value})
        return refs

    def _execute_handler(self, intent: str, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        handlers: dict[str, Callable[[str, str, dict[str, Any]], tuple[list[dict[str, Any]], dict[str, Any]]]] = {
            "citation_support": self._citation_support,
            "nature_figure_generation": self._figure_generation,
            "nature_paper_to_ppt": self._paper_to_ppt,
            "nature_academic_polishing": self._polishing,
            "nature_reviewer_response": self._reviewer_response,
            "nature_data_availability": self._data_availability,
            "scientific_data_analysis": self._scientific_data_analysis,
            "experiment_design": self._experiment_design,
            "protocol_to_sop": self._protocol_to_sop,
            "failure_recovery": self._failure_recovery,
            "weekly_report": self._weekly_report,
            "paper_deep_reading": self._paper_deep_reading,
        }
        handler = handlers.get(intent)
        if not handler:
            raise RuntimeError(f"workflow is not connected: {intent}")
        return handler(project_id, run_id, params)

    def _runtime(self, project_id: str, run_id: str, template: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        result = self.runtime.execute_template(project_id, template, params, run_id=run_id)
        if not result.get("ok"):
            raise WorkflowExecutionError(_text(result.get("status")) or "failed", _text(result.get("user_message")) or "coding runtime failed")
        artifacts = [self.registry.get(project_id, artifact["artifact_id"]) for artifact in result["artifacts"]]
        return artifacts, result

    def _content(self, project_id: str, run_id: str, source_type: str, display_name: str, content: str) -> dict[str, Any]:
        return self.registry.register_content(
            project_id=project_id,
            source_type=source_type,
            display_name=display_name,
            content=content,
            run_id=run_id,
            status="generated",
            ingest_status="generated",
        )

    def _csv(self, project_id: str, run_id: str, display_name: str, rows: list[list[Any]]) -> dict[str, Any]:
        stream = io.StringIO()
        csv.writer(stream).writerows(rows)
        return self._content(project_id, run_id, "generated_table", display_name, stream.getvalue())

    def _artifact_param(self, params: dict[str, Any]) -> dict[str, Any]:
        artifact_id = _text(params.get("artifact_id") or params.get("file_id") or params.get("data_file") or params.get("paper_pdf"))
        if artifact_id.startswith("artifact_"):
            return {"artifact_id": artifact_id, "project_id": params["project_id"]}
        return {}

    def _figure_generation(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        runtime_params = {**params, **self._artifact_param(params)}
        return self._runtime(project_id, run_id, "basic_stats_plot", runtime_params)

    def _scientific_data_analysis(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        runtime_params = {**params, **self._artifact_param(params)}
        template = _text(params.get("runtime_template"))
        if template not in {"data_profile", "basic_stats_plot", "qpcr_template"}:
            template = "basic_stats_plot" if params.get("x") and params.get("y") else "data_profile"
        return self._runtime(project_id, run_id, template, runtime_params)

    def _paper_to_ppt(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        outline = params.get("outline")
        if not outline:
            paper_text = _text(params.get("paper_text"))
            outline = [
                {"title": "Journal Club", "body": _text(params.get("title") or "Paper discussion")},
                {"title": "Research question", "body": paper_text[:500] or "Review the selected paper."},
                {"title": "Methods and evidence", "body": "Validate methods, figures, and limitations against the source paper."},
                {"title": "Discussion", "body": "Summarize supported conclusions and open questions."},
            ]
        artifacts, result = self._runtime(project_id, run_id, "ppt_from_outline", {"outline": outline, "filename": "journal_club.pptx"})
        outline_artifact = self._content(project_id, run_id, "generated_markdown", "slide_outline.md", "\n".join(f"# {row['title']}\n\n{row.get('body', '')}" for row in outline))
        notes = self._content(project_id, run_id, "generated_markdown", "speaker_notes.md", "# Speaker Notes\n\n- Verify every claim against the selected source paper.\n")
        return [*artifacts, outline_artifact, notes], result

    def _polishing(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        text = _text(params.get("text"))
        polished = text.replace("  ", " ").strip()
        artifacts = [
            self._content(project_id, run_id, "generated_markdown", "polished_text.md", f"# Polished Text\n\n{polished}\n"),
            self._content(project_id, run_id, "generated_markdown", "change_log.md", "# Change Log\n\n- Applied conservative whitespace and formatting normalization locally.\n"),
            self._content(project_id, run_id, "generated_markdown", "risk_flags.md", "# Risk Flags\n\n- Domain claims and journal-specific style still require human review.\n"),
        ]
        return artifacts, {"mode": "local_conservative_polish"}

    def _reviewer_response(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        comments = _text(params.get("reviewer_comments") or params.get("review_comments"))
        response = f"# Response Letter\n\n## Reviewer comments\n\n{comments}\n\n## Response draft\n\n- Review each comment and add evidence-backed revisions before submission.\n"
        artifacts = [
            self._content(project_id, run_id, "generated_markdown", "response_letter.md", response),
            self._csv(project_id, run_id, "action_matrix.csv", [["comment_id", "comment", "action", "revision_location"], ["1", comments, "needs_review", "needs_input"]]),
        ]
        return artifacts, {"mode": "local_response_scaffold"}

    def _data_availability(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        inventory = _text(params.get("dataset_inventory"))
        plan = _text(params.get("repository_plan"))
        return [
            self._content(project_id, run_id, "generated_markdown", "data_availability_statement.md", f"# Data Availability Statement\n\nDataset inventory: {inventory}\n\nRepository plan: {plan or 'needs_input'}\n"),
            self._content(project_id, run_id, "generated_markdown", "fair_audit.md", "# FAIR Audit\n\n- Repository accession and metadata completeness require human verification.\n"),
        ], {"mode": "local_fair_scaffold"}

    def _citation_support(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        claim = _text(params.get("claim") or params.get("manuscript_text"))
        return [
            self._content(project_id, run_id, "generated_markdown", "citation_candidates.md", f"# Citation Candidates\n\nClaim: {claim}\n\n- No citation was invented. Add verified project references or run literature harvest.\n"),
            self._csv(project_id, run_id, "reference_candidates.csv", [["claim", "reference_id", "doi", "status"], [claim, "", "", "needs_verified_reference"]]),
        ], {"mode": "no_fabrication_placeholder"}

    def _markdown_workflow(self, project_id: str, run_id: str, title: str, filename: str, sections: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._runtime(project_id, run_id, "markdown_report", {"title": title, "filename": filename, "sections": sections})

    def _experiment_design(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._markdown_workflow(project_id, run_id, "Experiment Design", "experiment_design.md", {"Objective": params.get("objective"), "Controls and QA": "Confirm controls, replicates, randomization, and analysis plan before wet-lab use."})

    def _protocol_to_sop(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._markdown_workflow(project_id, run_id, "Protocol to SOP", "protocol_sop.md", {"Source method": params.get("method_text") or params.get("source"), "Safety": "Human review is required before wet-lab use."})

    def _failure_recovery(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._markdown_workflow(project_id, run_id, "Failure Recovery", "failure_recovery.md", {"Observed failure": params.get("failure_description"), "Next checks": "Separate hypotheses from confirmed causes and test one variable at a time."})

    def _weekly_report(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._markdown_workflow(project_id, run_id, "Weekly Report", "weekly_report.md", {"Progress": params.get("current_progress") or params.get("content"), "Next week": params.get("next_steps") or "needs_input"})

    def _paper_deep_reading(self, project_id: str, run_id: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._markdown_workflow(project_id, run_id, "Paper Deep Reading", "paper_deep_reading.md", {"Source": params.get("paper_text") or params.get("paper_pdf"), "Review checklist": "Summarize question, methods, evidence, limitations, and reusable insights."})


def list_workflow_definitions(agent_root: Path) -> dict[str, Any]:
    return {"workflows": WorkflowExecutionService(agent_root).workflow_registry()}


def plan_workflow_execution(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return WorkflowExecutionService(agent_root).plan(_text(payload.get("project_id")), _text(payload.get("intent")), payload.get("params") if isinstance(payload.get("params"), dict) else payload)


def execute_workflow(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return WorkflowExecutionService(agent_root).execute(
        project_id=_text(payload.get("project_id")),
        intent=_text(payload.get("intent")),
        params=payload.get("params") if isinstance(payload.get("params"), dict) else payload,
        conversation_id=_text(payload.get("conversation_id")),
    )


def route_chat_workflow(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return WorkflowExecutionService(agent_root).route_chat(
        _text(payload.get("project_id")),
        _text(payload.get("message") or payload.get("text")),
        payload.get("params") if isinstance(payload.get("params"), dict) else {},
    )
