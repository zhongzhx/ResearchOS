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


class FrontendInformationArchitectureTests(unittest.TestCase):
    def test_project_selection_falls_back_to_existing_project_on_startup(self) -> None:
        state = read(WEB_CLIENT / "state.js")
        app = read(WEB_CLIENT / "app.js")
        switcher = read(WEB_CLIENT / "components" / "project_switcher.js")
        projects = read(WEB_CLIENT / "views" / "projects.js")

        self.assertIn("appState.cachedProjects[0]", state)
        self.assertIn('setCurrentView("chat")', app)
        self.assertNotIn("|| projects?.[0]", switcher)
        self.assertIn('setCurrentView("chat")', projects)
        self.assertIn("startNewConversation(projectId(created))", projects)

    def test_navigation_separates_normal_and_developer_pages(self) -> None:
        app = read(WEB_CLIENT / "app.js")
        index = read(WEB_CLIENT / "index.html")

        self.assertIn('id="mainNavigation"', index)
        for view in ["chat", "workspace", "projects", "simplified_library", "settings"]:
            with self.subTest(view=view):
                self.assertIn(f'view: "{view}"', app)
                self.assertNotIn("developerOnly: true", nav_entry(app, view))
        for view in ["library", "task_lifecycle", "brain", "skills", "runs", "developer_diagnostics"]:
            with self.subTest(view=view):
                self.assertIn(f'view: "{view}"', app)
                self.assertIn("developerOnly: true", nav_entry(app, view))
        self.assertIn("visibleNavItems", app)
        self.assertIn("canAccessView", app)

    def test_developer_mode_toggle_exists_without_shell_status_pills(self) -> None:
        app = read(WEB_CLIENT / "app.js")
        state = read(WEB_CLIENT / "state.js")
        settings = read(WEB_CLIENT / "views" / "settings.js")
        index = read(WEB_CLIENT / "index.html")

        for token in ["developerMode", "developerOnly", "developerModeToggle", "setDeveloperMode"]:
            with self.subTest(token=token):
                self.assertIn(token, app + state + settings)
        for token in ["dualAgentPill", "runtimePill", "协调器就绪", "运行时在线"]:
            with self.subTest(token=token):
                self.assertNotIn(token, index + app)
        self.assertNotIn("面向湿实验科研的 AI 工作台", index)

    def test_raw_details_remain_folded_without_developer_mode(self) -> None:
        json_viewer = read(WEB_CLIENT / "components" / "json_viewer.js")
        combined_views = "\n".join(read(path) for path in (WEB_CLIENT / "views").glob("*.js"))

        self.assertIn("open = false", json_viewer)
        self.assertNotIn(", true)", combined_views)

    def test_plain_chat_template_hides_internal_runtime_copy(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        render_match = re.search(r"export async function renderChatView\(.*?\n}\n", chat, re.S)
        self.assertIsNotNone(render_match)
        render_source = render_match.group(0)

        forbidden = [
            "demo_only",
            "not_connected",
            "SkillRun",
            "Pipeline",
            "TaskSpec",
            "Raw JSON",
            "Execution Memory",
            "MemoryOS",
            "Resolver",
            "Backend route",
            "Research Task Lifecycle",
            "Product feature demo",
            "experimentalModeToggle",
            "demoButton",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, render_source)

    def test_current_view_defaults_to_chat_without_internal_view_sanitizer(self) -> None:
        state = read(WEB_CLIENT / "state.js")

        self.assertIn('currentView: initialCurrentView()', state)
        self.assertIn('return storedView || "chat"', state)
        self.assertNotIn("isInternalView(storedView)", state)


if __name__ == "__main__":
    unittest.main()
