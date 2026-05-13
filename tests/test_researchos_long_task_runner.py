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


class ResearchOSLongTaskRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_long_task_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(
            self.agent_root,
            {"title": "Long Task Project", "research_area": "immune regulation"},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_literature_harvest_task_can_advance_through_stages(self) -> None:
        task = ros.create_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "task_type": "literature_harvest",
                "user_goal": "Collect NF-kB macrophage papers",
                "input_json": {"keywords": ["NF-kB", "macrophage"], "mock": True},
            },
        )

        started = ros.start_task(self.agent_root, task["task_id"])
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["current_stage"], "initializing")

        searching = ros.record_stage_transition(self.agent_root, task["task_id"], "searching", counters={"found": 3})
        self.assertEqual(searching["current_stage"], "searching")
        self.assertEqual(searching["counters"]["found"], 3)

        parsing = ros.record_stage_transition(self.agent_root, task["task_id"], "parsing", counters={"downloaded": 2, "parsed": 1})
        self.assertEqual(parsing["current_stage"], "parsing")
        self.assertEqual(parsing["counters"]["downloaded"], 2)
        self.assertEqual(parsing["counters"]["parsed"], 1)

    def test_error_recording_updates_errors_and_failed_status(self) -> None:
        task = ros.create_task(
            self.agent_root,
            {"project_id": self.project["id"], "task_type": "kb_ingestion", "user_goal": "Ingest PDFs"},
        )

        failed = ros.record_error(self.agent_root, task["task_id"], "PDF parser failed", stage="parsing", fail_task=True)

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["current_stage"], "failed")
        self.assertTrue(any(error["message"] == "PDF parser failed" for error in failed["errors"]))

    def test_completed_literature_workflow_generates_artifact(self) -> None:
        task = ros.create_task(
            self.agent_root,
            {
                "project_id": self.project["id"],
                "task_type": "literature_harvest",
                "user_goal": "Mock harvest",
                "input_json": {"keywords": ["NF-kB"], "mock": True},
            },
        )

        completed = ros.run_research_workflow_task(self.agent_root, task["task_id"])

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["current_stage"], "completed")
        self.assertTrue(completed["artifacts"])
        self.assertTrue(any(artifact["type"] in {"literature_harvest_summary", "learning_summary"} for artifact in completed["artifacts"]))

    def test_weekly_digest_task_generates_pending_memory_candidate(self) -> None:
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

        self.assertEqual(completed["status"], "completed")
        self.assertTrue(any(artifact["type"] in {"weekly_digest_report", "weekly_digest"} for artifact in completed["artifacts"]))
        candidates = [
            action
            for action in completed["next_actions"]
            if action.get("intent") == "memory_commit_request" and action.get("status") == "pending_user_confirmation"
        ]
        self.assertTrue(candidates)

    def test_get_task_status_and_last_active_task_are_truthful(self) -> None:
        first = ros.create_task(self.agent_root, {"project_id": self.project["id"], "task_type": "paper_recommendation", "user_goal": "Recommend papers"})
        second = ros.create_task(self.agent_root, {"project_id": self.project["id"], "task_type": "data_analysis", "user_goal": "Analyze table"})
        ros.start_task(self.agent_root, first["task_id"])
        ros.start_task(self.agent_root, second["task_id"])

        status = ros.get_task_status(self.agent_root, second["task_id"])
        recent = ros.list_project_tasks(self.agent_root, self.project["id"], limit=5)
        last = ros.last_active_task(self.agent_root, self.project["id"])

        self.assertEqual(status["task_id"], second["task_id"])
        self.assertEqual(status["status"], "running")
        self.assertEqual(recent["last_active_task"]["task_id"], second["task_id"])
        self.assertEqual(last["task_id"], second["task_id"])

    def test_pause_resume_cancel_and_attach_artifact(self) -> None:
        task = ros.create_task(self.agent_root, {"project_id": self.project["id"], "task_type": "protocol_extraction", "user_goal": "Extract protocol"})

        paused = ros.pause_task(self.agent_root, task["task_id"], reason="waiting for PDF")
        resumed = ros.resume_task(self.agent_root, task["task_id"])
        artifact = ros.attach_artifact_to_task(
            self.agent_root,
            task["task_id"],
            {"type": "protocol_report", "title": "Protocol extraction notes", "metadata": {"source": "mock"}},
        )
        cancelled = ros.cancel_task(self.agent_root, task["task_id"], reason="user cancelled")

        self.assertEqual(paused["status"], "paused")
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(artifact["task_id"], task["task_id"])
        self.assertEqual(cancelled["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
