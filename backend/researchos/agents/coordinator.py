from __future__ import annotations

from typing import Any

from .agent_protocol import BrainDecision, ExecutionResult, TaskSpec
from .brain_agent import ResearchBrainAgent, lightweight_chat_response
from .execution_agent import ResearchExecutionAgent
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent
from backend.researchos.skills.resolver_checker import run_resolver_smoke_tests
from backend.researchos.execution.runtime_adapter import check_pipeline_authorization
from backend.researchos.tasks import ResearchTaskStateStore, build_contract_from_task_spec
from backend.researchos.tasks.task_executor_bridge import collect_artifacts_from_execution, execution_result_to_payload
from backend.researchos.tasks.task_handoff import compose_handoff
from backend.researchos.tasks.task_memory_commit import build_memory_commit_record
from backend.researchos.tasks.task_planner import build_goal, build_plan_markdown
from backend.researchos.tasks.task_validator import validate_task_outputs
from backend.researchos.memory.compression.cognitive_state import refresh_cognitive_state_after_task
from backend.researchos.memory.episodic.episodic_memory_store import create_episode_from_task
from backend.researchos.memory.events.event_store import append_event
from backend.researchos.memory.memory_event import create_memory_event
from backend.researchos.memory.working.working_memory_store import append_recent_message, compact_working_memory, set_current_task


