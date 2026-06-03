from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(relative: str) -> str:
    return (WEB_CLIENT / relative).read_text(encoding="utf-8")


class WebClientProjectStatusTests(unittest.TestCase):
    def test_api_has_status_and_paths_calls_without_default_project_fallback(self) -> None:
        source = read("api.js")

        self.assertIn("getProjectStatus", source)
        self.assertIn("getProjectPaths", source)
        self.assertIn("requireProjectId", source)
        self.assertNotIn('export const DEFAULT_PROJECT_ID = "default"', source)
        self.assertNotIn("stableId(projectId, DEFAULT_PROJECT_ID)", source)

    def test_state_invalidates_legacy_cache_and_emits_active_project_change(self) -> None:
        source = read("state.js")

        self.assertIn("CLIENT_CACHE_SCHEMA_VERSION", source)
        self.assertIn("clearLegacyProjectCaches", source)
        self.assertIn("researchos:active-project-changed", source)
        self.assertIn("localStorage.removeItem", source)

    def test_projects_page_shows_normal_status_and_developer_only_paths(self) -> None:
        source = read("views/projects.js")

        self.assertIn("getProjectStatus", source)
        self.assertIn("getProjectPaths", source)
        for label in ["项目 ID", "项目根目录", "资料库状态", "知识库状态", "RAG 状态", "文件数量", "生成物数量", "最近 workflow run", "归档状态"]:
            with self.subTest(label=label):
                self.assertIn(label, source)
        self.assertIn("appState.developerMode", source)
        self.assertIn("数据库路径", source)
        self.assertIn("Debug 日志路径", source)

    def test_cached_artifacts_and_workflows_reject_empty_project_scope(self) -> None:
        artifacts = read("artifact_types.js")
        workflows = read("user_workflows.js")

        self.assertNotIn('String(projectId || "default")', artifacts)
        self.assertNotIn('compactId(projectId) || "default"', workflows)
        self.assertNotIn('options.projectId || "default"', workflows)
        self.assertIn("project_id is required", artifacts)
        self.assertIn("project_id is required", workflows)

    def test_chat_and_workspace_clear_project_bound_transient_state_on_switch(self) -> None:
        chat = read("views/chat.js")
        workspace = read("views/workspace.js")

        self.assertIn("researchos:active-project-changed", chat)
        self.assertIn("pendingWorkflow = null", chat)
        self.assertIn("researchos:active-project-changed", workspace)
        self.assertIn("resetWorkspaceForProject", workspace)

    def test_workflow_result_components_do_not_fall_back_to_default_project(self) -> None:
        message = read("components/message.js")
        result = read("components/workflow_result.js")

        self.assertNotIn('|| "default"', message)
        self.assertNotIn('|| "default"', result)
        self.assertNotIn('projectId = "default"', result)


if __name__ == "__main__":
    unittest.main()
