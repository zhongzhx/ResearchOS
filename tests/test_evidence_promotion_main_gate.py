import unittest
from unittest.mock import MagicMock

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.agents.brain_agent import ResearchBrainAgent


class EvidencePromotionMainGateTests(unittest.TestCase):
    def test_brain_memory_commit_accepts_promotion_decision_not_raw_execution_result(self) -> None:
        agent = ResearchBrainAgent()
        result = ExecutionResult(task_id="task1", status="success", summary="claim: mechanism", structured_outputs={"claim_text": "NF-kB activates marker X"})
        spec = TaskSpec(task_id="task1", project_id="p1", user_query="u", task_type="writing_review")
        pipeline = {"pipeline_name": "writing_review", "promotion_targets": ["claims"]}

        promotion = agent.promote_execution_result(result, spec, pipeline)
        with unittest.mock.patch("backend.researchos.brain.memory_writer.write_memory_from_execution_result", MagicMock(side_effect=AssertionError("raw write bypassed"))):
            commit = agent.commit_promoted_memory(promotion)

        self.assertEqual(commit["control_skill"], "memory_commit")


if __name__ == "__main__":
    unittest.main()
