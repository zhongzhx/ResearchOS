from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClientApiContractsTests(unittest.TestCase):
    def test_web_client_uses_mvp_http_adapter_paths(self) -> None:
        api_js = (ROOT / "web_client" / "api.js").read_text(encoding="utf-8")

        self.assertIn('const BACKEND_PREFIX = "/api/backend"', api_js)
        self.assertIn("/research-os/agent/chat", api_js)
        self.assertIn("/api/agents/coordinator/run", api_js)
        self.assertNotIn("backend/researchos", api_js)

    def test_api_client_aborts_slow_backend_requests(self) -> None:
        api_js = (ROOT / "web_client" / "api.js").read_text(encoding="utf-8")

        self.assertIn("REQUEST_TIMEOUT_MS", api_js)
        self.assertIn("MUTATION_TIMEOUT_MS", api_js)
        self.assertIn("AbortController", api_js)
        self.assertIn("signal: controller.signal", api_js)
        self.assertIn("clearTimeout(timeout)", api_js)
        self.assertIn("请求超时", api_js)
        self.assertIn('request("GET", path, undefined, REQUEST_TIMEOUT_MS)', api_js)
        self.assertIn('request("POST", path, body, MUTATION_TIMEOUT_MS)', api_js)

    def test_client_declared_endpoints_exist_or_are_dynamic_in_server(self) -> None:
        api_js = (ROOT / "web_client" / "api.js").read_text(encoding="utf-8")
        server = (ROOT / "backend" / "research_agent_runtime" / "scripts" / "research_agent_api.py").read_text(encoding="utf-8")
        endpoints = sorted(set(re.findall(r'["`](/(?:api|research-os)/[^"`?]+)', api_js)))

        missing = []
        for endpoint in endpoints:
            if endpoint == "/api/backend" or "${" in endpoint:
                continue
            dynamic = endpoint.rstrip("/")
            if dynamic and dynamic not in server:
                missing.append(endpoint)

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
