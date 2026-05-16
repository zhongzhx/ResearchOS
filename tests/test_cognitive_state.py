import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.memory.compression.cognitive_state import (
    compile_cognitive_state_from_memories,
    load_cognitive_state,
    refresh_cognitive_state_after_task,
    summarize_cognitive_state_for_context,
    update_cognitive_state,
)
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item


class CognitiveStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_cognitive_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_update_compile_refresh_and_summarize_state(self) -> None:
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="goal", title="Goal", content="Study TLR4", source_ids=["src1"]))
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="open_question", title="Question", content="What blocks NF-kB?", confidence="low"))

        update_cognitive_state("p1", {"current_goal": "Initial"}, source_ids=["manual"])
        compiled = compile_cognitive_state_from_memories("p1")
        refreshed = refresh_cognitive_state_after_task("p1", "t1")
        summary = summarize_cognitive_state_for_context("p1", max_items=5)

        self.assertIn("Study TLR4", str(compiled["current_goal"]))
        self.assertIn("t1", refreshed["last_updated_from"])
        self.assertTrue(summary["current_goal"])
        self.assertEqual(load_cognitive_state("p1")["project_id"], "p1")


if __name__ == "__main__":
    unittest.main()
