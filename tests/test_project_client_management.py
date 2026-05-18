from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ProjectClientManagementTests(unittest.TestCase):
    def test_project_switcher_shows_only_selected_project_and_create_entry(self) -> None:
        source = read(WEB_CLIENT / "components" / "project_switcher.js")

        self.assertIn('display_name || project.title || project.name || "未命名项目"', source)
        self.assertIn("currentProjectName", source)
        self.assertIn("新建项目", source)
        self.assertIn('data-view-target="projects"', source)
        self.assertNotIn("|| projects?.[0]", source)

    def test_create_project_calls_api_starts_conversation_and_opens_chat(self) -> None:
        source = read(WEB_CLIENT / "views" / "projects.js")
        app = read(WEB_CLIENT / "app.js")

        self.assertIn("createProject({ title: name, display_name: name })", source)
        self.assertLess(app.index("result.data.projects"), app.index("result.data.grouped?.active"))
        self.assertIn("setActiveProjectId(projectId(created))", source)
        self.assertIn("startNewConversation(projectId(created))", source)
        self.assertIn('setCurrentView("chat")', source)
        self.assertIn("await refreshProjects()", source)

    def test_rename_project_calls_update_api_and_refreshes_name(self) -> None:
        source = read(WEB_CLIENT / "views" / "projects.js")

        self.assertIn("updateProject(activeId, { title: name, display_name: name })", source)
        self.assertIn("renameProjectButton", source)
        self.assertIn("await refreshProjects()", source)

    def test_archive_requires_confirm_and_uses_archive_api(self) -> None:
        source = read(WEB_CLIENT / "views" / "projects.js")

        self.assertIn("archiveProject(activeId)", source)
        self.assertIn("confirm(", source)
        self.assertIn("archiveProjectButton", source)

    def test_clear_project_requires_second_confirmation_and_payload_confirmation(self) -> None:
        source = read(WEB_CLIENT / "views" / "projects.js")
        api = read(WEB_CLIENT / "api.js")

        self.assertIn('clearProject(activeId, { scope: "all", confirmation: clearPhrase })', source)
        self.assertGreaterEqual(source.count("confirm("), 2)
        self.assertIn("清空当前项目相关数据", source)
        self.assertIn("clearProject = (projectId, payload = {})", api)

    def test_purge_project_is_available_in_project_tools_without_developer_mode(self) -> None:
        source = read(WEB_CLIENT / "views" / "projects.js")

        self.assertNotIn("appState.developerMode", source)
        self.assertIn("purgeProject(activeId", source)
        self.assertIn("data-delete-project-id", source)
        self.assertIn("purgeProject(targetId", source)
        self.assertIn("危险区", source)


if __name__ == "__main__":
    unittest.main()
