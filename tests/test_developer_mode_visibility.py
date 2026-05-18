from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def nav_entry(source: str, view: str) -> str:
    match = re.search(r"\{[^{}]*view:\s*\"" + re.escape(view) + r"\"[^{}]*\}", source)
    return match.group(0) if match else ""


class DeveloperModeVisibilityTests(unittest.TestCase):
    def test_navigation_is_chinese_and_includes_all_feature_pages(self) -> None:
        app = read(WEB_CLIENT / "app.js")

        expected = {
            "chat": "对话",
            "projects": "项目",
            "library": "知识库",
            "task_lifecycle": "任务",
            "brain": "研究记忆",
            "skills": "技能",
            "runs": "运行记录",
            "settings": "设置",
        }
        for view, label in expected.items():
            entry = nav_entry(app, view)
            self.assertIn(f'label: "{label}"', entry)
            self.assertNotIn("developerOnly", entry)

    def test_settings_has_no_developer_mode_copy_or_toggle(self) -> None:
        settings = read(WEB_CLIENT / "views" / "settings.js")

        for token in ["开发者模式", "Developer Mode", "developerModeToggle", "setDeveloperMode", "experimentalModeToggle"]:
            with self.subTest(token=token):
                self.assertNotIn(token, settings)

    def test_internal_details_are_folded_by_default(self) -> None:
        message = read(WEB_CLIENT / "components" / "message.js")
        json_viewer = read(WEB_CLIENT / "components" / "json_viewer.js")

        self.assertIn("jsonDetails", message)
        self.assertIn("open = false", json_viewer)
        self.assertNotIn('jsonDetails("原始数据", data, true)', message)

    def test_shell_removes_status_pills_and_brand_tagline(self) -> None:
        index = read(WEB_CLIENT / "index.html")
        app = read(WEB_CLIENT / "app.js")

        for token in ["dualAgentPill", "runtimePill", "面向湿实验科研的 AI 工作台", "dev-status"]:
            with self.subTest(token=token):
                self.assertNotIn(token, index + app)

    def test_normal_pages_do_not_include_old_english_titles(self) -> None:
        combined = "\n".join(read(path) for path in [WEB_CLIENT / "index.html", WEB_CLIENT / "views" / "chat.js", WEB_CLIENT / "views" / "projects.js", WEB_CLIENT / "views" / "settings.js"])

        for token in ["Task Lifecycle", "Research Brain", "Library / Evidence", "Skills / Pipelines", "Runs / Execution", "Product Feature"]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
