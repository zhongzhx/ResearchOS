import unittest


class EvidencePromotionMvpIntegrationTests(unittest.TestCase):
    def test_new_feature_memory_commit_uses_evidence_promotion_gate(self) -> None:
        from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
        from backend.researchos.integration.mvp_memory_bridge import promote_execution_result_for_new_feature

        task_spec = TaskSpec(
            task_id="task_gate",
            task_type="writing_review",
            intent="writing_review",
            project_id="project_a",
            user_query="review writing",
            expected_outputs=["critique"],
        )
        result = ExecutionResult(
            task_id="task_gate",
            status="success",
            summary="Critique only; not evidence.",
            structured_outputs={"critique": "Unsupported causal claim."},
        )
        promotion = promote_execution_result_for_new_feature(result, task_spec, {"pipeline_name": "writing_review", "promotion_targets": ["criticism"]})

        self.assertEqual(promotion["control_skill"], "evidence-promotion")
        self.assertTrue(promotion["required_human_review"])
        self.assertNotIn("api_key", str(promotion).lower())


if __name__ == "__main__":
    unittest.main()
