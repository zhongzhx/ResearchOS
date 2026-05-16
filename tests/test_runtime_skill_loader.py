import unittest
from pathlib import Path
from unittest.mock import patch

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.agents.execution_agent import ResearchExecutionAgent
from backend.researchos.skills.runtime_skill_loader import (
    build_execution_skill_context,
    load_selected_skill_docs,
    load_skill_runtime_files,
)


ROOT = Path(__file__).resolve().parents[1]


class RuntimeSkillLoaderTests(unittest.TestCase):
    def test_load_selected_skill_docs_only_loads_required_skills(self) -> None:
        read_paths: list[Path] = []
        original_read_text = Path.read_text

        def tracked_read_text(path: Path, *args, **kwargs):
            if path.name == "SKILL.md":
                read_paths.append(path)
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked_read_text):
            docs = load_selected_skill_docs(["parse-scientific-data"])

        self.assertEqual(list(docs), ["parse-scientific-data"])
        self.assertEqual(len(read_paths), 1)
        self.assertTrue(str(read_paths[0]).replace("\\", "/").endswith("parse-scientific-data/SKILL.md"))

    def test_runtime_loader_does_not_recursively_read_all_skill_docs(self) -> None:
        with patch("pathlib.Path.rglob", side_effect=AssertionError("runtime loader must not recursively scan")):
            docs = load_selected_skill_docs(["sop-generation"])

        self.assertEqual(list(docs), ["sop-generation"])

    def test_build_execution_skill_context_contains_selected_sections_only(self) -> None:
        context = build_execution_skill_context(["parse-scientific-data"], max_tokens=1000)

        self.assertIn("parse-scientific-data", context)
        self.assertIn("Purpose", context)
        self.assertIn("Inputs", context)
        self.assertIn("Outputs", context)
        self.assertIn("script path", context.lower())
        self.assertNotIn("full_agent_memory", context)
        self.assertNotIn("API_KEY", context)

    def test_load_skill_runtime_files_limits_to_selected_skill_directory(self) -> None:
        files = load_skill_runtime_files("parse-scientific-data")

        self.assertTrue(any(path.endswith("parse_scientific_data.py") for path in files))
        self.assertTrue(all("parse-scientific-data" in path.replace("\\", "/") for path in files))
        self.assertFalse(any(path.endswith(".env") for path in files))

    def test_pending_review_skill_auto_execution_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            load_selected_skill_docs(["generated-skill-template"])

    def test_execution_agent_attaches_only_selected_skill_context(self) -> None:
        agent = ResearchExecutionAgent()
        spec = TaskSpec(
            project_id="p1",
            user_query="分析 CSV",
            intent="data_analysis_to_narrative",
            task_type="data_analysis_to_narrative",
            required_skills=["parse-scientific-data"],
            context_package={"task_brief": "分析 CSV"},
            expected_outputs=["structured_data"],
        )

        with patch("backend.researchos.agents.execution_agent.load_selected_skill_docs") as load_docs:
            load_docs.return_value = {"parse-scientific-data": {"skill_id": "parse-scientific-data", "sections": {}}}
            with patch("backend.researchos.agents.execution_agent.build_execution_skill_context", return_value="selected skill context"):
                with patch("backend.researchos.agents.execution_agent.run_execution_plan", return_value={"ok": True, "outputs": {}, "logs": [], "sources": [], "output_files": []}):
                    agent.execute_task(spec)

        load_docs.assert_called_once_with(["parse-scientific-data"])
        self.assertEqual(spec.context_package["active_skill_instructions"], ["selected skill context"])
        self.assertNotIn("full_skill_catalog", spec.context_package)
        self.assertNotIn("full_skill_docs", spec.context_package)


if __name__ == "__main__":
    unittest.main()
