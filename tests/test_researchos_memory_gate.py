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


class ResearchOSMemoryGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_memory_gate_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Memory Gate Project", "research_area": "immune regulation"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def project_memories(self) -> list[dict]:
        return ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)["entries"]

    def test_beginner_expression_is_session_context_not_user_name(self) -> None:
        gate = ros.classify_memory_candidate("我是免疫学小白", {"project_id": self.project["id"]})
        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "我是免疫学小白"})

        self.assertFalse(gate["should_save"])
        self.assertEqual(gate["memory_layer"], "session_context")
        self.assertEqual(gate["memory_type"], "explanation_level")
        self.assertEqual(gate["normalized_content"], "explanation_level: beginner")
        self.assertNotIn(response["intent"], ros.PROFILE_UPDATE_INTENTS)
        self.assertFalse(any(memory["memory_type"] == "user_profile" for memory in self.project_memories()))

    def test_explicit_name_is_high_confidence_user_profile(self) -> None:
        gate = ros.classify_memory_candidate("我叫张三", {"project_id": self.project["id"]})
        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "我叫张三"})

        self.assertTrue(gate["should_save"])
        self.assertEqual(gate["memory_layer"], "user_profile")
        self.assertEqual(gate["memory_type"], "user_name")
        self.assertEqual(gate["normalized_content"], "user_name: 张三")
        self.assertEqual(response["intent"], "user_profile_update")
        self.assertTrue(any(memory["memory_type"] == "user_profile" for memory in self.project_memories()))

    def test_task_status_and_api_key_questions_do_not_write_long_term_memory(self) -> None:
        for message in ["现在采集到哪了？", "API key 怎么配置？"]:
            with self.subTest(message=message):
                gate = ros.classify_memory_candidate(message, {"project_id": self.project["id"]})
                self.assertFalse(gate["should_save"])
                self.assertEqual(gate["memory_layer"], "none")

    def test_auto_weekly_digest_is_pending_candidate_and_confirmation_writes_project_memory(self) -> None:
        task = ros.create_task(self.agent_root, {"project_id": self.project["id"], "task_type": "weekly_research_digest", "user_goal": "Weekly digest"})
        ros.run_research_workflow_task(self.agent_root, task["task_id"])
        candidates = ros.list_pending_memory_candidates(self.agent_root, self.project["id"])

        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["status"], "pending")
        committed = ros.commit_pending_memory_candidate(self.agent_root, candidates[0]["candidate_id"])

        self.assertTrue(committed["committed"])
        self.assertEqual(committed["memory_type"], "weekly_digest")
        memory = committed["memory"]
        self.assertEqual(memory["source_type"], "research_artifact")
        self.assertEqual(memory["source_id"], committed["source_artifact"])
        self.assertEqual(memory["structured_content"]["evidence_level"], committed["evidence_level"])

    def test_explicit_failure_reason_commit_enters_project_memory_with_source(self) -> None:
        artifact = ros.create_artifact(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "artifact_type": "failure_summary",
                "title": "ELISA failure reason",
                "content_markdown": "ELISA failed because the standard curve was prepared with the wrong dilution.",
                "status": "pending_confirmation",
                "source_type": "agent_chat",
                "source_refs": [{"type": "chat", "id": "failure-note"}],
                "evidence_level": "user_confirmed",
            },
        )
        candidate = ros.list_pending_memory_candidates(self.agent_root, self.project["id"])[0]
        committed = ros.commit_pending_memory_candidate(self.agent_root, candidate["candidate_id"])

        self.assertEqual(artifact["artifact_type"], "failure_summary")
        self.assertEqual(committed["memory_type"], "failure_record")
        self.assertTrue(committed["memory_id"])
        self.assertEqual(committed["memory"]["source_id"], artifact["artifact_id"])
        self.assertEqual(committed["memory"]["structured_content"]["evidence_level"], "user_confirmed")

    def test_unconfirmed_experiment_suggestion_becomes_candidate_not_memory(self) -> None:
        artifact = ros.create_artifact(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "artifact_type": "experiment_plan",
                "title": "Dose response experiment idea",
                "content_markdown": "Try 10, 25, and 50 ug/mL as a draft dose response plan.",
                "status": "pending_confirmation",
                "evidence_level": "agent_generated_needs_review",
            },
        )

        candidates = ros.list_pending_memory_candidates(self.agent_root, self.project["id"])
        self.assertEqual(candidates[0]["artifact_id"], artifact["artifact_id"])
        self.assertFalse(self.project_memories())


if __name__ == "__main__":
    unittest.main()
