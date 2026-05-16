import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class CoordinatorEmptyPlanningFallbackTests(unittest.TestCase):
    def test_empty_research_planning_placeholder_falls_back(self) -> None:
        placeholder = {
            "ok": True,
            "answer": "# Research Task Handoff: task_abc\n\n- Execution completed. task_type=research_planning",
            "task_spec": {"task_type": "research_planning"},
            "execution_result": {"status": "success", "summary": "Execution completed. task_type=research_planning", "output_files": []},
            "artifacts": [],
            "memory_pages": [],
            "pending_skill": {"name": "Generated Research Planning", "status": "pending_review"},
        }

        self.assertTrue(api.coordinator_result_should_fallback(placeholder, {"user_query": "你好"}))
        self.assertFalse(api._coordinator_has_substantive_output(placeholder))

    def test_normalized_coordinator_result_has_provenance(self) -> None:
        result = api.normalize_dual_agent_result(
            {
                "ok": True,
                "task_spec": {"task_type": "literature_harvest"},
                "execution_result": {"status": "success", "summary": "created task"},
                "artifacts": [{"artifact_id": "a1"}],
                "handoff": "Research Task Handoff",
            }
        )

        self.assertEqual(result["answer_source"], "coordinator_handoff")
        self.assertFalse(result["llm_called"])
        self.assertFalse(result["llm_output_used"])


if __name__ == "__main__":
    unittest.main()
