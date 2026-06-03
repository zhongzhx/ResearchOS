from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web_client"


class FrontendDeveloperModeVisibilityTests(unittest.TestCase):
    def test_developer_navigation_is_appended_only_after_toggle(self) -> None:
        app = (WEB / "app.js").read_text(encoding="utf-8")

        self.assertIn('view: "chat"', app)
        self.assertIn('view: "workspace"', app)
        self.assertIn('view: "projects"', app)
        self.assertIn('view: "simplified_library"', app)
        self.assertIn('view: "settings"', app)
        for view in ["task_lifecycle", "brain", "skills", "runs", "library", "developer_diagnostics"]:
            with self.subTest(view=view):
                self.assertIn(f'view: "{view}"', app)
        self.assertIn("developerOnly: true", app)
        self.assertIn("appState.developerMode || !item.developerOnly", app)

    def test_raw_artifact_records_require_developer_mode(self) -> None:
        artifact = (WEB / "components" / "artifact_card.js").read_text(encoding="utf-8")
        settings = (WEB / "views" / "settings.js").read_text(encoding="utf-8")

        self.assertIn('developerDetails("Artifact raw record", artifact, developerMode)', artifact)
        self.assertIn("appState.developerMode", settings)


if __name__ == "__main__":
    unittest.main()
