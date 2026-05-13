import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"
WEB_SERVER = ROOT / "researchos_web_client.py"
PACKAGE_JSON = ROOT / "package.json"
ELECTRON_MAIN = ROOT / "electron" / "main.js"


def load_web_module():
    spec = importlib.util.spec_from_file_location("researchos_web_client", WEB_SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load web client module from {WEB_SERVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResearchOSWebClientTests(unittest.TestCase):
    def test_web_client_assets_exist(self) -> None:
        self.assertTrue((WEB_CLIENT / "index.html").exists())
        self.assertTrue((WEB_CLIENT / "styles.css").exists())
        self.assertTrue((WEB_CLIENT / "app.js").exists())

    def test_home_is_conversation_first_html(self) -> None:
        html = (WEB_CLIENT / "index.html").read_text(encoding="utf-8")

        self.assertIn("data-home-chat", html)
        self.assertIn('data-view="home"', html)
        self.assertNotIn("overview-grid", html)
        self.assertNotIn("dashboard-card", html)

    def test_css_uses_soft_html_surfaces(self) -> None:
        css = (WEB_CLIENT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("--radius-lg: 32px", css)
        self.assertIn("--radius-md: 24px", css)
        self.assertNotIn("border-radius: 0", css)

    def test_web_server_proxies_backend_same_origin(self) -> None:
        module = load_web_module()

        self.assertEqual(module.WEB_ROOT, WEB_CLIENT)
        self.assertTrue(hasattr(module.WebClientHandler, "proxy_backend"))
        self.assertIn("/api/backend", WEB_SERVER.read_text(encoding="utf-8"))

    def test_electron_package_declares_desktop_client_entry(self) -> None:
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

        self.assertEqual(package["main"], "electron/main.js")
        self.assertEqual(package["scripts"]["client:electron"], "electron .")
        self.assertEqual(package["scripts"]["client:electron:smoke"], "electron . --smoke-test")
        self.assertIn("electron", package["devDependencies"])

    def test_electron_main_loads_html_client_without_tk_shell(self) -> None:
        source = ELECTRON_MAIN.read_text(encoding="utf-8")

        self.assertIn("BrowserWindow", source)
        self.assertIn("web_client", source)
        self.assertIn("api/backend", source)
        self.assertIn("nodeIntegration: false", source)
        self.assertIn("--smoke-test", source)
        self.assertNotIn("tkinter", source.lower())


if __name__ == "__main__":
    unittest.main()
