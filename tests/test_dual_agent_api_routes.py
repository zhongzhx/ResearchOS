import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
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

    def test_coordinator_endpoint_delegates_ordinary_chat_to_mvp_runtime(self) -> None:
        fake_mvp = MagicMock()
        fake_mvp.agent_chat.return_value = {"ok": True, "answer": "MVP normal chat answer"}

        with patch("backend.researchos.api.dual_agent_routes.import_research_os_mvp", return_value=fake_mvp):
            response = asyncio.run(coordinator_run_endpoint({"user_query": "你好", "project_id": self.project["id"]}))

        self.assertTrue(response["ok"])
        self.assertEqual(response["mode"], "mvp_chat_fallback")
        self.assertEqual(response["answer"], "MVP normal chat answer")
        fake_mvp.agent_chat.assert_called_once()

    def test_coordinator_endpoint_delegates_memory_and_history_questions_to_mvp_runtime(self) -> None:
        fake_mvp = MagicMock()
        fake_mvp.agent_chat.return_value = {"ok": True, "answer": "MVP memory answer"}

        with patch("backend.researchos.api.dual_agent_routes.import_research_os_mvp", return_value=fake_mvp):
            memory_response = asyncio.run(coordinator_run_endpoint({"user_query": "你有什么记忆机制", "project_id": self.project["id"]}))
            first_message_response = asyncio.run(coordinator_run_endpoint({"user_query": "我和你对话的第一句话是什么", "project_id": self.project["id"]}))
            capabilities_response = asyncio.run(coordinator_run_endpoint({"user_query": "你有什么功能", "project_id": self.project["id"]}))

        self.assertEqual(memory_response["mode"], "mvp_chat_fallback")
        self.assertEqual(first_message_response["mode"], "mvp_chat_fallback")
        self.assertEqual(capabilities_response["mode"], "mvp_chat_fallback")
        self.assertEqual(fake_mvp.agent_chat.call_count, 3)

    def test_skill_library_and_pipeline_routes(self) -> None:
        catalog = asyncio.run(skill_catalog_endpoint())
        pipelines = asyncio.run(pipeline_registry_endpoint())
        routed = asyncio.run(route_skill_query_endpoint({"user_query": "帮我下载先天免疫文献"}))

        self.assertTrue(catalog["ok"])
        self.assertGreater(catalog["count"], 0)
        self.assertTrue(any(row["skill_id"] == "skill-router-orchestrator" for row in catalog["skills"]))
        self.assertTrue(pipelines["ok"])
        self.assertTrue(any(row["pipeline_name"] == "literature_harvest" for row in pipelines["pipelines"]))
        self.assertEqual(routed["source"], "mvp_runtime")
        self.assertEqual(routed["pipeline"]["source"], "mvp_prompt_router")
        self.assertEqual(routed["pipeline"]["pipeline_name"], routed["mvp_prompt_routing"]["task_type"])


if __name__ == "__main__":
    unittest.main()
