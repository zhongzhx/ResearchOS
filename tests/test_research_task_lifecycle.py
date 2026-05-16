import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.tasks import ResearchTaskStateStore, build_contract_from_task_spec
from backend.researchos.tasks.task_executor_bridge import collect_artifacts_from_execution, execution_result_to_payload
from backend.researchos.tasks.task_handoff import compose_handoff
from backend.researchos.tasks.task_memory_commit import build_memory_commit_record
from backend.researchos.tasks.task_planner import build_goal, build_plan_markdown
from backend.researchos.tasks.task_validator import validate_task_outputs


class ResearchTaskLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="research_task_lifecycle_"))
        self.store = ResearchTaskStateStore(self.tmp / "research_tasks")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_task_package_sections_are_persisted(self) -> None:
        task = self.store.create_task("project_1", "summarize paper evidence", task_id="task_lifecycle")
        spec = TaskSpec(
            task_id=task.task_id,
            project_id="project_1",
            user_query=task.user_query,
            intent="kb_query",
            task_type="kb_summary",
            required_skills=["core_build_user_research_kb"],
            allowed_tools=["rag_query"],
            expected_outputs=["structured_outputs"],
            validation_rules=["return evidence"],
            context_package={"task_brief": task.user_query},
        )
        output_file = self.tmp / "research_tasks" / task.task_id / "answer.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text('{"answer": "ok"}', encoding="utf-8")
        result = ExecutionResult(
            task_id=task.task_id,
            skillrun_id="skillrun_1",
            status="success",
            summary="Execution completed.",
            output_files=[str(output_file)],
            structured_outputs={"answer": "ok"},
            sources=[{"source_id": "source_1"}],
        )

        goal = build_goal(task.user_query, task.project_id, spec.intent, {"warnings": []})
        contract = build_contract_from_task_spec(spec)
        artifacts = collect_artifacts_from_execution(result, spec)
        execution = execution_result_to_payload(result, artifacts)
        validation = validate_task_outputs(result, spec, contract, {"valid": True, "safe_to_promote": True})
        memory_commit = build_memory_commit_record({}, {"pages": [{"page_type": "dataset", "path": "brain/page.md"}]})

        self.store.write_goal(task, goal)
        self.store.write_plan(task, build_plan_markdown(spec, {"pipeline_name": "kb_summary"}))
        self.store.write_contract(task, contract)
        self.store.mark_running(task)
        self.store.write_execution(task, execution)
        self.store.write_artifacts(task, artifacts)
        self.store.write_validation(task, validation)
        self.store.write_memory_commit(task, memory_commit)
        self.store.write_handoff(task, compose_handoff(task))

        task_dir = self.store.task_dir(task.task_id)
        for filename in [
            "task.json",
            "goal.json",
            "plan.md",
            "contract.json",
            "execution_result.json",
            "artifacts.json",
            "validation_report.json",
            "handoff.md",
            "memory_commit.json",
            "events.jsonl",
        ]:
            self.assertTrue((task_dir / filename).exists(), filename)
        self.assertEqual(json.loads((task_dir / "execution_result.json").read_text(encoding="utf-8"))["skillrun_id"], "skillrun_1")
        self.assertTrue(json.loads((task_dir / "artifacts.json").read_text(encoding="utf-8"))[0]["hash"])
        self.assertIn("handoff_written", (task_dir / "events.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
