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
from backend.researchos.agents.agent_protocol import TaskSpec  # noqa: E402
from backend.researchos.agents.execution_agent import ResearchExecutionAgent  # noqa: E402


class ExecutionAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="aura_execution_agent_"))
        self.agent_root = self.temp_dir / "agent_data"
        self.project = ros.create_project(self.agent_root, {"title": "Execution Agent Test", "research_area": "test"})

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_context_isolation_failure_returns_failed_result(self) -> None:
        agent = ResearchExecutionAgent(agent_root=self.agent_root)
        spec = TaskSpec(
            project_id=self.project["id"],
            user_query="run",
            intent="start_skill_request",
            task_type="generic_skill_task",
            context_package={"full_agent_memory": ["secret"]},
        )

        result = agent.execute_task(spec)

        self.assertEqual(result.status, "failed")
        self.assertTrue(result.errors)

    def test_active_skill_execution_writes_skillrun_and_execution_memory(self) -> None:
        ros.upsert_skill(
            self.agent_root,
            {
                "skill_id": "test_active_skill",
                "skill_name": "TestActiveSkill",
                "handler": "promoted_execution_memory",
                "status": "active",
            },
        )
        agent = ResearchExecutionAgent(agent_root=self.agent_root)
        spec = TaskSpec(
            project_id=self.project["id"],
            user_query="run active skill",
            intent="start_skill_request",
            task_type="generic_skill_task",
            required_skills=["TestActiveSkill"],
            allowed_tools=[],
            expected_outputs=["structured_outputs"],
            context_package={"task_brief": "run active skill"},
        )

        result = agent.execute_task(spec)

        self.assertEqual(result.status, "success")
        self.assertTrue(result.skillrun_id)
        self.assertTrue(ros.list_skill_runs(self.agent_root, project_id=self.project["id"]))
        self.assertTrue(ros.list_execution_memory(self.agent_root, project_id=self.project["id"]))

    def test_execution_agent_does_not_write_long_term_agent_memory(self) -> None:
        agent = ResearchExecutionAgent(agent_root=self.agent_root)
        spec = TaskSpec(
            project_id=self.project["id"],
            user_query="generic run",
            intent="start_skill_request",
            task_type="generic_skill_task",
            allowed_tools=[],
            context_package={"task_brief": "generic run"},
        )

        agent.execute_task(spec)

        memory = ros.list_agent_memory(self.agent_root, scope="project", project_id=self.project["id"], include_disabled=True)
        self.assertEqual(memory["entries"], [])

    def test_output_files_are_registered_as_artifacts(self) -> None:
        agent = ResearchExecutionAgent(agent_root=self.agent_root)
        spec = TaskSpec(
            project_id=self.project["id"],
            user_query="write output",
            intent="start_skill_request",
            task_type="report_generation",
            allowed_tools=["file_writer"],
            expected_outputs=["output_files"],
            input_data={"filename": "summary.txt", "content": "done"},
            context_package={"task_brief": "write output"},
        )

        result = agent.execute_task(spec)

        self.assertEqual(result.status, "success")
        self.assertTrue(result.output_files)
        artifacts = ros.workspace_state(self.agent_root, self.project["id"]).get("artifacts", [])
        self.assertTrue(any(item.get("path") == result.output_files[0] for item in artifacts))


if __name__ == "__main__":
    unittest.main()
