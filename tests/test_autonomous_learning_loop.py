import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.learning.autonomous_learning_loop import (
    create_pending_learning_recommendation,
    propose_learning_tasks,
    run_autonomous_learning_check,
)
from backend.researchos.memory.learning.project_gap_scanner import (
    find_claims_without_validation,
    find_failed_tasks_without_recovery,
    find_open_questions_without_tasks,
    scan_project_gaps,
)
from backend.researchos.memory.learning.skill_usage_evaluator import evaluate_skill_usage, find_repeated_failures, find_reusable_success_patterns
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item


class AutonomousLearningLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_learning_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="open_question", title="Q", content="What validates this?"))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="Weak", content="Weak claim", confidence="medium"))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="episodic", memory_type="failure", title="Failure", content="Tool failed", confidence="low"))

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_autonomous_learning_is_dry_run_recommendations_only(self) -> None:
        gaps = scan_project_gaps("p1")
        recommendation = create_pending_learning_recommendation("p1", {"title": "Validate claim", "risk": "medium"})
        check = run_autonomous_learning_check("p1")

        self.assertTrue(find_open_questions_without_tasks("p1"))
        self.assertTrue(find_claims_without_validation("p1"))
        self.assertTrue(find_failed_tasks_without_recovery("p1"))
        self.assertTrue(propose_learning_tasks("p1"))
        self.assertEqual(recommendation["status"], "pending")
        self.assertTrue(check["dry_run"])
        self.assertFalse(check["executed"])
        self.assertIn("open_questions_without_tasks", gaps)
        self.assertIn("success_patterns", evaluate_skill_usage("p1"))
        self.assertIsInstance(find_reusable_success_patterns("p1"), list)
        self.assertIsInstance(find_repeated_failures("p1"), list)


if __name__ == "__main__":
    unittest.main()
