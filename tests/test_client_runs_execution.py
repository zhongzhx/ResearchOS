from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNS_JS = ROOT / "web_client" / "views" / "runs.js"


class ClientRunsExecutionTests(unittest.TestCase):
    def test_runs_view_shows_skill_runs_execution_memory_runtime_and_scheduler(self) -> None:
        source = RUNS_JS.read_text(encoding="utf-8")

        for name in ["getSkillRuns", "getExecutionMemory", "getRuntimeStatus", "getSchedulerStatus"]:
            self.assertIn(name, source)

        for field in ["skill_id", "started_at", "finished_at", "project_id", "artifacts", "validation_report", "unresolved_items"]:
            self.assertIn(field, source)

        for field in ["summary", "confidence", "safe_to_promote", "source skillrun_id", "promoted"]:
            self.assertIn(field, source)

    def test_promote_only_for_safe_execution_memory_and_requires_confirm(self) -> None:
        source = RUNS_JS.read_text(encoding="utf-8")

        self.assertIn("promoteExecutionMemory", source)
        self.assertIn("safe_to_promote", source)
        self.assertIn("confirm(", source)
        self.assertIn("data-promote-memory", source)
        self.assertNotIn("runLegacySkill", source)
        self.assertNotIn("runCoordinator", source)


if __name__ == "__main__":
    unittest.main()
