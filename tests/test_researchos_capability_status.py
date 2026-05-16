import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class ResearchOSCapabilityStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_capability_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Capability Audit Project", "research_area": "immune regulation"})

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_capability_status_returns_required_modules(self) -> None:
        status = ros.get_researchos_capability_status(self.agent_root, self.project["id"])

        for key in [
            "project_context",
            "skill_registry",
            "intent_router",
            "context_compiler",
            "long_task_runner",
            "literature_harvest",
            "kb_rag",
            "project_memory",
            "memory_source_of_truth",
            "execution_memory",
            "artifact_store",
            "response_formatter",
        ]:
            self.assertIn(status[key], {"real", "mock", "missing", "partial"})
        self.assertIsInstance(status["known_gaps"], list)
        self.assertIsInstance(status["recommended_next_fixes"], list)
        self.assertIn("details", status)

    def test_missing_schema_is_marked_missing(self) -> None:
        conn = ros.connect(self.agent_root)
        try:
            conn.execute("DROP TABLE artifacts")
            conn.commit()
        finally:
            conn.close()

        status = ros.get_researchos_capability_status(self.agent_root, self.project["id"])

        self.assertEqual(status["artifact_store"], "missing")
        self.assertTrue(any("artifact" in gap.lower() for gap in status["known_gaps"]))

    def test_mock_or_fallback_capability_is_not_reported_as_real(self) -> None:
        status = ros.get_researchos_capability_status(self.agent_root, self.project["id"])

        self.assertIn(status["literature_harvest"], {"partial", "mock"})
        self.assertIn("mock/manual fallback", " ".join(status["known_gaps"]).lower())

    def test_capability_audit_does_not_break_chat_and_rag(self) -> None:
        ros.get_researchos_capability_status(self.agent_root, self.project["id"])

        chat = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "What project are we working on?"})
        rag = ros.query_research_rag(self.agent_root, {"project_id": self.project["id"], "question": "immune regulation"})

        self.assertTrue(chat["ok"])
        self.assertIn("query_id", rag)


if __name__ == "__main__":
    unittest.main()
