import unittest
from unittest.mock import patch

from backend.researchos.agents.brain_agent import model_identity_response


class CoordinatorLlmGatewayIntegrationTests(unittest.TestCase):
    def test_model_identity_uses_llm_gateway_summary_not_raw_environment_secret(self) -> None:
        with patch("backend.researchos.llm.gateway.get_llm_config_for_agent", return_value={"provider": "mock", "model": "mock-model", "base_url": "", "key_configured": False}):
            result = model_identity_response()

        self.assertTrue(result["ok"])
        self.assertIn("mock-model", result["answer"])
        self.assertNotIn("api_key", result["answer"].lower())


if __name__ == "__main__":
    unittest.main()
