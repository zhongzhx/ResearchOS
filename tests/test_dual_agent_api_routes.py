import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402
from backend.researchos.api.dual_agent_routes import (  # noqa: E402
    activate_generated_skill_endpoint,
    coordinator_run_endpoint,
    pending_skills_endpoint,
    pipeline_registry_endpoint,
    process_skillrun_endpoint,
    reject_generated_skill_endpoint,
    resolver_check_endpoint,
    route_skill_query_endpoint,
    skill_catalog_endpoint,
)


class DualAgentApiRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_api_routes_"))
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_SKILLS_ROOT"] = str(self.tmp / "skills")
        self.agent_root = Path(os.environ["RESEARCHOS_AGENT_ROOT"])
        self.project = ros.create_project(self.agent_root, {"title": "API", "research_area": "demo"})

    def tearDown(self) -> None:
        for key in ["RESEARCHOS_AGENT_ROOT", "RESEARCH_BRAIN_ROOT", "RESEARCHOS_SKILLS_ROOT"]:
            os.environ.pop(key, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_route_functions_cover_full_flow(self) -> None:
        response = asyncio.run(coordinator_run_endpoint({"user_query": "write report", "project_id": self.project["id"]}))

        self.assertTrue(response["ok"])
        self.assertIn("task_spec", response)
        self.assertIn("post_task_processing", response)

        processed = asyncio.run(process_skillrun_endpoint(response["execution_result"]["skillrun_id"]))
        pending = asyncio.run(pending_skills_endpoint())
        resolver = asyncio.run(resolver_check_endpoint())

        self.assertTrue(processed["ok"])
        self.assertTrue(pending)
        self.assertIn("resolver_entries", resolver)

        name = pending[0]["name"]
        active = asyncio.run(activate_generated_skill_endpoint(name))
        self.assertEqual(active["status"], "active")

        response2 = asyncio.run(coordinator_run_endpoint({"user_query": "write report again", "project_id": self.project["id"]}))
        pending2 = asyncio.run(pending_skills_endpoint())
        rejected = asyncio.run(reject_generated_skill_endpoint(pending2[0]["name"], {"reason": "manual rejection"}))
        self.assertEqual(rejected["rejection_reason"], "manual rejection")

    def test_skill_library_and_pipeline_routes(self) -> None:
        catalog = asyncio.run(skill_catalog_endpoint())
        pipelines = asyncio.run(pipeline_registry_endpoint())
        routed = asyncio.run(route_skill_query_endpoint({"user_query": "帮我下载先天免疫文献"}))

        self.assertTrue(catalog["ok"])
        self.assertGreater(catalog["count"], 0)
        self.assertTrue(any(row["skill_id"] == "skill-router-orchestrator" for row in catalog["skills"]))
        self.assertTrue(pipelines["ok"])
        self.assertTrue(any(row["pipeline_name"] == "literature_harvest" for row in pipelines["pipelines"]))
        self.assertEqual(routed["pipeline"]["pipeline_name"], "literature_harvest")


if __name__ == "__main__":
    unittest.main()
