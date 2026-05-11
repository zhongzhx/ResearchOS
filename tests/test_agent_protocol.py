import unittest

from backend.researchos.agents.agent_protocol import BrainDecision, ContextEnvelope, ExecutionResult, TaskSpec


class AgentProtocolTests(unittest.TestCase):
    def test_task_spec_can_be_created_with_execution_minimal_scope(self) -> None:
        spec = TaskSpec(
            task_id="task-1",
            project_id="project-1",
            user_query="summarize the papers",
            intent="kb_query",
            task_type="kb_summary",
            required_skills=["build-user-research-kb"],
            allowed_tools=["rag_query"],
            expected_outputs=["summary"],
            validation_rules=["cite sources"],
        )

        self.assertEqual(spec.context_scope, "execution_minimal")
        self.assertEqual(spec.priority, "normal")
        self.assertEqual(spec.created_by, "brain_agent")
        self.assertIn("build-user-research-kb", spec.required_skills)
        self.assertIn("summary", spec.expected_outputs)
        self.assertIn("cite sources", spec.validation_rules)

    def test_execution_result_can_be_created(self) -> None:
        result = ExecutionResult(
            task_id="task-1",
            skillrun_id="skillrun-1",
            status="success",
            summary="Completed mock execution.",
            output_files=["out.json"],
            structured_outputs={"items": 1},
            sources=[{"source_id": "ref-1"}],
            logs=["started", "finished"],
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.structured_outputs["items"], 1)

    def test_brain_decision_and_context_envelope_can_be_created(self) -> None:
        envelope = ContextEnvelope(
            agent_name="brain_agent",
            scope="brain_full",
            project_id="project-1",
            user_query="what next?",
            allowed_context_types=["project_summary"],
            context_package={"project_summary": "A short summary"},
        )
        decision = BrainDecision(
            decision_type="accept",
            reason="Result is sufficient.",
            user_facing_summary="已完成。",
        )

        self.assertEqual(envelope.scope, "brain_full")
        self.assertEqual(decision.decision_type, "accept")


if __name__ == "__main__":
    unittest.main()
