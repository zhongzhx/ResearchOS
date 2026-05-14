from __future__ import annotations

import sys
import os
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
from backend.researchos.execution.runtime_adapter import check_pipeline_authorization, scripts_dir
from backend.researchos.brain.context_indexer import update_project_context_index
from backend.researchos.brain.evidence_promotion import promote_skill_outputs_to_brain, validate_skill_output
from backend.researchos.brain.memory_writer import write_memory_from_execution_result, write_memory_from_promotion_decision
from backend.researchos.brain.post_task_reflector import reflect_on_completed_skillrun
from backend.researchos.brain.research_graph import rebuild_graph
from backend.researchos.brain.scientific_memory_validator import validate_memory_write
from backend.researchos.brain.skill_crystallizer import crystallize_skill_from_reflection
from backend.researchos.brain.skill_registry_review import register_pending_skill
from backend.researchos.brain.workflow_template_builder import build_workflow_template_from_skillruns, save_workflow_template
from backend.researchos.memory.retrieval.context_assembler import assemble_brain_context
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent, route_query_to_pipeline
from backend.researchos.skills.skill_discovery import search_skills


class ResearchBrainAgent:
    """Command-layer scaffold for the ResearchOS dual-agent architecture."""

    def __init__(self, execution_agent: ResearchExecutionAgent | None = None, agent_root: Path | None = None) -> None:
        self.execution_agent = execution_agent or ResearchExecutionAgent()
        self.agent_root = agent_root

    def handle_user_request(self, user_query: str, project_id: str | None = None) -> dict[str, Any]:
        intent = self._infer_intent(user_query)
        lightweight = lightweight_chat_response(user_query, intent)
        if lightweight:
            return lightweight
        compiled_context = self.compile_context(user_query, project_id, intent)
        task_spec = self.plan_task(user_query, compiled_context)
        result = self.dispatch_to_execution(task_spec)
        decision = self.evaluate_execution_result(result, task_spec)
        return self.compose_user_response(result, decision)

    def compile_context(self, user_query: str, project_id: str | None, intent: str) -> dict[str, Any]:
        envelope = build_brain_context_envelope(user_query, project_id, intent)
        memoryos_context: dict[str, Any] = {}
        if project_id:
            try:
                memoryos_context = assemble_brain_context(project_id, user_query, intent=intent, max_tokens=4000)
            except Exception as exc:  # noqa: BLE001
                memoryos_context = {"warnings": [f"MemoryOS context unavailable: {exc}"]}
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
                    if memoryos_context:
                        compiled["memoryos_context"] = memoryos_context
                        compiled.setdefault("project_summary", (memoryos_context.get("cognitive_state") or {}).get("current_goal") or "")
                        compiled.setdefault("sources", memoryos_context.get("selected_semantic_memories") or [])
                        compiled.setdefault("context_items", (memoryos_context.get("selected_semantic_memories") or []) + (memoryos_context.get("selected_episodes") or []))
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
                    "memoryos_context": memoryos_context,
                    "context_envelope": envelope.to_dict(),
                }
        return {
            "user_query": user_query,
            "intent": intent,
            "project_id": project_id,
            "project_summary": "",
            "sources": [],
            "context_items": [],
            "memoryos_context": memoryos_context,
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
        discovered_skills: list[dict[str, Any]] = []
        if not use_pipeline:
            discovered_skills = search_skills(user_query, intent=intent, top_k=1)
            if discovered_skills:
                required_skills = [str(item["skill_id"]) for item in discovered_skills]
        safety_constraints = ["Do not write long-term memory.", "Do not modify confirmed claims.", "Do not access forbidden context types."]
        if pipeline.get("requires_user_authorization"):
            safety_constraints.append("requires_user_authorization")
        user_authorization_flags = dict(compiled_context.get("user_authorization_flags") or compiled_context.get("authorization_flags") or {})
        if compiled_context.get("authorized") is True:
            user_authorization_flags["authorized"] = True
        if compiled_context.get("browser_authorized") is True:
            user_authorization_flags["browser"] = True
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
        if user_authorization_flags:
            spec.input_data["user_authorization_flags"] = user_authorization_flags
        spec.input_data["control_skills"] = control_skills
        spec.input_data["routing_control_skill"] = "skill-router-orchestrator"
        spec.input_data["context_control_skill"] = "context-compiler-maintenance"
        if discovered_skills:
            spec.input_data["skill_discovery"] = [
                {
                    "skill_id": item.get("skill_id"),
                    "display_name": item.get("display_name"),
                    "canonical_path": item.get("canonical_path"),
                    "score": item.get("score"),
                }
                for item in discovered_skills
            ]
        spec.context_package = build_execution_context_package(spec, compiled_context)
        spec.context_redaction_report = {"source": "build_execution_context_package", "control_skill": "context-compiler-maintenance", "raw_compiled_context_not_forwarded": True}
        spec.context_source_ids = [str(item.get("source_id") or item.get("id")) for item in spec.context_package.get("relevant_sources", []) if isinstance(item, dict)]
        authorization = check_pipeline_authorization(spec, pipeline)
        if authorization["requires_user_authorization"] and "requires_user_authorization" not in spec.safety_constraints:
            spec.safety_constraints.append("requires_user_authorization")
        spec.input_data["authorization_report"] = authorization
        spec.input_data["authorized"] = True if not authorization["requires_user_authorization"] else authorization["valid"]
        return spec

    def dispatch_to_execution(self, task_spec: TaskSpec) -> ExecutionResult:
        pipeline = get_pipeline_for_intent(str(task_spec.input_data.get("pipeline_name") or task_spec.intent or task_spec.task_type))
        authorization = check_pipeline_authorization(task_spec, pipeline)
        if not authorization["valid"]:
            return ExecutionResult(
                task_id=task_spec.task_id,
                status="failed",
                summary="Execution blocked pending explicit user authorization.",
                logs=["authorization pre-dispatch rejected"],
                errors=authorization["errors"],
                validation_report={"authorization": authorization},
            )
        return self.execution_agent.execute_task(task_spec)

    def evaluate_execution_result(self, result: ExecutionResult, task_spec: TaskSpec) -> BrainDecision:
        authorization = (result.validation_report or {}).get("authorization") if isinstance(result.validation_report, dict) else {}
        if isinstance(authorization, dict) and authorization.get("missing_authorization"):
            return BrainDecision(
                decision_type="ask_user",
                reason="Execution requires explicit user authorization before dispatch.",
                next_task_spec=task_spec,
                user_facing_summary="这个任务需要你明确授权后才能执行，尤其是浏览器或远程浏览器相关步骤。",
            )
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

    def validate_execution_result_for_promotion(self, result: ExecutionResult, task_spec: TaskSpec, pipeline: dict[str, Any]) -> dict[str, Any]:
        report = validate_skill_output(result, task_spec, pipeline)
        result.validation_report = {**(result.validation_report or {}), "skill_output_validator": report}
        return report

    def promote_execution_result(self, result: ExecutionResult, task_spec: TaskSpec, pipeline: dict[str, Any]) -> dict[str, Any]:
        return promote_skill_outputs_to_brain(result, task_spec, pipeline)

    def commit_promoted_memory(self, promotion_decision: dict[str, Any]) -> dict[str, Any]:
        return write_memory_from_promotion_decision(promotion_decision)

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
        if reflection.get("should_update_brain"):
            pipeline = get_pipeline_for_intent(task_spec.intent)
            self.validate_execution_result_for_promotion(result, task_spec, pipeline)
            promotion = self.promote_execution_result(result, task_spec, pipeline)
            memory_write = self.commit_promoted_memory(promotion)
        else:
            memory_write = {"pages": [], "skipped": "reflection skipped brain update"}
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
        if is_general_chat_input(user_query):
            return "general_chat"
        if is_model_identity_input(user_query):
            return "model_identity"
        if is_unclear_short_input(user_query):
            return "unclear_chat"
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


def is_general_chat_input(user_query: str) -> bool:
    text = " ".join(str(user_query or "").casefold().strip().split())
    if not text:
        return True
    greetings = {
        "hi",
        "hello",
        "hey",
        "yo",
        "你好",
        "您好",
        "在吗",
        "在么",
        "帮我看看",
        "帮我看下",
    }
    if text in greetings:
        return True
    return len(text) <= 12 and any(text.startswith(item) for item in greetings)


def general_chat_response() -> dict[str, Any]:
    return {
        "ok": True,
        "intent": "general_chat",
        "answer": "\u4f60\u597d\uff0c\u6211\u5728\u3002\u4f60\u53ef\u4ee5\u76f4\u63a5\u544a\u8bc9\u6211\u8981\u641c\u7d22\u6587\u732e\u3001\u6574\u7406 PDF\u3001\u5206\u6790\u6570\u636e\uff0c\u6216\u8005\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u540e\u7ee7\u7eed\u3002",
        "suggested_actions": [],
        "visible_sources": [],
        "warnings": [],
    }


def is_model_identity_input(user_query: str) -> bool:
    text = " ".join(str(user_query or "").casefold().strip().split())
    if not text:
        return False
    return any(
        phrase in text
        for phrase in [
            "什么大模型",
            "哪个大模型",
            "什么模型",
            "哪个模型",
            "model are you",
            "what model",
            "llm",
        ]
    )


def is_unclear_short_input(user_query: str) -> bool:
    text = str(user_query or "").strip()
    if not text:
        return True
    compact = "".join(text.split())
    if len(compact) > 8:
        return False
    return not any(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in compact)


def model_identity_response() -> dict[str, Any]:
    provider = os.environ.get("LLM_PROVIDER") or ("openai-compatible" if os.environ.get("OPENAI_API_KEY") else "mock")
    model = os.environ.get("LLM_MODEL") or os.environ.get("OPENAI_MODEL") or ""
    base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    if model:
        answer = f"当前后端连接的是 {provider} 模型接口，模型名是 {model}。"
    else:
        answer = f"当前后端模型 provider 是 {provider}，但没有读取到明确的模型名。"
    if base_url:
        answer += f" Base URL 是 {base_url}。"
    return {
        "ok": True,
        "intent": "model_identity",
        "answer": answer,
        "suggested_actions": [],
        "visible_sources": [],
        "warnings": [],
    }


def unclear_chat_response() -> dict[str, Any]:
    return {
        "ok": True,
        "intent": "unclear_chat",
        "answer": "我没看懂这条消息。你可以直接问我要做什么，例如“你是什么大模型”、 “帮我搜索文献”，或“总结当前项目”。",
        "suggested_actions": [],
        "visible_sources": [],
        "warnings": [],
    }


def lightweight_chat_response(user_query: str, intent: str | None = None) -> dict[str, Any] | None:
    resolved = intent or ""
    if not resolved:
        if is_general_chat_input(user_query):
            resolved = "general_chat"
        elif is_model_identity_input(user_query):
            resolved = "model_identity"
        elif is_unclear_short_input(user_query):
            resolved = "unclear_chat"
    if resolved == "general_chat":
        return general_chat_response()
    if resolved == "model_identity":
        return model_identity_response()
    if resolved == "unclear_chat":
        return unclear_chat_response()
    return None
