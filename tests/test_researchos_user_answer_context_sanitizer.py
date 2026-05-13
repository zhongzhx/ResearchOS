import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "researchos_skill_library" / "01_core_runtime_memory" / "research-agent-runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_context_compiler as compiler  # noqa: E402
import research_os_mvp as ros  # noqa: E402


class UserAnswerContextSanitizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_answer_context_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Sanitizer Project", "research_area": "immune regulation"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize_context_for_user_answer_filters_internal_ids_and_raw_progress_json(self) -> None:
        raw = {
            "active_project_id": "proj_abc123456789",
            "active_project_display_name": "Sanitizer Project",
            "compiled_context": (
                "Project summary\n"
                "- [project:proj_abc123456789] project_id=proj_abc123456789\n"
                "Current task status\n"
                "- [task_status:task_abc123456789] progress={\"downloaded\": 2, \"indexed\": 1}"
            ),
            "context_items": [
                {
                    "source_type": "task_status",
                    "source_id": "task_abc123456789",
                    "title": "Harvest",
                    "content": "status=running; progress={\"downloaded\": 2, \"indexed\": 1}; candidate_id=cand_abc123",
                    "metadata": {"memory_id": "mem_abc123"},
                }
            ],
            "sources": [
                {
                    "reference_id": "ref_abc123",
                    "chunk_id": "chunk_abc123",
                    "title": "Source title",
                    "citation_id": 1,
                    "excerpt": "Short excerpt.",
                }
            ],
            "task_status": [
                {
                    "task_id": "task_abc123456789",
                    "task_name": "Harvest",
                    "status": "running",
                    "progress": {"total": 5, "downloaded": 2, "indexed": 1, "failed": 0},
                    "updated_at": "2026-05-10T10:00:00",
                    "error": "Traceback (most recent call last): boom",
                    "next_action": "Continue parsing",
                }
            ],
            "memory_used": [{"id": "mem_abc123", "title": "Memory"}],
            "context_hash": "hash_abc123",
        }

        sanitized = compiler.sanitize_context_for_user_answer(raw)
        rendered = str(sanitized)

        self.assertNotIn("proj_abc123456789", rendered)
        self.assertNotIn("task_abc123456789", rendered)
        self.assertNotIn("mem_abc123", rendered)
        self.assertNotIn("cand_abc123", rendered)
        self.assertNotIn("chunk_abc123", rendered)
        self.assertNotIn('{"downloaded": 2', rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertIn("user_visible_task_status", sanitized)
        self.assertEqual(
            set(sanitized["user_visible_task_status"][0]),
            {"task name", "human readable status", "progress summary", "last update", "error summary", "next action"},
        )

    def test_compiled_context_for_answer_generation_hides_project_task_and_memory_ids(self) -> None:
        run = ros.start_service_skill_run(
            self.agent_root,
            "unit_status_skill",
            "UnitStatusSkill",
            self.project["id"],
            {"project_id": self.project["id"]},
        )
        ros.finish_service_skill_run(
            self.agent_root,
            run["id"],
            {"project_id": self.project["id"], "result": "ok"},
            [{"type": "report", "id": "status-report"}],
            ["status run completed"],
        )

        context = compiler.compile_research_context(
            self.agent_root,
            {"project_id": self.project["id"], "user_message": "what is the current progress", "intent": "task_status_query"},
        )
        compiled = context["compiled_context"]

        self.assertNotIn(self.project["id"], compiled)
        self.assertNotIn(run["id"], compiled)
        self.assertNotIn("task_id", compiled)
        self.assertNotIn("memory_id", compiled)
        self.assertNotIn("candidate_id", compiled)
        self.assertNotIn('progress={"', compiled)
        self.assertTrue(context["user_visible_task_status"])

    def test_pending_memory_candidate_id_does_not_appear_in_memory_choice_answer(self) -> None:
        candidate_ids: list[str] = []
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
            candidate = ros.create_pending_memory_candidate(
                self.agent_root,
                {
                    "project_id": self.project["id"],
                    "artifact_id": artifact["artifact_id"],
                    "memory_type": artifact_type,
                    "normalized_content": f"{title} content",
                },
            )
            candidate_ids.append(candidate["candidate_id"])

        response = ros.agent_chat(self.agent_root, {"project_id": self.project["id"], "message": "save"})

        self.assertEqual(response["intent"], "memory_commit_request")
        self.assertNotIn("candidate_id", response["answer"])
        for candidate_id in candidate_ids:
            self.assertNotIn(candidate_id, response["answer"])


if __name__ == "__main__":
    unittest.main()
