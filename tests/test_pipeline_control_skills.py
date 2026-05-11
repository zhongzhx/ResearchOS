import unittest
from pathlib import Path

from backend.researchos.skills.pipeline_registry import list_pipelines


ROOT = Path(__file__).resolve().parents[1]


class PipelineControlSkillsTests(unittest.TestCase):
    def test_resolver_documents_system_control_skills(self) -> None:
        resolver = (ROOT / "skills" / "RESOLVER.md").read_text(encoding="utf-8")

        self.assertIn("## System Control Skills", resolver)
        self.assertIn("skill_router_orchestrator", resolver)
        self.assertIn("context_compiler_maintenance", resolver)
        self.assertIn("skill_output_validator", resolver)
        self.assertIn("evidence_promotion", resolver)

    def test_every_pipeline_has_pre_dispatch_and_post_execution_control_skills(self) -> None:
        for pipeline in list_pipelines():
            control = pipeline.get("control_skills") or {}
            self.assertEqual(control.get("pre_dispatch"), ["skill-router-orchestrator", "context-compiler-maintenance"])
            self.assertEqual(control.get("post_execution"), ["skill-output-validator", "evidence-promotion"])


if __name__ == "__main__":
    unittest.main()
