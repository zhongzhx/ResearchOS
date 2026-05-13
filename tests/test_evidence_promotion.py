import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.brain.evidence_promotion import promote_skill_outputs_to_brain, validate_before_promotion
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent


class EvidencePromotionTests(unittest.TestCase):
    def test_literature_harvest_promotes_papers_and_project_memory(self) -> None:
        pipeline = get_pipeline_for_intent("literature_harvest")
        spec = TaskSpec(project_id="p1", user_query="download papers", intent="literature_harvest", task_type="literature_harvest")
        result = ExecutionResult(
            task_id=spec.task_id,
            skillrun_id="sr1",
            status="success",
            summary="papers indexed",
            structured_outputs={"paper_table": [{"title": "Paper A", "source_id": "pmid1"}]},
            sources=[{"source_id": "pmid1"}],
        )

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertIn("papers", promoted["accepted_targets"])
        self.assertIn("project memory", promoted["accepted_targets"])
        self.assertFalse(promoted["rejected_items"])

    def test_browser_learning_outputs_are_low_confidence_notes_only(self) -> None:
        pipeline = get_pipeline_for_intent("browser_research_learning")
        spec = TaskSpec(project_id="p1", user_query="learn page", intent="browser_research_learning", task_type="browser_research_learning")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="Browser observed a method.")

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertEqual(promoted["targets"], ["browser_learning_evidence", "project_memory_low_confidence_notes"])
        self.assertFalse(promoted["high_confidence_claim_allowed"])
        self.assertTrue(all(item["confidence"] == "low" for item in promoted["memory_items"]))

    def test_peer_review_output_is_not_fact_evidence(self) -> None:
        pipeline = get_pipeline_for_intent("writing_review")
        spec = TaskSpec(project_id="p1", user_query="review", intent="writing_review", task_type="writing_review")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="Reviewer criticism.")

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertIn("unresolved_issues", promoted["targets"])
        self.assertIn("criticism", promoted["accepted_targets"])
        self.assertFalse(promoted["fact_evidence_allowed"])
        self.assertFalse(any(item["page_type"] == "claim" for item in promoted["memory_items"]))

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

    def test_mechanism_claim_without_source_ids_is_downgraded_to_hypothesis(self) -> None:
        pipeline = get_pipeline_for_intent("data_analysis_to_narrative")
        spec = TaskSpec(project_id="p1", user_query="mechanism", intent="data_analysis_to_narrative", task_type="data_analysis_to_narrative")
        result = ExecutionResult(
            task_id=spec.task_id,
            skillrun_id="sr1",
            status="success",
            summary="Claim: TLR4 activates NF-kB in macrophages.",
            structured_outputs={"claim_text": "TLR4 activates NF-kB in macrophages."},
        )

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        claim_items = [item for item in promoted["memory_items"] if item["page_type"] == "claim"]
        self.assertTrue(claim_items)
        self.assertEqual(claim_items[0]["confidence"], "low")
        self.assertIn("Hypothesis:", claim_items[0]["compiled_truth"])
        self.assertTrue(promoted["required_human_review"])

    def test_secret_detection_rejects_promotion(self) -> None:
        pipeline = get_pipeline_for_intent("literature_harvest")
        spec = TaskSpec(project_id="p1", user_query="download", intent="literature_harvest", task_type="literature_harvest")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="api key sk-test leaked")

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertEqual(promoted["accepted_targets"], [])
        self.assertTrue(promoted["rejected_items"])
        self.assertTrue(promoted["required_human_review"])

    def test_raw_logs_are_not_promoted_as_memory_items(self) -> None:
        pipeline = get_pipeline_for_intent("literature_harvest")
        spec = TaskSpec(project_id="p1", user_query="download", intent="literature_harvest", task_type="literature_harvest")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="papers indexed", logs=["raw compiled truth from logs"])

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertFalse(any("raw compiled truth" in item.get("compiled_truth", "") for item in promoted["memory_items"]))


if __name__ == "__main__":
    unittest.main()
