from pathlib import Path
import os
import tempfile
import unittest


class TaskLifecycleMvpBridgeTests(unittest.TestCase):
    def test_product_flow_lifecycle_bridge_persists_required_files(self) -> None:
        from backend.researchos.integration.mvp_task_bridge import persist_product_feature_lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get("RESEARCHOS_TASKS_ROOT")
            os.environ["RESEARCHOS_TASKS_ROOT"] = str(Path(tmp) / "research_tasks")
            try:
                result = persist_product_feature_lifecycle(
                    "experiment_design_workflow",
                    {"project_id": "project_a", "query": "design experiment"},
                    {"status": "partial", "summary": "demo", "artifacts": [], "validation_report": {"safe_to_return": True}, "memory_update": {"status": "skipped"}},
                )
            finally:
                if previous is None:
                    os.environ.pop("RESEARCHOS_TASKS_ROOT", None)
                else:
                    os.environ["RESEARCHOS_TASKS_ROOT"] = previous

            task_dir = Path(result["research_task_dir"])
            expected = {
                "goal.json",
                "plan.md",
                "contract.json",
                "execution_result.json",
                "artifacts.json",
                "validation_report.json",
                "handoff.md",
                "memory_commit.json",
                "events.jsonl",
            }
            self.assertTrue(task_dir.exists())
            self.assertTrue(expected.issubset({path.name for path in task_dir.iterdir()}))


if __name__ == "__main__":
    unittest.main()
