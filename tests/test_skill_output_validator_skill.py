import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.brain.evidence_promotion import validate_skill_output


class SkillOutputValidatorSkillTests(unittest.TestCase):
    def test_validator_redacts_secret_like_outputs_and_blocks_promotion(self) -> None:
        spec = TaskSpec(project_id="p1", user_query="run", intent="data_analysis_to_narrative", task_type="data_analysis_to_narrative")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="API key sk-123 leaked", logs=["token=abc"], structured_outputs={"password": "secret"})

        report = validate_skill_output(result, spec, {"pipeline_name": "data_analysis_to_narrative"})

        self.assertFalse(report["safe_to_promote"])
        self.assertTrue(report["required_human_review"])
        self.assertTrue(report["redacted_outputs"])


if __name__ == "__main__":
    unittest.main()
