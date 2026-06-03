from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FrontendProjectWorkspaceTests(unittest.TestCase):
    def test_api_exposes_workspace_and_server_artifacts(self) -> None:
        source = read(WEB_CLIENT / "api.js")

        self.assertIn("getWorkspaceState", source)
        self.assertIn('"/research-os/workspace-state"', source)
        self.assertIn("getProjectArtifacts", source)
        self.assertIn('"/research-os/artifacts"', source)
        self.assertIn("archiveProjectArtifact", source)

    def test_normal_library_loads_workspace_and_server_artifacts(self) -> None:
        source = read(WEB_CLIENT / "views" / "simplified_library.js")

        self.assertIn("getWorkspaceState", source)
        self.assertIn("getProjectArtifacts", source)
        self.assertIn("serverArtifacts", source)
        self.assertIn("projectWorkspace", source)
        for label in ["项目工作区", "知识目录", "RAG 范围", "当前项目", "知识库状态"]:
            with self.subTest(label=label):
                self.assertIn(label, source)

    def test_projects_view_shows_active_workspace_paths_and_kb_state(self) -> None:
        source = read(WEB_CLIENT / "views" / "projects.js")

        self.assertIn("getWorkspaceState", source)
        self.assertIn("projectWorkspace", source)
        for label in ["本地项目目录", "知识目录", "RAG 范围", "知识库"]:
            with self.subTest(label=label):
                self.assertIn(label, source)


if __name__ == "__main__":
    unittest.main()
