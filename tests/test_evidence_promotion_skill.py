import unittest

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.brain.evidence_promotion import promote_skill_outputs_to_brain
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent


class EvidencePromotionSkillTests(unittest.TestCase):
    def test_promotion_result_records_control_skill_name(self) -> None:
        pipeline = get_pipeline_for_intent("literature_harvest")
        spec = TaskSpec(project_id="p1", user_query="download", intent="literature_harvest", task_type="literature_harvest")
        result = ExecutionResult(task_id=spec.task_id, status="success", summary="papers indexed", sources=[{"source_id": "ref1"}])

        promoted = promote_skill_outputs_to_brain(result, spec, pipeline)

        self.assertEqual(promoted["control_skill"], "evidence-promotion")
        self.assertIn("papers", promoted["targets"])


if __name__ == "__main__":
    unittest.main()
