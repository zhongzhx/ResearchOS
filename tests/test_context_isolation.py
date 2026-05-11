import unittest

from backend.researchos.agents.agent_protocol import (
    TaskSpec,
    build_execution_context_package,
    redact_forbidden_context,
    sanitize_context_for_execution,
    validate_context_isolation,
)


class ContextIsolationTests(unittest.TestCase):
    def test_execution_context_rejects_full_agent_memory(self) -> None:
        spec = TaskSpec(
            task_id="task-2",
            user_query="analyze",
            intent="research_advice",
            task_type="result_analysis",
            context_package={"full_agent_memory": {"private": "do not send"}},
        )

        report = validate_context_isolation(spec)

        self.assertFalse(report["valid"])
        self.assertIn("full_agent_memory", report["forbidden_found"])

    def test_execution_context_rejects_full_research_brain_repo(self) -> None:
        spec = TaskSpec(
            task_id="task-3",
            user_query="run tool",
            intent="start_skill_request",
            task_type="pdf_ingest",
            context_package={"full_research_brain_repo": {"plans": []}},
        )

        report = validate_context_isolation(spec)

        self.assertFalse(report["valid"])
        self.assertIn("full_research_brain_repo", report["forbidden_found"])

    def test_compiled_context_is_not_passed_through_raw(self) -> None:
        compiled_context = {
            "compiled_context": "long brain-only prompt",
            "project_summary": "short project summary",
            "sources": [{"source_id": "ref-1", "excerpt": "evidence"}],
            "memory_used": [{"id": "mem-1"}],
            "full_agent_memory": [{"id": "secret"}],
        }
        spec = TaskSpec(
            task_id="task-4",
            user_query="summarize",
            intent="kb_query",
            task_type="kb_summary",
            validation_rules=["cite sources"],
        )

        package = sanitize_context_for_execution(compiled_context, spec)

        self.assertNotIn("compiled_context", package)
        self.assertNotIn("full_agent_memory", package)
        self.assertIn("task_brief", package)
        self.assertIn("relevant_sources", package)

    def test_forbidden_context_types_are_redacted(self) -> None:
        context = {
            "task_brief": "brief",
            "full_project_history": ["secret"],
            "relevant_sources": [{"source_id": "ref-1"}],
        }

        redacted = redact_forbidden_context(context, ["full_project_history"])

        self.assertNotIn("full_project_history", redacted["context_package"])
        self.assertIn("full_project_history", redacted["redacted"])

    def test_build_execution_context_package_limits_to_allowed_fields(self) -> None:
        compiled_context = {
            "project_summary": "short",
            "sources": [{"source_id": "ref-1"}],
            "context_items": [{"source_type": "kb_entry", "text": "chunk"}],
            "claims": [{"id": "claim-1"}],
        }
        spec = TaskSpec(
            task_id="task-5",
            user_query="summarize",
            intent="kb_query",
            task_type="kb_summary",
            expected_outputs=["summary"],
        )

        package = build_execution_context_package(spec, compiled_context)

        self.assertEqual(set(package).issubset({
            "task_brief",
            "project_short_summary",
            "relevant_sources",
            "relevant_chunks",
            "required_output_schema",
            "validation_rules",
            "known_constraints",
            "active_skill_instructions",
        }), True)


if __name__ == "__main__":
    unittest.main()
