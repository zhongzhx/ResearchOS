from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BackendConsolidationAuditTests(unittest.TestCase):
    def test_audit_doc_records_mvp_trunk_and_recommended_order(self) -> None:
        audit = ROOT / "backend_consolidation_audit.md"

        self.assertTrue(audit.exists())
        text = audit.read_text(encoding="utf-8")
        self.assertIn("research_agent_api.py", text)
        self.assertIn("/research-os/agent/chat", text)
        self.assertIn("researchos_agent_system_prompt.md", text)
        self.assertIn("MVP Runtime Source of Truth Policy", text)
        self.assertIn("Duplicate behavior must prefer the MVP runtime", text)
        self.assertIn("backend/researchos is a service library and adapter layer", text)
        self.assertIn("Recommended Fusion Order", text)

    def test_mvp_trunk_directory_exists(self) -> None:
        trunk = ROOT / "backend" / "research_agent_runtime" / "scripts"

        self.assertTrue(trunk.exists())
        self.assertTrue((trunk / "research_agent_api.py").exists())
        self.assertTrue((trunk / "research_os_mvp.py").exists())


if __name__ == "__main__":
    unittest.main()
