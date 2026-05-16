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


class SettingsLlmMaskingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="researchos_llm_masking_"))
        self.agent_root = self.tmp / "agent_data"
        self.previous_config = getattr(api, "CONFIG", None)
        self.previous_env = {key: os.environ.get(key) for key in ["LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "OPENAI_API_KEY"]}
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

    def test_get_llm_settings_returns_only_masked_key(self) -> None:
        secret = "sk-test-client-chat-secret"
        self._post_json("/api/settings/llm", {"mode": "single_key", "provider": "openai-compatible", "model": "deepseek-v4-pro", "api_key": secret})

        loaded = self._get_json("/api/settings/llm")
        payload = json.dumps(loaded)

        self.assertTrue(loaded["api_key_configured"])
        masked_values = [
            loaded.get("masked_key"),
            loaded.get("brain_api_key_masked"),
            loaded.get("execution_api_key_masked"),
            (loaded.get("brain_agent") or {}).get("masked_key"),
            (loaded.get("execution_agent") or {}).get("masked_key"),
        ]
        self.assertTrue(any(masked_values))
        self.assertNotIn(secret, payload)
        self.assertNotIn('"api_key":', payload)

    def test_get_llm_settings_treats_llm_api_key_env_as_configured(self) -> None:
        secret = "sk-env-client-chat-secret"
        os.environ["LLM_PROVIDER"] = "openai-compatible"
        os.environ["LLM_MODEL"] = "deepseek-v4-pro"
        os.environ["LLM_BASE_URL"] = "https://example.test/v1"
        os.environ["LLM_API_KEY"] = secret
        os.environ.pop("OPENAI_API_KEY", None)

        loaded = self._get_json("/api/settings/llm")
        payload = json.dumps(loaded)

        self.assertTrue(loaded["api_key_configured"])
        self.assertEqual(loaded["provider"], "openai-compatible")
        self.assertEqual(loaded["model"], "deepseek-v4-pro")
        self.assertNotIn(secret, payload)


if __name__ == "__main__":
    unittest.main()
