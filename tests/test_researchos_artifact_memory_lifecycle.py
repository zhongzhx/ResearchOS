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


class ResearchOSArtifactMemoryLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_artifact_memory_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Artifact Memory Project", "research_area": "immune regulation"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_weekly_digest_task_creates_artifact_and_pending_memory_candidate(self) -> None:
        task = ros.create_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "task_type": "weekly_research_digest",
                "user_goal": "Generate weekly digest",
                "input_json": {"research_interests": "immune regulation"},
            },
        )

        completed = ros.run_research_workflow_task(self.agent_root, task["task_id"])
        artifacts = ros.get_recent_artifacts(self.agent_root, self.project["id"], limit=5)
        candidates = ros.list_pending_memory_candidates(self.agent_root, self.project["id"], limit=5)

        self.assertEqual(completed["status"], "completed")
        self.assertTrue(any(item["artifact_type"] == "weekly_digest" for item in artifacts))
        self.assertTrue(any(item["memory_type"] == "weekly_digest" and item["status"] == "pending" for item in candidates))

    def test_weekly_digest_workflow_creates_artifact_candidate_without_direct_memory_write(self) -> None:
        ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Macrophage NF-kB control in inflammatory signaling",
                "abstract": "NF-kB regulates inflammatory cytokine production in RAW264.7 macrophage models.",
                "year": "2025",
                "doi": "10.0000/test-weekly-digest",
                "source_provider": "manual_fixture",
                "relevance_score": 0.95,
            },
        )
        ros.build_project_research_kb(self.agent_root, {"project_id": self.project["id"], "trigger_watcher_after_ingest": False})

        result = ros.generate_weekly_project_digest(self.agent_root, {"project_id": self.project["id"], "provider": "none"})

        artifact = result["artifact"]
        self.assertEqual(artifact["artifact_type"], "weekly_digest")
        self.assertEqual(artifact["status"], "pending_confirmation")
        self.assertIn("date_range", artifact)
        self.assertIn("weekly_digest", artifact["content_json"])
        self.assertTrue(artifact["source_refs"])
        candidates = ros.list_pending_memory_candidates(self.agent_root, self.project["id"], limit=5)
        self.assertEqual(len([item for item in candidates if item["artifact_id"] == artifact["artifact_id"]]), 1)
        memories = ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)["entries"]
        self.assertFalse(any(item["memory_type"] == "weekly_digest" for item in memories))

    def test_manual_chinese_weekly_digest_trigger_generates_artifact(self) -> None:
        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "\u751f\u6210\u672c\u5468\u7814\u7a76\u5468\u62a5"},
        )

        self.assertEqual(response["intent"], "weekly_digest_generation")
        self.assertEqual(response["artifact"]["artifact_type"], "weekly_digest")
        self.assertEqual(response["artifact"]["status"], "pending_confirmation")
        self.assertTrue(response["memory_candidate"]["candidate_id"])

    def test_commit_weekly_digest_then_retrieve_from_project_memory(self) -> None:
        generated = ros.generate_weekly_project_digest(self.agent_root, {"project_id": self.project["id"], "provider": "none"})

        response = ros.agent_chat(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "message": "\u7eb3\u5165\u9879\u76ee\u8bb0\u5fc6",
                "conversation_state": {"last_artifact_id": generated["artifact"]["artifact_id"]},
            },
        )

        self.assertTrue(response["memory_commit"]["committed"])
        rag = ros.query_research_rag(
            self.agent_root,
            {"project_id": self.project["id"], "question": "\u4e0a\u6b21\u5468\u62a5\u8bf4\u4e86\u4ec0\u4e48", "mode": "weekly_digest"},
        )
        self.assertIn("Weekly Research Digest", rag["answer"])

    def test_weekly_digest_schedule_entry_exists_and_no_config_is_noop(self) -> None:
        result = ros.run_scheduled_weekly_digest(self.agent_root, force=False, project_id=self.project["id"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["outcomes"], [])

    def test_learning_summary_chat_generates_artifact_and_pending_candidate(self) -> None:
        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "\u77e5\u8bc6\u5e93\u65b0\u589e\u4e86\u4ec0\u4e48"},
        )

        self.assertEqual(response["intent"], "literature_learning_summary")
        self.assertEqual(response["artifact"]["artifact_type"], "learning_summary")
        candidates = ros.list_pending_memory_candidates(self.agent_root, self.project["id"], limit=5)
        self.assertTrue(any(item["artifact_id"] == response["artifact"]["artifact_id"] for item in candidates))

    def test_paper_recommendation_chat_generates_artifact(self) -> None:
        ros.import_reference(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "title": "Priority macrophage NF-kB paper",
                "abstract": "Macrophage NF-kB signaling paper for priority reading and method selection.",
                "year": "2025",
                "doi": "10.0000/priority-paper",
                "source_provider": "manual_fixture",
            },
        )
        ros.build_project_research_kb(self.agent_root, {"project_id": self.project["id"], "trigger_watcher_after_ingest": False})

        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "what papers should I read first for macrophage NF-kB"},
        )

        self.assertEqual(response["intent"], "paper_recommendation")
        self.assertEqual(response["artifact"]["artifact_type"], "paper_recommendation")
        artifacts = ros.get_recent_artifacts(self.agent_root, self.project["id"], limit=5)
        self.assertTrue(any(item["artifact_id"] == response["artifact"]["artifact_id"] for item in artifacts))

    def test_save_previous_phrase_commits_recent_artifact_from_chat_context(self) -> None:
        ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "\u77e5\u8bc6\u5e93\u65b0\u589e\u4e86\u4ec0\u4e48", "conversation_id": "save_recent_demo"},
        )

        response = ros.agent_chat(
            self.agent_root,
            {"project_id": self.project["id"], "message": "\u4fdd\u5b58\u521a\u624d\u7684", "conversation_id": "save_recent_demo"},
        )

        self.assertEqual(response["intent"], "memory_commit_request")
        self.assertTrue(response["memory_commit"]["committed"])
        self.assertEqual(response["memory_commit"]["memory_type"], "literature_learning")
        self.assertTrue(response["memory_commit"]["source_artifact_id"])

    def test_previous_item_and_use_this_phrases_commit_recent_candidate(self) -> None:
        generated = ros.generate_weekly_project_digest(self.agent_root, {"project_id": self.project["id"], "provider": "none"})

        resolved = ros.resolve_recent_artifact_reference(self.agent_root, self.project["id"], "\u4fdd\u5b58\u4e0a\u4e00\u6761")
        self.assertEqual(resolved["resolution"], "single_candidate")
        self.assertEqual(resolved["candidate"]["artifact_id"], generated["artifact"]["artifact_id"])

        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "\u5c31\u6309\u8fd9\u4e2a"})
        self.assertTrue(response["memory_commit"]["committed"])

    def test_api_model_question_does_not_create_pending_candidate(self) -> None:
        ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "\u4f60\u7528\u7684\u662f\u4ec0\u4e48\u6a21\u578b\uff0cAPI key \u5728\u54ea"})

        self.assertEqual(ros.list_pending_memory_candidates(self.agent_root, self.project["id"], limit=5), [])

    def test_core_skill_outputs_register_research_artifacts(self) -> None:
        cases = [
            ("protocol-extraction", "protocol"),
            ("sop-generation", "sop"),
            ("analyze-experiment-results", "data_analysis_result"),
            ("design-experiment-matrix", "experiment_plan"),
            ("peer-review-simulation", "manuscript_review_summary"),
            ("failure-log", "failure_summary"),
        ]
        for folder, artifact_type in cases:
            ros.run_imported_core_skill_adapter(
                self.agent_root,
                folder,
                {"source_path": f"core_skill:{folder}"},
                {
                    "project_id": self.project["id"],
                    "skill_run_id": f"run_{folder}",
                    "text": "Draft source text for artifact lifecycle testing.",
                    "data_summary": "Observed change requires review.",
                    "title": f"{folder} output",
                },
            )

            artifacts = ros.get_recent_artifacts(self.agent_root, self.project["id"], limit=20)
            self.assertTrue(any(item["artifact_type"] == artifact_type for item in artifacts), artifact_type)

    def test_commit_request_saves_previous_weekly_digest(self) -> None:
        task = ros.create_task(self.agent_root, {"project_id": self.project["id"], "task_type": "weekly_research_digest", "user_goal": "Generate weekly digest"})
        ros.run_research_workflow_task(self.agent_root, task["task_id"])

        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "纳入项目记忆"})

        self.assertEqual(response["intent"], "memory_commit_request")
        self.assertTrue(response["memory_commit"]["committed"])
        self.assertEqual(response["memory_commit"]["memory_type"], "weekly_digest")
        self.assertTrue(response["memory_commit"]["memory_id"])
        memories = ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)["entries"]
        self.assertTrue(any(item["id"] == response["memory_commit"]["memory_id"] for item in memories))

    def test_save_previous_summary_commits_recent_learning_summary(self) -> None:
        artifact = ros.create_artifact(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "artifact_type": "learning_summary",
                "title": "NF-kB learning summary",
                "content_markdown": "NF-kB may regulate inflammatory cytokines in macrophages.",
                "status": "pending_confirmation",
                "source_type": "agent_chat",
            },
        )
        candidate = ros.create_pending_memory_candidate(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "artifact_id": artifact["artifact_id"],
                "memory_type": "literature_learning",
                "normalized_content": artifact["content_markdown"],
                "evidence_level": "literature_derived",
            },
        )

        resolved = ros.resolve_memory_reference_from_context(
            self.agent_root,
            self.project["id"],
            "保存刚才的总结",
            {"last_artifact_id": artifact["artifact_id"]},
        )
        committed = ros.commit_pending_memory_candidate(self.agent_root, candidate["candidate_id"])

        self.assertEqual(resolved["resolution"], "single_candidate")
        self.assertEqual(resolved["candidate"]["candidate_id"], candidate["candidate_id"])
        self.assertTrue(committed["committed"])
        self.assertEqual(committed["memory_type"], "literature_learning")

    def test_no_candidate_asks_user_for_specific_content(self) -> None:
        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "保存刚才的总结"})

        self.assertEqual(response["intent"], "memory_commit_request")
        self.assertFalse(response["memory_commit"]["committed"])
        self.assertEqual(response["memory_commit"]["resolution"], "no_candidate")
        self.assertIn("具体内容", response["answer"])

    def test_multiple_candidates_ask_user_to_choose(self) -> None:
        for title in ["Weekly digest", "Learning summary"]:
            artifact_type = "weekly_digest" if "Weekly" in title else "learning_summary"
            artifact = ros.create_artifact(
                self.agent_root,
                {
                    "project_id": self.project["id"],
                    "artifact_type": artifact_type,
                    "title": title,
                    "content_markdown": f"{title} content",
                    "status": "pending_confirmation",
                },
            )
            ros.create_pending_memory_candidate(
                self.agent_root,
                {
                    "project_id": self.project["id"],
                    "artifact_id": artifact["artifact_id"],
                    "memory_type": artifact_type,
                    "normalized_content": f"{title} content",
                },
            )

        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "保存"})

        self.assertEqual(response["intent"], "memory_commit_request")
        self.assertFalse(response["memory_commit"]["committed"])
        self.assertEqual(response["memory_commit"]["resolution"], "multiple_candidates")
        self.assertIn("请选择", response["answer"])

    def test_ordinary_chat_does_not_create_pending_memory_candidate(self) -> None:
        ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "你好，今天聊一下科研方向"})

        self.assertEqual(ros.list_pending_memory_candidates(self.agent_root, self.project["id"], limit=5), [])


if __name__ == "__main__":
    unittest.main()