class AgentCoordinator:
    def __init__(
        self,
        brain_agent: ResearchBrainAgent | None = None,
        execution_agent: ResearchExecutionAgent | None = None,
        task_store: ResearchTaskStateStore | None = None,
    ) -> None:
        self.execution_agent = execution_agent or ResearchExecutionAgent()
        self.brain_agent = brain_agent or ResearchBrainAgent(execution_agent=self.execution_agent)
        self.task_store = task_store or ResearchTaskStateStore()

    def run(self, user_query: str, project_id: str | None = None) -> dict[str, Any]:
        intent = self.brain_agent._infer_intent(user_query)
        lightweight = lightweight_chat_response(user_query, intent)
        if lightweight:
            return lightweight
        if project_id:
            append_recent_message(project_id, "user", user_query, {"project_id": project_id})
        compiled_context = self.brain_agent.compile_context(user_query, project_id, intent)
        task_spec = self.brain_agent.plan_task(user_query, compiled_context)
        if project_id:
            set_current_task(project_id, task_spec.task_id, project_id=project_id)
        pipeline_key = str(task_spec.input_data.get("pipeline_name") or task_spec.intent or task_spec.task_type)
        pipeline = get_pipeline_for_intent(pipeline_key)
        authorization = check_pipeline_authorization(task_spec, pipeline)
        if not authorization["valid"]:
            result = _authorization_block_result(task_spec, authorization)
            decision = self.brain_agent.evaluate_execution_result(result, task_spec)
            response = self.brain_agent.compose_user_response(result, decision)
            response["task_spec"] = task_spec.to_dict()
            response["execution_result"] = result.to_dict()
            response["brain_decision"] = decision.to_dict()
            response["validation_report"] = _authorization_validation_report(authorization)
            response["promotion_decision"] = {"accepted_targets": [], "rejected_items": [{"target": "execution", "reason": "missing user authorization"}], "required_human_review": True}
            response["memory_commit"] = _authorization_memory_commit(authorization)
            response["brain_memory_write"] = response["memory_commit"]
            response["rejected_items"] = response["memory_commit"]["rejected_items"]
            response["required_human_review"] = True
            response["research_graph"] = {"skipped": "execution blocked pending authorization"}
            response["context_index"] = {"skipped": "execution blocked pending authorization"}
            response["post_task_reflection"] = {"ok": False, "skipped": "execution blocked pending authorization"}
            response["resolver_health"] = run_resolver_smoke_tests()
            return response
        result = self.execution_agent.execute_task(task_spec)
        validation_report = self.brain_agent.validate_execution_result_for_promotion(result, task_spec, pipeline)
        promotion_decision = self.brain_agent.promote_execution_result(result, task_spec, pipeline)
        memory_commit = self.brain_agent.commit_promoted_memory(promotion_decision)
        graph_update = self.brain_agent.update_research_graph(project_id)
        context_index = self.brain_agent.update_context_index(project_id)
        cognitive_state = refresh_cognitive_state_after_task(project_id, task_spec.task_id) if project_id else {}
        if result.skillrun_id:
            try:
                post_task_reflection = self.brain_agent.run_post_task_reflection(result.skillrun_id)
            except Exception as exc:  # noqa: BLE001
                post_task_reflection = {"ok": False, "skipped": "post-task reflection unavailable", "error": str(exc)}
        else:
            post_task_reflection = {"ok": False, "skipped": "execution_result did not contain skillrun_id"}
        decision = self.brain_agent.evaluate_execution_result(result, task_spec)
        response = self.brain_agent.compose_user_response(result, decision)
        response["task_spec"] = task_spec.to_dict()
        response["execution_result"] = result.to_dict()
        response["brain_decision"] = decision.to_dict()
        response["validation_report"] = validation_report
        response["promotion_decision"] = promotion_decision
        response["memory_commit"] = memory_commit
        response["brain_memory_write"] = memory_commit
        response["rejected_items"] = promotion_decision.get("rejected_items") or memory_commit.get("rejected_items") or []
        response["required_human_review"] = bool(promotion_decision.get("required_human_review") or memory_commit.get("required_human_review"))
        response["research_graph"] = graph_update
        response["context_index"] = context_index
        response["cognitive_state"] = cognitive_state
        response["post_task_reflection"] = post_task_reflection
        response["resolver_health"] = run_resolver_smoke_tests()
        return response

    def run_full_cycle(self, user_query: str, project_id: str | None = None, process_after_execution: bool = True) -> dict[str, Any]:
        intent = self.brain_agent._infer_intent(user_query)
        lightweight = lightweight_chat_response(user_query, intent)
        if lightweight:
            return lightweight
        if project_id:
            append_recent_message(project_id, "user", user_query, {"project_id": project_id})
        task = self.task_store.create_task(project_id, user_query)
        if project_id:
            append_event(create_memory_event("task_created", project_id=project_id, task_id=task.task_id, source_id=task.task_id, source_type="task", payload={"user_query": user_query}))
        compiled_context = self.brain_agent.compile_context(user_query, project_id, intent)
        self.task_store.write_goal(task, build_goal(user_query, project_id, intent, compiled_context))

        task_spec = self.brain_agent.plan_task(user_query, compiled_context)
        task_spec.task_id = task.task_id
        task_spec.project_id = project_id or task_spec.project_id
        if project_id:
            set_current_task(project_id, task.task_id, project_id=project_id)
        pipeline_key = str(task_spec.input_data.get("pipeline_name") or task_spec.intent or task_spec.task_type)
        pipeline = get_pipeline_for_intent(pipeline_key)
        self.task_store.write_plan(task, build_plan_markdown(task_spec, pipeline))

        contract = build_contract_from_task_spec(task_spec)
        self.task_store.write_contract(task, contract)
        authorization = check_pipeline_authorization(task_spec, pipeline)
        if not authorization["valid"]:
            result = _authorization_block_result(task_spec, authorization)
            self.task_store.write_execution(task, execution_result_to_payload(result, []))
            self.task_store.write_artifacts(task, [])
            validation_report = _authorization_validation_report(authorization)
            self.task_store.write_validation(task, validation_report)
            memory_commit = _authorization_memory_commit(authorization)
            self.task_store.write_memory_commit(task, memory_commit)
            episode = create_episode_from_task(task.task_id)
            cognitive_state = refresh_cognitive_state_after_task(project_id, task.task_id) if project_id else {}
            decision = self.brain_agent.evaluate_execution_result(result, task_spec)
            handoff = compose_handoff(task)
            self.task_store.write_handoff(task, handoff)
            response = self.brain_agent.compose_user_response(result, decision)
            response["task_id"] = task.task_id
            response["research_task_id"] = task.task_id
            response["research_task_dir"] = str(self.task_store.task_dir(task.task_id))
            response["research_task"] = task.to_dict()
            response["handoff"] = handoff
            response["handoff_summary"] = _handoff_summary(handoff)
            response["task_spec"] = task_spec.to_dict()
            response["execution_result"] = result.to_dict()
            response["brain_decision"] = decision.to_dict()
            response["validation_report"] = validation_report
            response["promotion_validation_report"] = validation_report
            response["promotion_decision"] = {"accepted_targets": [], "rejected_items": memory_commit["rejected_items"], "required_human_review": True}
            response["memory_commit"] = memory_commit
            response["episode"] = episode
            response["cognitive_state"] = cognitive_state
            response["brain_memory_write"] = memory_commit
            response["rejected_items"] = memory_commit["rejected_items"]
            response["required_human_review"] = True
            response["research_graph"] = {"skipped": "execution blocked pending authorization"}
            response["context_index"] = {"skipped": "execution blocked pending authorization"}
            response["post_task_reflection"] = {"ok": False, "skipped": "execution blocked pending authorization"}
            response["post_task_processing"] = {"ok": False, "skipped": "execution blocked pending authorization"}
            response["resolver_health"] = run_resolver_smoke_tests()
            if project_id:
                compact_working_memory(project_id, project_id=project_id)
            return response
        self.task_store.mark_running(task)

        result = self.execution_agent.execute_task(task_spec)
        if result.task_id != task.task_id:
            self.task_store.append_event(task.task_id, "execution_task_id_rewritten", {"original_task_id": result.task_id, "research_task_id": task.task_id})
            result.task_id = task.task_id
        artifacts = collect_artifacts_from_execution(result, task_spec)
        self.task_store.write_execution(task, execution_result_to_payload(result, artifacts))
        self.task_store.write_artifacts(task, artifacts)

        promotion_validation = self.brain_agent.validate_execution_result_for_promotion(result, task_spec, pipeline)
        validation_report = validate_task_outputs(result, task_spec, contract, promotion_validation)
        self.task_store.write_validation(task, validation_report)

        promotion_decision = self.brain_agent.promote_execution_result(result, task_spec, pipeline)
        brain_memory_write = self.brain_agent.commit_promoted_memory(promotion_decision)
        graph_update = self.brain_agent.update_research_graph(project_id)
        context_index = self.brain_agent.update_context_index(project_id)

        if result.skillrun_id:
            try:
                post_task_reflection = self.brain_agent.run_post_task_reflection(result.skillrun_id)
            except Exception as exc:  # noqa: BLE001
                post_task_reflection = {"ok": False, "skipped": "post-task reflection unavailable", "error": str(exc)}
        else:
            post_task_reflection = {"ok": False, "skipped": "execution_result did not contain skillrun_id"}

        if process_after_execution:
            if result.skillrun_id:
                post_task_processing = self.process_completed_skillrun(result.skillrun_id)
            else:
                post_task_processing = {"ok": False, "error": "execution_result did not contain skillrun_id"}
        else:
            post_task_processing = {"ok": False, "skipped": "process_after_execution disabled"}

        memory_commit = build_memory_commit_record(
            promotion_decision,
            brain_memory_write,
            graph_update=graph_update,
            context_index_update=context_index,
            pending_skill=(post_task_processing.get("pending_skill") if isinstance(post_task_processing, dict) else None),
        )
        self.task_store.write_memory_commit(task, memory_commit)
        episode = create_episode_from_task(task.task_id)
        cognitive_state = refresh_cognitive_state_after_task(project_id, task.task_id) if project_id else {}

        decision = self.brain_agent.evaluate_execution_result(result, task_spec)
        handoff = compose_handoff(task)
        self.task_store.write_handoff(task, handoff)

        response = self.brain_agent.compose_user_response(result, decision)
        response["task_id"] = task.task_id
        response["research_task_id"] = task.task_id
        response["research_task_dir"] = str(self.task_store.task_dir(task.task_id))
        response["research_task"] = task.to_dict()
        response["handoff"] = handoff
        response["handoff_summary"] = _handoff_summary(handoff)
        response["task_spec"] = task_spec.to_dict()
        response["execution_result"] = result.to_dict()
        response["brain_decision"] = decision.to_dict()
        response["validation_report"] = validation_report
        response["promotion_validation_report"] = promotion_validation
        response["promotion_decision"] = promotion_decision
        response["memory_commit"] = memory_commit
        response["brain_memory_write"] = brain_memory_write
        response["episode"] = episode
        response["cognitive_state"] = cognitive_state
        response["rejected_items"] = memory_commit.get("rejected_items") or []
        response["required_human_review"] = bool(memory_commit.get("required_human_review"))
        response["research_graph"] = graph_update
        response["context_index"] = context_index
        response["post_task_reflection"] = post_task_reflection
        response["post_task_processing"] = post_task_processing
        response["resolver_health"] = run_resolver_smoke_tests()
        if project_id:
            append_event(create_memory_event("skillrun_completed", project_id=project_id, task_id=task.task_id, skillrun_id=result.skillrun_id, source_id=result.skillrun_id, source_type="skillrun", payload={"status": result.status, "summary": result.summary}))
            compact_working_memory(project_id, project_id=project_id)
        return response

    def run_brain_only(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "plan_task":
            user_query = str(payload.get("user_query") or payload.get("query") or "")
            project_id = payload.get("project_id")
            intent = str(payload.get("intent") or self.brain_agent._infer_intent(user_query))
            compiled = self.brain_agent.compile_context(user_query, project_id, intent)
            spec = self.brain_agent.plan_task(user_query, compiled)
            return {"ok": True, "task_spec": spec.to_dict()}
        return {"ok": False, "error": f"Unsupported brain action: {action}"}

    def run_execution_only(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        spec = TaskSpec(**task_spec)
        authorization = check_pipeline_authorization(spec, get_pipeline_for_intent(str(spec.input_data.get("pipeline_name") or spec.intent or spec.task_type)))
        if not authorization["valid"]:
            result = _authorization_block_result(spec, authorization)
            return {"ok": False, "execution_result": result.to_dict(), "authorization": authorization}
        result = self.execution_agent.execute_task(spec)
        return {"ok": result.status in {"success", "partial_success"}, "execution_result": result.to_dict()}

    def process_completed_skillrun(self, skillrun_id: str) -> dict[str, Any]:
        return self.brain_agent.process_completed_skillrun(skillrun_id)


def _handoff_summary(handoff: str, max_lines: int = 8) -> str:
    lines = [line for line in handoff.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def _authorization_block_result(task_spec: TaskSpec, authorization: dict[str, Any]) -> ExecutionResult:
    return ExecutionResult(
        task_id=task_spec.task_id,
        status="failed",
        summary="Execution blocked pending explicit user authorization.",
        logs=["authorization pre-dispatch rejected"],
        errors=list(authorization.get("errors") or []),
        validation_report={"authorization": authorization},
    )


def _authorization_validation_report(authorization: dict[str, Any]) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "safe_to_return": True,
        "safe_to_promote": False,
        "safe_to_crystallize": False,
        "required_human_review": True,
        "issues": list(authorization.get("errors") or []),
    }


def _authorization_memory_commit(authorization: dict[str, Any]) -> dict[str, Any]:
    return {
        "promoted_pages": [],
        "promoted_claims": [],
        "promoted_datasets": [],
        "promoted_decisions": [],
        "failure_memory": [],
        "context_index_update": {},
        "graph_update": {},
        "pending_skill": {},
        "rejected_items": [{"target": "execution", "reason": error} for error in authorization.get("errors") or ["missing user authorization"]],
        "required_human_review": True,
        "promotion_decision": {"accepted_targets": [], "rejected_items": [], "required_human_review": True},
        "memory_commit": {"pages": [], "rejected_items": [], "required_human_review": True},
    }
