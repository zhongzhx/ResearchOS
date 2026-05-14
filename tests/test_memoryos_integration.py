import os
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.researchos.agents.agent_protocol import ExecutionResult, TaskSpec
from backend.researchos.agents.coordinator import AgentCoordinator
from backend.researchos.brain.evidence_promotion import promote_skill_outputs_to_brain
from backend.researchos.brain.memory_writer import write_memory_from_promotion_decision
from backend.researchos.memory.compression.cognitive_state import load_cognitive_state
from backend.researchos.memory.episodic.episodic_memory_store import list_recent_episodes
from backend.researchos.memory.events.event_store import list_events
from backend.researchos.memory.semantic.semantic_memory_store import list_semantic_memories
from backend.researchos.skills.pipeline_registry import get_pipeline_for_intent


class MemoryOSIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="memoryos_integration_"))
        os.environ["MEMORYOS_ROOT"] = str(self.tmp / "memoryos")
        os.environ["RESEARCH_BRAIN_ROOT"] = str(self.tmp / "research_brain")
        os.environ["RESEARCHOS_TASKS_ROOT"] = str(self.tmp / "tasks")
        os.environ["RESEARCHOS_AGENT_ROOT"] = str(self.tmp / "agent_data")

    def tearDown(self) -> None:
        os.environ.pop("MEMORYOS_ROOT", None)
        os.environ.pop("RESEARCH_BRAIN_ROOT", None)
        os.environ.pop("RESEARCHOS_TASKS_ROOT", None)
        os.environ.pop("RESEARCHOS_AGENT_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_evidence_promotion_commit_generates_memoryos_event_and_item(self) -> None:
        spec = TaskSpec(project_id="p1", user_query="download papers", intent="literature_harvest", task_type="literature_harvest")
        result = ExecutionResult(task_id=spec.task_id, skillrun_id="sr1", status="success", summary="papers indexed", sources=[{"source_id": "pmid1"}], structured_outputs={"paper_table": [{"title": "Paper A"}]})
        promotion = promote_skill_outputs_to_brain(result, spec, get_pipeline_for_intent("literature_harvest"))

        committed = write_memory_from_promotion_decision(promotion)

        self.assertTrue(committed["memoryos"]["memory_items"])
        self.assertTrue(list_events(project_id="p1", event_type="evidence_promoted"))
        self.assertTrue(list_semantic_memories("p1"))

    def test_task_completion_creates_episode_and_refreshes_cognitive_state(self) -> None:
        coordinator = AgentCoordinator()
        response = coordinator.run_full_cycle("summarize project status", project_id="p1", process_after_execution=False)

        self.assertIn(response["execution_result"]["status"], {"success", "partial_success", "failed"})
        self.assertTrue(list_recent_episodes("p1"))
        self.assertEqual(load_cognitive_state("p1")["project_id"], "p1")
        self.assertNotIn("full_research_brain_repo", str(response.get("task_spec", {}).get("context_package", {})))

    def test_memory_api_helpers_return_redacted_json(self) -> None:
        from backend.researchos.api.dual_agent_routes import memory_search, memory_working

        working = memory_working({"project_id": "p1", "conversation_id": "c1"})
        search = memory_search({"project_id": "p1", "query": "token=abc123"})

        self.assertTrue(working["ok"])
        self.assertTrue(search["ok"])
        self.assertNotIn("abc123", str(search))


if __name__ == "__main__":
    unittest.main()
