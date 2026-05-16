from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MvpPromptAdapterTests(unittest.TestCase):
    def test_locates_and_loads_existing_mvp_prompt(self) -> None:
        from backend.researchos.prompts.mvp_prompt_adapter import locate_mvp_prompt_sources, load_mvp_system_prompt

        sources = locate_mvp_prompt_sources(ROOT)
        prompt = load_mvp_system_prompt(ROOT)

        self.assertTrue(sources["system_prompt_path"].endswith("researchos_agent_system_prompt.md"))
        self.assertTrue(Path(sources["system_prompt_path"]).exists())
        self.assertGreater(len(prompt), 100)

    def test_backend_prompt_extensions_are_not_runtime_prompt_rules(self) -> None:
        from backend.researchos.prompts.mvp_prompt_adapter import (
            build_brain_agent_prompt_extension,
            build_execution_agent_prompt_extension,
            load_mvp_prompt_router_config,
        )

        router = load_mvp_prompt_router_config(ROOT)
        brain_extension = build_brain_agent_prompt_extension()
        execution_extension = build_execution_agent_prompt_extension()

        self.assertIn("backend_llm_guardrails", router["supported_policies"])
        self.assertEqual(brain_extension, "")
        self.assertEqual(execution_extension, "")

    def test_backend_agent_llm_calls_use_only_mvp_system_prompt(self) -> None:
        from backend.researchos.agents.brain_agent import ResearchBrainAgent
        from backend.researchos.agents.execution_agent import ResearchExecutionAgent
        from unittest.mock import patch

        captured: list[tuple[str, list[dict]]] = []

        def fake_call_llm(agent_name: str, messages: list[dict], **kwargs):
            captured.append((agent_name, messages))
            return {"ok": True, "message": {"role": "assistant", "content": "ok"}}

        with patch("backend.researchos.prompts.mvp_prompt_adapter.load_mvp_system_prompt", return_value="MVP_SYSTEM_PROMPT_ONLY"), patch(
            "backend.researchos.llm.gateway.call_llm",
            side_effect=fake_call_llm,
        ):
            ResearchBrainAgent().call_llm([{"role": "user", "content": "hi"}])
            ResearchExecutionAgent().call_llm([{"role": "user", "content": "run"}])

        self.assertEqual([item[0] for item in captured], ["brain_agent", "execution_agent"])
        for _, messages in captured:
            self.assertEqual(messages[0], {"role": "system", "content": "MVP_SYSTEM_PROMPT_ONLY"})
            self.assertNotIn("MVP extension", messages[0]["content"])
            self.assertNotIn("Brain Agent", messages[0]["content"])
            self.assertNotIn("Execution Agent", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
