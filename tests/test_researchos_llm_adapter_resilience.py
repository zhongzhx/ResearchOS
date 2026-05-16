import http.client
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_os_mvp as ros  # noqa: E402


class LLMAdapterResilienceTests(unittest.TestCase):
    def test_remote_disconnect_returns_controlled_fallback_answer(self) -> None:
        adapter = ros.LLMAdapter()
        adapter.provider = "openai-compatible"
        adapter.api_key = "unit-test-key"
        adapter.base_url = "https://example.invalid/v1"
        adapter.model = "unit-test-model"

        with patch("urllib.request.urlopen", side_effect=http.client.RemoteDisconnected("closed")):
            answer = adapter.chat_text("hello", system_prompt="system")

        self.assertIn("后端模型连接暂时中断", answer)
        self.assertIn("closed", answer)


if __name__ == "__main__":
    unittest.main()
