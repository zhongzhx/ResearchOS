import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"
PACKAGE_JSON = ROOT / "package.json"
ELECTRON_MAIN = ROOT / "electron" / "main.js"
LEGACY_CLIENT_FILES = [
    ROOT / "researchos_local_client.pyw",
    ROOT / "researchos_web_client.py",
    ROOT / "tests" / "test_local_client_boot.py",
    ROOT / "tests" / "test_researchos_local_client_project_actions.py",
]


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

    def test_electron_package_declares_desktop_client_entry(self) -> None:
        package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

        self.assertEqual(package["main"], "electron/main.js")
        self.assertEqual(package["scripts"]["client:electron"], "electron .")
        self.assertEqual(package["scripts"]["client:electron:smoke"], "electron . --smoke-test")
        self.assertNotIn("client:web", package["scripts"])
        self.assertIn("electron", package["devDependencies"])

    def test_electron_main_loads_html_client_without_tk_shell(self) -> None:
        source = ELECTRON_MAIN.read_text(encoding="utf-8")

        self.assertIn("BrowserWindow", source)
        self.assertIn("web_client", source)
        self.assertIn("api/backend", source)
        self.assertIn("nodeIntegration: false", source)
        self.assertIn("--smoke-test", source)
        self.assertNotIn("tkinter", source.lower())

    def test_legacy_python_clients_are_removed(self) -> None:
        for path in LEGACY_CLIENT_FILES:
            with self.subTest(path=path.name):
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
