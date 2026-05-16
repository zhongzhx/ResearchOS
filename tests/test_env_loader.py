import os
import tempfile
import unittest
from pathlib import Path

from backend.researchos.config.env_loader import get_bool_env, get_env, get_int_env, load_env_file, redact_env_value


class EnvLoaderTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in ["RESEARCHOS_ENV_TEST_VALUE", "RESEARCHOS_ENV_TEST_BOOL", "RESEARCHOS_ENV_TEST_INT"]:
            os.environ.pop(key, None)

    def test_env_file_can_load_values_without_overriding_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("RESEARCHOS_ENV_TEST_VALUE=from_file\nRESEARCHOS_ENV_TEST_BOOL=true\n", encoding="utf-8")
            os.environ["RESEARCHOS_ENV_TEST_VALUE"] = "from_os"

            loaded = load_env_file(path)

        self.assertEqual(loaded["RESEARCHOS_ENV_TEST_VALUE"], "from_file")
        self.assertEqual(os.environ["RESEARCHOS_ENV_TEST_VALUE"], "from_os")
        self.assertTrue(get_bool_env("RESEARCHOS_ENV_TEST_BOOL"))

    def test_missing_env_file_falls_back_to_os_environ(self) -> None:
        os.environ["RESEARCHOS_ENV_TEST_INT"] = "42"

        loaded = load_env_file(Path(tempfile.gettempdir()) / "missing-researchos.env")

        self.assertEqual(loaded, {})
        self.assertEqual(get_env("RESEARCHOS_ENV_TEST_INT"), "42")
        self.assertEqual(get_int_env("RESEARCHOS_ENV_TEST_INT"), 42)

    def test_redact_env_value_masks_secret_names(self) -> None:
        self.assertEqual(redact_env_value("OPENAI_API_KEY", "sk-test-secret"), "****cret")
        self.assertEqual(redact_env_value("RESEARCHOS_HOST", "127.0.0.1"), "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
