import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.researchos.llm.gateway import get_llm_config_for_agent, call_llm, check_llm_connection
from backend.researchos.settings.secret_store import delete_llm_settings, save_llm_settings


class LlmGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_llm_gateway_"))
        self.previous = {
            "RESEARCHOS_AGENT_DATA_DIR": os.environ.get("RESEARCHOS_AGENT_DATA_DIR"),
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER"),
            "LLM_API_KEY": os.environ.get("LLM_API_KEY"),
            "LLM_BASE_URL": os.environ.get("LLM_BASE_URL"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
            "MINIMAX_API_KEY": os.environ.get("MINIMAX_API_KEY"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "BRAIN_AGENT_API_KEY": os.environ.get("BRAIN_AGENT_API_KEY"),
            "EXECUTION_AGENT_API_KEY": os.environ.get("EXECUTION_AGENT_API_KEY"),
        }
        os.environ["RESEARCHOS_AGENT_DATA_DIR"] = str(self.tmp / "agent_data")
        for key in ["LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MINIMAX_API_KEY", "OPENAI_API_KEY", "BRAIN_AGENT_API_KEY", "EXECUTION_AGENT_API_KEY"]:
            os.environ[key] = ""

    def tearDown(self) -> None:
        delete_llm_settings()
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_separate_keys_resolve_by_agent_without_cross_reading(self) -> None:
        save_llm_settings(
            {
                "mode": "separate_keys",
                "brain_agent": {"provider": "openai", "model": "brain", "api_key": "sk-brain-only"},
                "execution_agent": {"provider": "minimax", "model": "exec", "api_key": "sk-exec-only"},
            }
        )

        brain = get_llm_config_for_agent("brain_agent")
        execution = get_llm_config_for_agent("execution_agent")

        self.assertEqual(brain["api_key"], "sk-brain-only")
        self.assertEqual(execution["api_key"], "sk-exec-only")
        self.assertNotEqual(brain["api_key"], execution["api_key"])

    def test_missing_configuration_returns_not_configured_without_secret_leak(self) -> None:
        result = call_llm("brain_agent", [{"role": "user", "content": "hello"}])

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_configured")
        self.assertNotIn("api_key", result)

    def test_mock_provider_returns_structured_response(self) -> None:
        save_llm_settings({"mode": "single_key", "provider": "mock", "model": "mock-model", "api_key": ""})

        result = check_llm_connection("execution_agent")

        self.assertTrue(result["ok"])
        self.assertEqual(result["agent_name"], "execution_agent")
        self.assertEqual(result["provider"], "mock")

    def test_live_provider_delegates_to_mvp_llm_adapter(self) -> None:
        save_llm_settings(
            {
                "mode": "single_key",
                "provider": "openai-compatible",
                "model": "deepseek-v4-pro",
                "base_url": "http://127.0.0.1:9/v1",
                "api_key": "sk-live-secret",
            }
        )
        adapter_instances = []

        class FakeMvpAdapter:
            def __init__(self, *args, **kwargs) -> None:
                self.provider = ""
                self.model = ""
                self.base_url = ""
                self.api_key = ""
                self.calls = []
                adapter_instances.append(self)

            def chat_text(self, prompt: str, system_prompt: str = "", temperature: float = 0.1) -> str:
                self.calls.append({"prompt": prompt, "system_prompt": system_prompt, "temperature": temperature})
                return "来自 MVP LLMAdapter 的回答"

        fake_mvp = SimpleNamespace(LLMAdapter=FakeMvpAdapter)

        with patch("backend.researchos.execution.runtime_adapter.import_research_os_mvp", return_value=fake_mvp), patch(
            "backend.researchos.llm.gateway.urllib.request.urlopen",
            side_effect=AssertionError("new backend gateway must not call provider HTTP directly"),
        ):
            result = call_llm(
                "brain_agent",
                [{"role": "system", "content": "MVP system prompt"}, {"role": "user", "content": "你好"}],
                temperature=0.2,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"]["content"], "来自 MVP LLMAdapter 的回答")
        self.assertEqual(adapter_instances[0].provider, "openai-compatible")
        self.assertEqual(adapter_instances[0].model, "deepseek-v4-pro")
        self.assertEqual(adapter_instances[0].base_url, "http://127.0.0.1:9/v1")
        self.assertEqual(adapter_instances[0].api_key, "sk-live-secret")
        self.assertEqual(adapter_instances[0].calls[0]["system_prompt"], "MVP system prompt")
        self.assertEqual(adapter_instances[0].calls[0]["prompt"], "你好")
        self.assertEqual(adapter_instances[0].calls[0]["temperature"], 0.2)
        self.assertNotIn("api_key", result)


if __name__ == "__main__":
    unittest.main()
