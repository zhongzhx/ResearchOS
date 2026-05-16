import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class CoordinatorPlaceholderFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_coord_fallback_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {key: os.environ.get(key) for key in ["RESEARCHOS_DUAL_AGENT_API_ENABLED"]}
        os.environ["RESEARCHOS_DUAL_AGENT_API_ENABLED"] = "true"
        api.CONFIG = api.RuntimeConfig(self.agent_root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        if self.previous_config is not None:
            api.CONFIG = self.previous_config
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _post_json(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + "/api/agents/coordinator/run",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.assertEqual(response.status, 200)
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.fail(f"unexpected HTTP {exc.code}: {exc.read().decode('utf-8')}")

    def test_placeholder_success_falls_back_to_mvp_chat(self) -> None:
        placeholder = {
            "ok": True,
            "answer": "Execution completed. task_type=research_planning",
            "task_spec": {"task_type": "research_planning", "user_query": "\u4f60\u597d\uff0c\u4f60\u73b0\u5728\u53ef\u4ee5\u6b63\u5e38\u56de\u7b54\u5417\uff1f"},
            "execution_result": {"status": "success", "summary": "Execution completed. task_type=research_planning"},
            "research_task": {"artifacts": []},
            "artifacts": [],
            "memory_pages": [],
            "pending_skill": {"name": "Generated Research Planning", "status": "pending_review"},
        }

        with patch("backend.researchos.api.dual_agent_routes.coordinator_run", return_value=placeholder), patch.object(
            api.research_os,
            "agent_chat",
            return_value={"ok": True, "answer": "\u6211\u53ef\u4ee5\u6b63\u5e38\u56de\u7b54\u3002", "conversation_id": "c1"},
        ) as legacy_chat:
            result = self._post_json(
                {"user_query": "\u4f60\u597d\uff0c\u4f60\u73b0\u5728\u53ef\u4ee5\u6b63\u5e38\u56de\u7b54\u5417\uff1f", "project_id": "demo_project"}
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "mvp_chat_fallback")
        self.assertEqual(result["fallback_reason"], "coordinator_placeholder_result")
        self.assertIn("answer_source", result)
        self.assertIn("llm_called", result)
        self.assertEqual(result["answer"], "\u6211\u53ef\u4ee5\u6b63\u5e38\u56de\u7b54\u3002")
        self.assertNotIn("Execution completed", result["answer"])
        self.assertEqual(result["coordinator_result"]["hidden_in_ui"], True)
        legacy_chat.assert_called_once()

    def test_general_chat_lightweight_result_falls_back_to_mvp_chat(self) -> None:
        lightweight = {
            "ok": True,
            "intent": "general_chat",
            "answer": "\u4f60\u597d\uff0c\u6211\u5728\u3002\u4f60\u53ef\u4ee5\u76f4\u63a5\u544a\u8bc9\u6211\u8981\u641c\u7d22\u6587\u732e\u3001\u6574\u7406 PDF\u3001\u5206\u6790\u6570\u636e\uff0c\u6216\u8005\u5148\u9009\u62e9\u4e00\u4e2a\u9879\u76ee\u540e\u7ee7\u7eed\u3002",
            "suggested_actions": [],
            "visible_sources": [],
            "warnings": [],
        }

        with patch("backend.researchos.api.dual_agent_routes.coordinator_run", return_value=lightweight), patch.object(
            api.research_os,
            "agent_chat",
            return_value={"ok": True, "answer": "\u8fd9\u662f MVP chat \u56de\u7b54\u3002", "conversation_id": "c2"},
        ) as legacy_chat:
            result = self._post_json({"user_query": "\u4f60\u597d", "project_id": "demo_project"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "mvp_chat_fallback")
        self.assertEqual(result["answer"], "\u8fd9\u662f MVP chat \u56de\u7b54\u3002")
        self.assertEqual(result["fallback_reason"], "coordinator_placeholder_result")
        self.assertIn("answer_source", result)
        legacy_chat.assert_called_once()

    def test_memory_meta_question_handoff_falls_back_to_mvp_chat(self) -> None:
        handoff = {
            "ok": True,
            "answer": "# Research Task Handoff: task_2845f2d88ac6\n\n## \u5b8c\u6210\u4e86\u4ec0\u4e48\n- Execution completed. task_type=research_planning",
            "handoff": "# Research Task Handoff: task_2845f2d88ac6\n\n- Execution completed. task_type=research_planning",
            "task_spec": {"task_type": "research_planning", "user_query": "\u4f60\u6709\u4ec0\u4e48\u8bb0\u5fc6\u673a\u5236"},
            "execution_result": {"status": "success", "summary": "Execution completed. task_type=research_planning", "output_files": []},
            "artifacts": [],
            "memory_pages": [],
            "memory_update": {},
            "memory_commit": {},
            "validation_report": {"confidence": "medium-high", "safe_to_return": True},
        }

        with patch("backend.researchos.api.dual_agent_routes.coordinator_run", return_value=handoff), patch.object(
            api.research_os,
            "agent_chat",
            return_value={"ok": True, "answer": "\u8fd9\u662f MVP \u8bb0\u5fc6\u673a\u5236\u56de\u7b54\u3002", "conversation_id": "c3"},
        ) as legacy_chat:
            result = self._post_json({"user_query": "\u4f60\u6709\u4ec0\u4e48\u8bb0\u5fc6\u673a\u5236", "project_id": "demo_project"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "mvp_chat_fallback")
        self.assertEqual(result["answer"], "\u8fd9\u662f MVP \u8bb0\u5fc6\u673a\u5236\u56de\u7b54\u3002")
        self.assertNotIn("Research Task Handoff", result["answer"])
        legacy_chat.assert_called_once()

    def test_capability_question_handoff_falls_back_to_mvp_chat(self) -> None:
        handoff = {
            "ok": True,
            "answer": "# Research Task Handoff: task_2d7d026135d9\n\n## \u5b8c\u6210\u4e86\u4ec0\u4e48\n- Execution completed. task_type=research_planning",
            "handoff": "# Research Task Handoff: task_2d7d026135d9\n\n- Execution completed. task_type=research_planning",
            "task_spec": {"task_type": "research_planning", "user_query": "\u4f60\u6709\u4ec0\u4e48\u529f\u80fd"},
            "execution_result": {"status": "success", "summary": "Execution completed. task_type=research_planning", "output_files": []},
            "artifacts": [],
            "memory_pages": [],
            "pending_skill": {"name": "Generated Research Planning", "status": "pending_review"},
            "validation_report": {"confidence": "medium-high", "safe_to_return": True},
        }

        with patch("backend.researchos.api.dual_agent_routes.coordinator_run", return_value=handoff), patch.object(
            api.research_os,
            "agent_chat",
            return_value={"ok": True, "answer": "\u8fd9\u662f MVP \u529f\u80fd\u4ecb\u7ecd\u3002", "conversation_id": "c4"},
        ) as legacy_chat:
            result = self._post_json({"user_query": "\u4f60\u6709\u4ec0\u4e48\u529f\u80fd", "project_id": "demo_project"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "mvp_chat_fallback")
        self.assertEqual(result["answer"], "\u8fd9\u662f MVP \u529f\u80fd\u4ecb\u7ecd\u3002")
        self.assertNotIn("Research Task Handoff", result["answer"])
        legacy_chat.assert_called_once()


if __name__ == "__main__":
    unittest.main()
