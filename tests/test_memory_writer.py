import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import BrainDecision, ExecutionResult, TaskSpec
from backend.researchos.brain.memory_writer import write_memory_from_execution_result


class MemoryWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_memory_writer_"))
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writer_creates_claim_page_for_success_result(self) -> None:
        spec = TaskSpec(project_id="p1", user_query="summarize claim", intent="kb_query", task_type="kb_summary", context_package={"task_brief": "summarize"})
        result = ExecutionResult(task_id=spec.task_id, skillrun_id="sr1", status="success", summary="Claim: X is associated with Y.", sources=[{"source_id": "src1"}], structured_outputs={"claim_text": "X is associated with Y."})
        decision = BrainDecision(decision_type="accept", reason="ok", user_facing_summary="ok")

        written = write_memory_from_execution_result(result, decision, spec)

        self.assertTrue(any(item["page_type"] == "claim" for item in written["pages"]))
        self.assertTrue((self.tmp / "research_brain" / "claims").exists())

    def test_failed_result_only_writes_failure_memory(self) -> None:
        spec = TaskSpec(project_id="p1", user_query="run", intent="start_skill_request", task_type="generic_skill_task", context_package={"task_brief": "run"})
        result = ExecutionResult(task_id=spec.task_id, status="failed", summary="Tool failed", errors=["boom"])
        decision = BrainDecision(decision_type="revise", reason="failed", user_facing_summary="failed")

        written = write_memory_from_execution_result(result, decision, spec)

        self.assertEqual([item["page_type"] for item in written["pages"]], ["failure"])
        self.assertFalse((self.tmp / "research_brain" / "claims").exists())


if __name__ == "__main__":
    unittest.main()
