import shutil
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.agents.agent_protocol import TaskSpec  # noqa: E402
from backend.researchos.agents.execution_agent import ResearchExecutionAgent  # noqa: E402
from backend.researchos.execution.skill_dispatcher import resolve_required_skill  # noqa: E402


class ExecutionAgentSkillPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = ROOT / ".tmp" / "tests"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tmp_root / f"aura_skill_pipeline_{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.agent_root = self.tmp / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Pipeline", "research_area": "test"})
        for skill_id in ["compliant-literature-access", "extract-first-article-keywords", "build-user-research-kb"]:
            ros.upsert_skill(
                self.agent_root,
                {
                    "skill_id": skill_id,
                    "skill_name": skill_id,
                    "handler": "promoted_execution_memory",
                    "status": "active",
                    "source_path": f"{skill_id}/SKILL.md",
                },
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_resolve_required_skill_prefers_canonical_path(self) -> None:
        resolved = resolve_required_skill("parse-scientific-data/SKILL.md", agent_root=self.agent_root)

        self.assertTrue(resolved["canonical_path"].endswith("04_data_analysis_writing_review/parse-scientific-data/SKILL.md"))

    def test_execution_agent_runs_pipeline_skills_in_order(self) -> None:
        agent = ResearchExecutionAgent(agent_root=self.agent_root)
        spec = TaskSpec(
            project_id=self.project["id"],
            user_query="download literature",
            intent="literature_harvest",
            task_type="literature_harvest",
            required_skills=["compliant-literature-access", "extract-first-article-keywords", "build-user-research-kb"],
            allowed_tools=[],
            context_package={"task_brief": "download literature"},
            expected_outputs=["paper_table", "downloaded_pdfs", "ingestion_status"],
        )

        result = agent.execute_task(spec)

        self.assertEqual(result.status, "success")
        skill_results = result.structured_outputs["skill_results"]
        self.assertEqual([item["skill_name"] for item in skill_results], spec.required_skills)
        self.assertTrue(result.skillrun_id)


if __name__ == "__main__":
    unittest.main()
