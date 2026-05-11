import os
import shutil
import unittest
import uuid
from pathlib import Path

from backend.researchos.execution.runtime_adapter import import_research_os_mvp, scripts_dir
from backend.researchos.skills.pipeline_registry import load_skill_catalog


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNTIME_SCRIPTS = (
    ROOT
    / "skills"
    / "researchos_skill_library"
    / "01_core_runtime_memory"
    / "research-agent-runtime"
    / "scripts"
)


class RuntimeSkillDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp_root = ROOT / ".tmp" / "tests"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tmp_root / f"aura_runtime_discovery_{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")

    def tearDown(self) -> None:
        for key in ["RESEARCHOS_AGENT_ROOT", "RESEARCH_BRAIN_ROOT", "RESEARCHOS_SKILLS_ROOT"]:
            os.environ.pop(key, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_runtime_adapter_uses_canonical_classified_runtime_skill(self) -> None:
        self.assertEqual(scripts_dir(), CANONICAL_RUNTIME_SCRIPTS)
        self.assertTrue((scripts_dir() / "research_os_mvp.py").exists())
        self.assertIsNotNone(import_research_os_mvp())

    def test_backend_prompt_router_loads_skill_instructions_from_classified_library(self) -> None:
        ros = import_research_os_mvp()
        agent_root = Path(os.environ["RESEARCHOS_AGENT_ROOT"])

        routed = ros.simulate_prompt_routing(
            agent_root,
            {
                "user_message": "帮我用关键词采集文献",
                "skill_name": "keyword-research-harvest",
                "prompt_language": "zh",
            },
        )

        self.assertEqual(routed["resolved_skill_name"], "Keyword Research Harvest")
        self.assertEqual(routed["skill_prompt_source"], "skill_registry")
        self.assertTrue(
            any(str(path).replace("\\", "/").endswith("keyword-research-harvest/SKILL.md") for path in routed["prompt_files"]),
            routed["prompt_files"],
        )

    def test_catalog_skill_slug_can_execute_through_skillrun_registry(self) -> None:
        ros = import_research_os_mvp()
        agent_root = Path(os.environ["RESEARCHOS_AGENT_ROOT"])
        project = ros.create_project(agent_root, {"title": "Skill bridge", "research_area": "demo"})

        result = ros.run_skill(
            agent_root,
            "compliant-literature-access",
            project_id=project["id"],
            input_payload={"project_id": project["id"], "doi": "10.1000/example"},
        )

        self.assertEqual(result["skill_run"]["skill_id"], "compliant-literature-access")
        prompt_files = str(result["skill_run"]["prompt_files"]).replace("\\", "/")
        while "//" in prompt_files:
            prompt_files = prompt_files.replace("//", "/")
        self.assertIn("compliant-literature-access//SKILL.md".replace("//", "/"), prompt_files)

    def test_runtime_registry_knows_every_real_catalog_skill_id(self) -> None:
        ros = import_research_os_mvp()
        agent_root = Path(os.environ["RESEARCHOS_AGENT_ROOT"])

        registered = {row["skill_id"] for row in ros.list_skills(agent_root, include_disabled=True)}
        catalog = load_skill_catalog()
        real_catalog_ids = {
            skill_id
            for skill_id, row in catalog.items()
            if "{" not in str(row.get("canonical_path") or "")
        }

        self.assertTrue(real_catalog_ids.issubset(registered), sorted(real_catalog_ids - registered))

    def test_browser_tool_capability_sources_use_classified_skill_paths(self) -> None:
        ros = import_research_os_mvp()
        agent_root = Path(os.environ["RESEARCHOS_AGENT_ROOT"])

        capabilities = ros.list_tool_capabilities(agent_root)
        browser_sources = [Path(row["source_path"]) for row in capabilities if str(row.get("capability_id", "")).startswith("tool_")]

        self.assertTrue(browser_sources)
        self.assertTrue(all(path.exists() for path in browser_sources), [str(path) for path in browser_sources if not path.exists()])


if __name__ == "__main__":
    unittest.main()
