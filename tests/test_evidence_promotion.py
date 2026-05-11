import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.brain.evidence_promotion import promote_skill_outputs_to_brain, validate_before_promotion
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent


class EvidencePromotionTests(unittest.TestCase):
    def test_browser_learning_outputs_are_low_confidence_notes_only(self) -> None:
        pipeline = get_pipeline_for_intent("browser_research_learning")
        spec = TaskSpec(project_id="p1", user_query="learn page", intent="browser_research_learning", task_type="browser_research_learning")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="Browser observed a method.")

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertEqual(promoted["targets"], ["browser_learning_evidence", "project_memory_low_confidence_notes"])
        self.assertFalse(promoted["high_confidence_claim_allowed"])

    def test_peer_review_output_is_not_fact_evidence(self) -> None:
        pipeline = get_pipeline_for_intent("writing_review")
        spec = TaskSpec(project_id="p1", user_query="review", intent="writing_review", task_type="writing_review")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="Reviewer criticism.")

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertIn("unresolved_issues", promoted["targets"])
        self.assertFalse(promoted["fact_evidence_allowed"])

    def test_failed_result_promotes_only_to_failure_memory(self) -> None:
        pipeline = get_pipeline_for_intent("data_analysis_to_narrative")
        spec = TaskSpec(project_id="p1", user_query="analyze", intent="data_analysis_to_narrative", task_type="data_analysis_to_narrative")
        result = ExecutionResult(task_id=spec.task_id, status="failed", summary="parse failed", errors=["bad csv"])

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertEqual(promoted["targets"], ["failures"])

    def test_missing_statistics_blocks_strong_claim(self) -> None:
        result = ExecutionResult(task_id="t1", status="success", summary="treatment improved cytokines")

        validation = validate_before_promotion(result, "claims")

        self.assertFalse(validation["valid"])
        self.assertIn("statistical evidence", " ".join(validation["issues"]))


if __name__ == "__main__":
    unittest.main()
