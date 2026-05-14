import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.memory.memory_item import create_memory_item
from backend.researchos.memory.retrieval.context_assembler import assemble_brain_context, assemble_execution_context, select_context_sources
from backend.researchos.memory.semantic.semantic_memory_store import create_semantic_memory_item


class ContextAssemblerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_context_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        create_semantic_memory_item(create_memory_item(project_id="p1", memory_layer="semantic", memory_type="claim", title="TLR4 claim", content="TLR4 regulates cytokines", source_ids=["src1"]))

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_brain_context_has_audit_and_selected_sources(self) -> None:
        context = assemble_brain_context("p1", "TLR4 cytokines", intent="mechanism_reasoning", max_tokens=2000)

        self.assertTrue(context["retrieval_audit"])
        self.assertTrue(context["selected_semantic_memories"])
        self.assertTrue(select_context_sources("p1", "TLR4"))

    def test_execution_context_is_minimal_and_redacted(self) -> None:
        brain_context = assemble_brain_context("p1", "TLR4 token=abc", max_tokens=2000)
        spec = TaskSpec(project_id="p1", user_query="Use sk-test123", validation_rules=["cite sources"], safety_constraints=["no secrets"])
        execution = assemble_execution_context(spec, brain_context, max_tokens=1000)

        self.assertEqual(set(execution).issubset({"task_brief", "project_short_summary", "selected_sources", "validation_rules", "known_constraints", "required_output_schema", "selected_skill_instructions", "context_audit"}), True)
        self.assertNotIn("full_research_brain_repo", str(execution))
        self.assertNotIn("sk-test123", str(execution))
        self.assertNotIn("token=abc", str(execution))


if __name__ == "__main__":
    unittest.main()
