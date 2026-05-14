import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import BrainDecision, ExecutionResult, TaskSpec
from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.tasks import ResearchTaskStateStore


class FakeBrain:
    def _infer_intent(self, user_query: str) -> str:
        return "kb_query"

    def compile_context(self, user_query: str, project_id: str | None, intent: str) -> dict:
        return {"user_query": user_query, "project_id": project_id, "intent": intent, "sources": []}

    def plan_task(self, user_query: str, compiled_context: dict) -> TaskSpec:
        return TaskSpec(
            project_id=compiled_context.get("project_id"),
            user_query=user_query,
            intent="kb_query",
            task_type="kb_summary",
            required_skills=[],
            allowed_tools=[],
            expected_outputs=["structured_outputs"],
            context_package={"task_brief": user_query},
        )

    def validate_execution_result_for_promotion(self, result: ExecutionResult, task_spec: TaskSpec, pipeline: dict) -> dict:
        return {"valid": True, "issues": [], "safe_to_return": True, "safe_to_promote": True, "safe_to_crystallize": True}

    def promote_execution_result(self, result: ExecutionResult, task_spec: TaskSpec, pipeline: dict) -> dict:
        if result.status == "failed":
            return {
                "project_id": task_spec.project_id,
                "task_id": task_spec.task_id,
                "rejected_items": [],
                "required_human_review": True,
                "memory_items": [{"page_type": "failure", "compiled_truth": result.summary, "title": "failed", "source_ids": [task_spec.task_id]}],
            }
        return {"project_id": task_spec.project_id, "task_id": task_spec.task_id, "rejected_items": [], "required_human_review": False, "memory_items": []}

    def commit_promoted_memory(self, promotion_decision: dict) -> dict:
        pages = [{"page_type": item["page_type"], "path": f"{item['page_type']}.md"} for item in promotion_decision.get("memory_items") or []]
        return {"pages": pages, "rejected_items": [], "required_human_review": promotion_decision.get("required_human_review", False)}

    def update_research_graph(self, project_id: str | None) -> dict:
        return {"project_id": project_id, "edge_count": 0}

    def update_context_index(self, project_id: str | None) -> dict:
        return {"project_id": project_id}

    def run_post_task_reflection(self, skillrun_id: str) -> dict:
        return {"skillrun_id": skillrun_id}

    def process_completed_skillrun(self, skillrun_id: str) -> dict:
        return {"ok": True, "reflection": {"skillrun_id": skillrun_id}, "pending_skill": {"created": False}}

    def evaluate_execution_result(self, result: ExecutionResult, task_spec: TaskSpec) -> BrainDecision:
        return BrainDecision(decision_type="accept" if result.status != "failed" else "revise", reason="done", user_facing_summary=result.summary)

    def compose_user_response(self, result: ExecutionResult, decision: BrainDecision) -> dict:
        return {"ok": result.status in {"success", "partial_success"}, "answer": decision.user_facing_summary}


class FakeExecution:
    def __init__(self, status: str = "success") -> None:
        self.status = status
        self.calls = 0

    def execute_task(self, task_spec: TaskSpec) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            task_id=task_spec.task_id,
            skillrun_id="skillrun_fake" if self.status != "failed" else None,
            status=self.status,
            summary="Execution completed." if self.status != "failed" else "Execution failed.",
            structured_outputs={"answer": "ok"} if self.status != "failed" else {},
            errors=[] if self.status != "failed" else ["boom"],
        )


class CoordinatorResearchTaskFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="coordinator_task_flow_"))
        self.store = ResearchTaskStateStore(self.tmp / "research_tasks")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_full_cycle_writes_research_task_package(self) -> None:
        coordinator = AgentCoordinator(brain_agent=FakeBrain(), execution_agent=FakeExecution(), task_store=self.store)

        response = coordinator.run_full_cycle("summarize", project_id="project_1")

        self.assertTrue(response["ok"])
        self.assertTrue(response["task_id"])
        task_dir = Path(response["research_task_dir"])
        self.assertTrue((task_dir / "goal.json").exists())
        self.assertTrue((task_dir / "plan.md").exists())
        self.assertTrue((task_dir / "contract.json").exists())
        self.assertTrue((task_dir / "execution_result.json").exists())
        self.assertTrue((task_dir / "memory_commit.json").exists())
        self.assertTrue((task_dir / "handoff.md").exists())
        self.assertIn("Research Task Handoff", response["handoff_summary"])

    def test_failed_task_has_handoff_and_failure_memory(self) -> None:
        coordinator = AgentCoordinator(brain_agent=FakeBrain(), execution_agent=FakeExecution("failed"), task_store=self.store)

        response = coordinator.run_full_cycle("fail this task", project_id="project_1")

        self.assertFalse(response["ok"])
        task_dir = Path(response["research_task_dir"])
        memory_commit = json.loads((task_dir / "memory_commit.json").read_text(encoding="utf-8"))
        handoff = (task_dir / "handoff.md").read_text(encoding="utf-8")
        self.assertTrue(memory_commit["failure_memory"])
        self.assertIn("Execution failed.", handoff)
        self.assertIn("execution_written", (task_dir / "events.jsonl").read_text(encoding="utf-8"))

    def test_greeting_does_not_create_task_or_call_execution(self) -> None:
        execution = FakeExecution()
        coordinator = AgentCoordinator(execution_agent=execution, task_store=self.store)

        response = coordinator.run_full_cycle("hi", project_id="project_1")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "general_chat")
        self.assertIn("answer", response)
        self.assertNotIn("task_spec", response)
        self.assertNotIn("execution_result", response)
        self.assertEqual(execution.calls, 0)
        self.assertEqual(list((self.tmp / "research_tasks").glob("*")), [])

    def test_model_identity_question_does_not_create_task_or_call_execution(self) -> None:
        execution = FakeExecution()
        coordinator = AgentCoordinator(execution_agent=execution, task_store=self.store)

        response = coordinator.run_full_cycle("你是什么大模型", project_id="project_1")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "model_identity")
        self.assertIn("answer", response)
        self.assertNotIn("task_spec", response)
        self.assertNotIn("execution_result", response)
        self.assertEqual(execution.calls, 0)
        self.assertEqual(list((self.tmp / "research_tasks").glob("*")), [])

    def test_unclear_short_input_does_not_create_task_or_call_execution(self) -> None:
        execution = FakeExecution()
        coordinator = AgentCoordinator(execution_agent=execution, task_store=self.store)

        response = coordinator.run_full_cycle("？？？", project_id="project_1")

        self.assertTrue(response["ok"])
        self.assertEqual(response["intent"], "unclear_chat")
        self.assertIn("没看懂", response["answer"])
        self.assertEqual(execution.calls, 0)
        self.assertEqual(list((self.tmp / "research_tasks").glob("*")), [])


if __name__ == "__main__":
    unittest.main()
