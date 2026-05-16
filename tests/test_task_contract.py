import unittest

from backend.researchos.agents.agent_protocol import TaskSpec
from backend.researchos.tasks.task_contract import build_contract_from_task_spec


class TaskContractTests(unittest.TestCase):
    def test_contract_is_derived_from_task_spec(self) -> None:
        spec = TaskSpec(
            project_id="project_1",
            user_query="download literature",
            intent="literature_harvest",
            task_type="literature_harvest",
            required_skills=["core_keyword_research_harvest"],
            allowed_tools=["literature_search"],
            forbidden_tools=["read_secrets"],
            input_files=["input.csv"],
            expected_outputs=["output_files"],
            validation_rules=["cite sources"],
            source_requirements={"required": True},
            safety_constraints=["requires_user_authorization"],
            input_data={"authorized": False},
            context_package={"task_brief": "download literature"},
        )

        contract = build_contract_from_task_spec(spec)

        self.assertEqual(contract["required_skills"], ["core_keyword_research_harvest"])
        self.assertEqual(contract["allowed_tools"], ["literature_search"])
        self.assertEqual(contract["forbidden_tools"], ["read_secrets"])
        self.assertEqual(contract["input_files"], ["input.csv"])
        self.assertEqual(contract["expected_outputs"], ["output_files"])
        self.assertTrue(contract["authorization_requirements"]["blocked_if_missing"])
        self.assertFalse(contract["memory_commit_policy"]["direct_execution_memory_write_allowed"])


if __name__ == "__main__":
    unittest.main()
