from __future__ import annotations

from typing import Any

from .agent_protocol import BrainDecision, ExecutionResult, TaskSpec
from .brain_agent import ResearchBrainAgent
from .execution_agent import ResearchExecutionAgent
from backend.researchos.skills.resolver_checker import run_resolver_smoke_tests


class AgentCoordinator:
    def __init__(self, brain_agent: ResearchBrainAgent | None = None, execution_agent: ResearchExecutionAgent | None = None) -> None:
        self.execution_agent = execution_agent or ResearchExecutionAgent()
        self.brain_agent = brain_agent or ResearchBrainAgent(execution_agent=self.execution_agent)

    def run(self, user_query: str, project_id: str | None = None) -> dict[str, Any]:
        intent = self.brain_agent._infer_intent(user_query)
        compiled_context = self.brain_agent.compile_context(user_query, project_id, intent)
        task_spec = self.brain_agent.plan_task(user_query, compiled_context)
        result = self.execution_agent.execute_task(task_spec)
        decision = self.brain_agent.evaluate_execution_result(result, task_spec)
        memory_write = self.brain_agent.write_memory_from_result(result, decision, task_spec)
        graph_update = self.brain_agent.update_research_graph(project_id)
        context_index = self.brain_agent.update_context_index(project_id)
        response = self.brain_agent.compose_user_response(result, decision)
        response["task_spec"] = task_spec.to_dict()
        response["execution_result"] = result.to_dict()
        response["brain_decision"] = decision.to_dict()
        response["brain_memory_write"] = memory_write
        response["research_graph"] = graph_update
        response["context_index"] = context_index
        response["resolver_health"] = run_resolver_smoke_tests()
        return response

    def run_full_cycle(self, user_query: str, project_id: str | None = None, process_after_execution: bool = True) -> dict[str, Any]:
        response = self.run(user_query, project_id=project_id)
        if process_after_execution:
            skillrun_id = ((response.get("execution_result") or {}).get("skillrun_id") if isinstance(response.get("execution_result"), dict) else "")
            if skillrun_id:
                response["post_task_processing"] = self.process_completed_skillrun(skillrun_id)
            else:
                response["post_task_processing"] = {"ok": False, "error": "execution_result did not contain skillrun_id"}
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
        result = self.execution_agent.execute_task(spec)
        return {"ok": result.status in {"success", "partial_success"}, "execution_result": result.to_dict()}

    def process_completed_skillrun(self, skillrun_id: str) -> dict[str, Any]:
        return self.brain_agent.process_completed_skillrun(skillrun_id)
