import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class ResearchAgentApiDualAgentGateTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("RESEARCHOS_DUAL_AGENT_API_ENABLED", None)

    def test_dual_agent_api_defaults_to_disabled(self) -> None:
        os.environ.pop("RESEARCHOS_DUAL_AGENT_API_ENABLED", None)

        self.assertFalse(api.dual_agent_api_enabled())

    def test_dual_agent_paths_are_recognized(self) -> None:
        self.assertTrue(api.is_dual_agent_get_path("/api/skills/catalog"))
        self.assertTrue(api.is_dual_agent_get_path("/api/demo/dual-agent"))
        self.assertTrue(api.is_dual_agent_post_path("/api/agents/coordinator/run"))
        self.assertTrue(api.is_dual_agent_post_path("/api/brain/skillrun/run-1/process"))
        self.assertTrue(api.is_dual_agent_post_path("/api/self-evolution/skills/example/activate"))
        self.assertFalse(api.is_dual_agent_get_path("/research-os/agent/chat"))

    def test_workspace_root_resolution_does_not_require_legacy_client(self) -> None:
        self.assertEqual(api.resolve_workspace_root(SCRIPTS / "research_agent_api.py"), ROOT)

    def test_safe_error_message_redacts_paths_and_secret_values(self) -> None:
        message = api.safe_error_message(ValueError(r"failed at C:\Users\11710\.env token=abc123 password=hunter2"))

        self.assertNotIn(r"C:\Users", message)
        self.assertNotIn("abc123", message)
        self.assertNotIn("hunter2", message)

    def test_normalized_coordinator_response_contains_stable_fields(self) -> None:
        response = api.normalize_dual_agent_result({"ok": True, "execution_result": {"status": "success", "skillrun_id": "sr1"}})

        for key in [
            "ok",
            "task_spec",
            "execution_result",
            "brain_decision",
            "validation_report",
            "promotion_decision",
            "memory_update",
            "memory_pages",
            "pending_skill",
            "resolver_health",
            "handoff",
            "summary",
        ]:
            self.assertIn(key, response)


if __name__ == "__main__":
    unittest.main()
