import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.agents.brain_agent import ResearchBrainAgent


class BrainAgentMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_brain_agent_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_brain_agent_writes_memory_from_accepted_result(self) -> None:
        brain = ResearchBrainAgent()
        spec = TaskSpec(project_id="p1", user_query="summarize", intent="kb_query", task_type="kb_summary", context_package={"task_brief": "summarize"})
        result = ExecutionResult(task_id=spec.task_id, skillrun_id="sr1", status="success", summary="Claim: X has evidence.", structured_outputs={"claim_text": "X has evidence."}, sources=[{"source_id": "src1"}])
        decision = brain.evaluate_execution_result(result, spec)

        written = brain.write_memory_from_result(result, decision, spec)
        graph = brain.update_research_graph("p1")
        index = brain.update_context_index("p1")

        self.assertTrue(written["pages"])
        self.assertIn("edge_count", graph)
        self.assertEqual(index["project_id"], "p1")

    def test_failed_result_writes_failure_only(self) -> None:
        brain = ResearchBrainAgent()
        spec = TaskSpec(project_id="p1", user_query="run", intent="start_skill_request", task_type="generic_skill_task", context_package={"task_brief": "run"})
        result = ExecutionResult(task_id=spec.task_id, status="failed", summary="failed", errors=["boom"])
        decision = brain.evaluate_execution_result(result, spec)

        written = brain.write_memory_from_result(result, decision, spec)

        self.assertEqual([item["page_type"] for item in written["pages"]], ["failure"])


if __name__ == "__main__":
    unittest.main()
