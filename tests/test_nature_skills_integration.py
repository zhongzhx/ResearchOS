import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.agents.agent_protocol import TaskSpec  # noqa: E402
from backend.researchos.agents.execution_agent import ResearchExecutionAgent  # noqa: E402
from backend.researchos.execution.skill_dispatcher import resolve_required_skill  # noqa: E402
from backend.researchos.skills.pipeline_registry import load_skill_catalog, route_query_to_pipeline  # noqa: E402


class NatureSkillsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_nature_skills_"))
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Nature Skills", "research_area": "writing"})

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_catalog_contains_nature_skills_with_existing_paths(self) -> None:
        catalog = load_skill_catalog()
        expected = {
            "nature-citation",
            "nature-data",
            "nature-figure",
            "nature-paper2ppt",
            "nature-polishing",
            "nature-response",
        }

        self.assertTrue(expected.issubset(set(catalog)))
        for skill_id in expected:
            self.assertTrue((ROOT / catalog[skill_id]["canonical_path"]).exists(), skill_id)

    def test_pipeline_routes_nature_queries(self) -> None:
        cases = {
            "please make a Nature figure": "nature_figure_generation",
            "\u8bf7\u5e2e\u6211\u7ed9\u8fd9\u6bb5\u8bdd\u8865\u5f15\u7528": "nature_citation_support",
            "\u5e2e\u6211\u5199 Data Availability": "nature_data_availability",
            "\u5ba1\u7a3f\u610f\u89c1\u56de\u590d": "nature_reviewer_response",
            "\u505a\u6587\u732e\u6c47\u62a5PPT": "nature_paper_to_ppt",
            "\u8bba\u6587\u6da6\u8272": "nature_academic_polishing",
        }

        for query, pipeline_name in cases.items():
            self.assertEqual(route_query_to_pipeline(query)["pipeline_name"], pipeline_name)

    def test_nature_skill_is_registered_and_executable(self) -> None:
        resolved = resolve_required_skill("nature-polishing", agent_root=self.agent_root)
        self.assertEqual(resolved["skill_id"], "nature-polishing")

        result = ResearchExecutionAgent(agent_root=self.agent_root).execute_task(
            TaskSpec(
                project_id=self.project["id"],
                user_query="polish manuscript paragraph",
                intent="nature_academic_polishing",
                task_type="nature_academic_polishing",
                required_skills=["nature-polishing"],
                context_package={"task_brief": "polish manuscript paragraph"},
                expected_outputs=["polished_text", "revision_notes", "risk_flags"],
            )
        )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.skillrun_id)


if __name__ == "__main__":
    unittest.main()
