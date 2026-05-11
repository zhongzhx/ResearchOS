from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .agent_protocol import (
    BrainDecision,
    ExecutionResult,
    TaskSpec,
    build_brain_context_envelope,
    build_execution_context_package,
)
from .execution_agent import ResearchExecutionAgent
from backend.researchos.execution.runtime_adapter import scripts_dir
from backend.researchos.brain.context_indexer import update_project_context_index
from backend.researchos.brain.memory_writer import write_memory_from_execution_result
from backend.researchos.brain.post_task_reflector import reflect_on_completed_skillrun
from backend.researchos.brain.research_graph import rebuild_graph
from backend.researchos.brain.scientific_memory_validator import validate_memory_write
from backend.researchos.brain.skill_crystallizer import crystallize_skill_from_reflection
from backend.researchos.brain.skill_registry_review import register_pending_skill
from backend.researchos.brain.workflow_template_builder import build_workflow_template_from_skillruns, save_workflow_template
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent, route_query_to_pipeline


class ResearchBrainAgent:
    """Command-layer scaffold for the ResearchOS dual-agent architecture."""

    def __init__(self, execution_agent: ResearchExecutionAgent | None = None, agent_root: Path | None = None) -> None:
        self.execution_agent = execution_agent or ResearchExecutionAgent()
        self.agent_root = agent_root

    def handle_user_request(self, user_query: str, project_id: str | None = None) -> dict[str, Any]:
        intent = self._infer_intent(user_query)
        compiled_context = self.compile_context(user_query, project_id, intent)
        task_spec = self.plan_task(user_query, compiled_context)
        result = self.dispatch_to_execution(task_spec)
        decision = self.evaluate_execution_result(result, task_spec)
        return self.compose_user_response(result, decision)

    def compile_context(self, user_query: str, project_id: str | None, intent: str) -> dict[str, Any]:
        envelope = build_brain_context_envelope(user_query, project_id, intent)
        if self.agent_root:
            try:
                runtime_scripts_dir = scripts_dir()
                if runtime_scripts_dir.exists() and str(runtime_scripts_dir) not in sys.path:
                    sys.path.insert(0, str(runtime_scripts_dir))
                import research_context_compiler  # type: ignore

                compiled = research_context_compiler.compile_research_context(
                    self.agent_root,
                    {
                        "user_message": user_query,
                        "intent": intent,
                        "project_id": project_id,
                        "max_tokens": 2000,
                    },
                )
                if isinstance(compiled, dict):
                    compiled.setdefault("user_query", user_query)
                    compiled.setdefault("intent", intent)
                    compiled.setdefault("project_id", project_id)
                return compiled
            except Exception as exc:  # noqa: BLE001
                return {
                    "user_query": user_query,
                    "intent": intent,
                    "project_id": project_id,
                    "project_summary": "",
                    "sources": [],
                    "context_items": [],
                    "warnings": [f"Research Context Compiler unavailable: {exc}"],
                    "context_envelope": envelope.to_dict(),
                }
        return {
            "user_query": user_query,
            "intent": intent,
            "project_id": project_id,
            "project_summary": "",
            "sources": [],
            "context_items": [],
            "context_envelope": envelope.to_dict(),
        }

    def plan_task(self, user_query: str, compiled_context: dict[str, Any]) -> TaskSpec:
        intent = str(compiled_context.get("intent") or self._infer_intent(user_query))
        pipeline = get_pipeline_for_intent(intent)
        if pipeline.get("pipeline_name") == "generic_skill_task":
            routed = route_query_to_pipeline(user_query)
            if routed.get("pipeline_name") != "research_route_planning" or intent in {routed.get("intent"), "research_advice", "start_skill_request"}:
                pipeline = routed
        use_pipeline = pipeline.get("pipeline_name") != "generic_skill_task" and intent not in {"kb_query"}
        control_skills = pipeline.get("control_skills") or {
            "pre_dispatch": ["skill-router-orchestrator", "context-compiler-maintenance"],
            "post_execution": ["skill-output-validator", "evidence-promotion"],
        }
        task_type = str(pipeline.get("pipeline_name")) if use_pipeline else self._task_type_for_intent(intent, user_query)
        required_skills = list(pipeline.get("execution_skills") or []) if use_pipeline else self._skills_for_task(task_type)
        expected_outputs = list(pipeline.get("expected_outputs") or []) if use_pipeline else self._outputs_for_task(task_type)
        validation_rules = list(pipeline.get("validation_rules") or []) if use_pipeline else ["Only use the supplied execution_minimal context.", "Return sources for evidence-backed outputs."]
        safety_constraints = ["Do not write long-term memory.", "Do not modify confirmed claims.", "Do not access forbidden context types."]
        if pipeline.get("requires_user_authorization"):
            safety_constraints.append("requires_user_authorization")
        spec = TaskSpec(
            project_id=compiled_context.get("project_id"),
            user_query=user_query,
            intent=intent,
            task_type=task_type,
            priority="normal",
            required_skills=required_skills,
            allowed_tools=list(pipeline.get("allowed_tools") or []) if use_pipeline else self._tools_for_task(task_type),
            forbidden_tools=["delete_files", "read_secrets", "modify_raw_data"],
            expected_outputs=expected_outputs,
            validation_rules=validation_rules,
            safety_constraints=safety_constraints,
            max_context_tokens=1500,
        )
        spec.input_data["pipeline_name"] = pipeline.get("pipeline_name") if use_pipeline else ""
        spec.input_data["authorized"] = False if pipeline.get("requires_user_authorization") else True
        spec.input_data["control_skills"] = control_skills
        spec.input_data["routing_control_skill"] = "skill-router-orchestrator"
        spec.input_data["context_control_skill"] = "context-compiler-maintenance"
        spec.context_package = build_execution_context_package(spec, compiled_context)
        spec.context_redaction_report = {"source": "build_execution_context_package", "control_skill": "context-compiler-maintenance", "raw_compiled_context_not_forwarded": True}
        spec.context_source_ids = [str(item.get("source_id") or item.get("id")) for item in spec.context_package.get("relevant_sources", []) if isinstance(item, dict)]
        return spec

    def dispatch_to_execution(self, task_spec: TaskSpec) -> ExecutionResult:
        return self.execution_agent.execute_task(task_spec)

    def evaluate_execution_result(self, result: ExecutionResult, task_spec: TaskSpec) -> BrainDecision:
        if result.status == "success":
            claim_text = result.structured_outputs.get("claim_text") if isinstance(result.structured_outputs, dict) else ""
            if claim_text:
                validation = validate_memory_write({"type": "claim", "text": claim_text, "source_ids": [source.get("source_id") for source in result.sources if isinstance(source, dict) and source.get("source_id")], "confidence": "medium"})
                if not validation["valid"]:
                    return BrainDecision(
                        decision_type="revise",
                        reason="Execution output contains a claim that needs evidence or confidence downgrade.",
                        user_facing_summary="结果已生成，但其中有结论需要补充证据或降级为假设后才能写入长期科研记忆。",
                    )
            return BrainDecision(
                decision_type="accept",
                reason="Execution Agent returned a successful result.",
                user_facing_summary=result.summary,
            )
        if result.status == "partial_success":
            return BrainDecision(
                decision_type="accept",
                reason="Execution Agent returned partial output with unresolved items; write only low-confidence memory.",
                user_facing_summary=result.summary,
            )
        return BrainDecision(
            decision_type="revise",
            reason="Execution Agent failed or returned partial output.",
            next_task_spec=task_spec,
            user_facing_summary=result.summary,
        )

    def write_memory_from_result(self, result: ExecutionResult, decision: BrainDecision, task_spec: TaskSpec) -> dict[str, Any]:
        if decision.decision_type not in {"accept", "write_memory", "revise"}:
            return {"pages": [], "skipped": f"decision_type={decision.decision_type}"}
        return write_memory_from_execution_result(result, decision, task_spec)

    def update_research_graph(self, project_id: str | None) -> dict[str, Any]:
        return rebuild_graph(project_id)

    def update_context_index(self, project_id: str | None) -> dict[str, Any]:
        if not project_id:
            return {"project_id": "", "skipped": "missing_project_id"}
        return update_project_context_index(project_id)

    def run_post_task_reflection(self, skillrun_id: str) -> dict[str, Any]:
        return reflect_on_completed_skillrun(skillrun_id)

    def crystallize_skill_if_useful(self, reflection: dict[str, Any]) -> dict[str, Any]:
        if not reflection.get("should_crystallize_skill"):
            return {"created": False, "reason": "reflection did not meet crystallization threshold"}
        generated = crystallize_skill_from_reflection(reflection)
        registered = register_pending_skill(generated["skill_dir"])
        return {"created": True, "generated": generated, "status": registered.get("status"), **registered}

    def process_completed_skillrun(self, skillrun_id: str) -> dict[str, Any]:
        reflection = self.run_post_task_reflection(skillrun_id)
        project_id = reflection.get("project_id")
        status = "failed" if reflection.get("failure_items") else "success"
        task_spec = TaskSpec(
            project_id=project_id,
            user_query=reflection.get("user_query") or reflection.get("task_summary") or "",
            intent="post_task_reflection",
            task_type=reflection.get("task_type") or "generic_skill_task",
            context_package={"task_brief": reflection.get("task_summary") or ""},
        )
        result = ExecutionResult(
            task_id=task_spec.task_id,
            skillrun_id=skillrun_id,
            status=status,
            summary=reflection.get("task_summary") or "",
            structured_outputs={"claim_text": reflection.get("task_summary")} if status == "success" else {},
            sources=[{"source_id": item.get("id") or item.get("source_id") or str(item)} for item in reflection.get("evidence_items") or []],
            errors=reflection.get("failure_items") or [],
        )
        decision = self.evaluate_execution_result(result, task_spec)
        memory_write = self.write_memory_from_result(result, decision, task_spec) if reflection.get("should_update_brain") else {"pages": [], "skipped": "reflection skipped brain update"}
        graph = self.update_research_graph(project_id)
        context_index = self.update_context_index(project_id)
        pending_skill = self.crystallize_skill_if_useful(reflection)
        workflow_template = {"created": False}
        if reflection.get("should_create_workflow_template"):
            try:
                workflow_template = save_workflow_template(build_workflow_template_from_skillruns([skillrun_id, skillrun_id]))
                workflow_template["created"] = True
            except Exception as exc:  # noqa: BLE001
                workflow_template = {"created": False, "error": str(exc)}
        return {
            "ok": True,
            "skillrun_id": skillrun_id,
            "reflection": reflection,
            "memory_write": memory_write,
            "research_graph": graph,
            "context_index": context_index,
            "pending_skill": pending_skill,
            "workflow_template": workflow_template,
        }

    def compose_user_response(self, result: ExecutionResult, decision: BrainDecision) -> dict[str, Any]:
        return {
            "ok": result.status in {"success", "partial_success"},
            "answer": decision.user_facing_summary or result.summary,
            "execution_result": result.to_dict(),
            "brain_decision": decision.to_dict(),
        }

    def _infer_intent(self, user_query: str) -> str:
        lowered = user_query.lower()
        routed = route_query_to_pipeline(user_query)
        if routed.get("pipeline_name") and routed.get("pipeline_name") != "research_route_planning":
            return str(routed.get("intent") or routed.get("pipeline_name"))
        if any(term in lowered for term in ["知识库", "文献", "paper", "kb", "rag"]):
            return "kb_query"
        if any(term in lowered for term in ["下载", "采集", "执行", "run", "start"]):
            return "start_skill_request"
        return "research_advice"

    def _task_type_for_intent(self, intent: str, user_query: str) -> str:
        if intent == "kb_query":
            return "kb_summary"
        if intent == "start_skill_request":
            return "literature_harvest" if any(term in user_query for term in ["文献", "paper", "literature"]) else "skill_execution"
        return "research_planning"

    def _skills_for_task(self, task_type: str) -> list[str]:
        mapping = {
            "kb_summary": ["core_build_user_research_kb"],
            "literature_harvest": ["core_keyword_research_harvest"],
            "research_planning": ["core_plan_research_route"],
        }
        return mapping.get(task_type, ["general-research-skill"])

    def _tools_for_task(self, task_type: str) -> list[str]:
        mapping = {
            "kb_summary": ["rag_query"],
            "literature_harvest": ["literature_search"],
            "research_planning": ["context_lookup"],
        }
        return mapping.get(task_type, [])

    def _outputs_for_task(self, task_type: str) -> list[str]:
        mapping = {
            "kb_summary": ["structured_outputs"],
            "literature_harvest": ["download_report", "references"],
            "research_planning": ["task_plan"],
        }
        return mapping.get(task_type, ["structured_output"])
