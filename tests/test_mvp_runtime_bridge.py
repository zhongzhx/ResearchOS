from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]


class MvpRuntimeBridgeTests(unittest.TestCase):
    def test_runtime_bridge_reports_mvp_state(self) -> None:
        from backend.researchos.integration.mvp_runtime_bridge import get_mvp_runtime_state

        state = get_mvp_runtime_state(ROOT / "agent_data")

        self.assertTrue(state["mvp_available"])
        self.assertTrue(state["api_entrypoint"].endswith("research_agent_api.py"))
        self.assertTrue(state["scripts_root"].endswith("scripts"))

    def test_runtime_bridge_wraps_project_api(self) -> None:
        from backend.researchos.integration.mvp_runtime_bridge import list_mvp_projects

        with tempfile.TemporaryDirectory() as tmp:
            result = list_mvp_projects(Path(tmp))

        self.assertIn("projects", result)
        self.assertIsInstance(result["projects"], list)

    def test_skill_route_prefers_mvp_prompt_router_before_new_registry(self) -> None:
        from backend.researchos.integration import mvp_skill_bridge

        fake_mvp = MagicMock()
        fake_mvp.simulate_prompt_routing.return_value = {
            "task_type": "literature_mining",
            "resolved_skill_name": "Keyword Research Harvest",
            "prompt_policy": "literature_rag",
            "skill_prompt_source": "skill_registry",
        }

        with patch("backend.researchos.integration.mvp_skill_bridge.default_agent_root", return_value=ROOT / "agent_data"), patch(
            "backend.researchos.integration.mvp_skill_bridge.import_research_os_mvp",
            return_value=fake_mvp,
        ), patch("backend.researchos.integration.mvp_skill_bridge.route_query_to_pipeline") as new_router:
            result = mvp_skill_bridge.route_skill_query({"query": "search papers about macrophages", "project_id": "demo_project"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "mvp_runtime")
        self.assertEqual(result["mvp_prompt_routing"]["task_type"], "literature_mining")
        self.assertEqual(result["pipeline"]["pipeline_name"], "literature_mining")
        fake_mvp.simulate_prompt_routing.assert_called_once()
        new_router.assert_not_called()


if __name__ == "__main__":
    unittest.main()
