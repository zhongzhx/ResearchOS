import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "backend" / "research_agent_runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_agent_api as api  # noqa: E402


class SettingsLlmApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="aura_llm_settings_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {
            key: os.environ.get(key)
            for key in [
                "LLM_PROVIDER",
                "LLM_API_KEY",
                "LLM_BASE_URL",
                "LLM_MODEL",
                "MINIMAX_API_KEY",
                "OPENAI_API_KEY",
                "BRAIN_AGENT_API_KEY",
                "EXECUTION_AGENT_API_KEY",
            ]
        }
        for key in self.previous_env:
            os.environ[key] = ""
        api.CONFIG = api.RuntimeConfig(self.agent_root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        if self.previous_config is not None:
            api.CONFIG = self.previous_config
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base_url + path, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_llm_settings_save_masks_keys_and_does_not_store_plaintext(self) -> None:
        secret = "sk-test-product-flow-secret"
        saved = self._post_json(
            "/api/settings/llm",
            {
                "mode": "single_key",
                "brain_provider": "openai",
                "brain_model": "gpt-test",
                "brain_base_url": "https://example.test/v1",
                "brain_api_key": secret,
            },
        )
        loaded = self._get_json("/api/settings/llm")
        config_path = self.agent_root / "config" / "llm_settings.json"

        self.assertTrue(saved["ok"])
        self.assertEqual(saved["settings"]["brain_api_key_masked"], "sk-...cret")
        self.assertNotIn(secret, json.dumps(saved))
        self.assertNotIn(secret, json.dumps(loaded))
        self.assertTrue(config_path.exists())
        self.assertNotIn(secret, config_path.read_text(encoding="utf-8"))

    def test_llm_test_reports_not_configured_without_key(self) -> None:
        result = self._post_json("/api/settings/llm/test", {"mode": "single_key"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "not_configured")


if __name__ == "__main__":
    unittest.main()
