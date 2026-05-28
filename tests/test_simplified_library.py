from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


class SimplifiedLibraryTests(unittest.TestCase):
    def test_normal_library_shows_user_level_sections(self) -> None:
        source = read(WEB_CLIENT / "views" / "simplified_library.js")
        expected = [
            "已上传文件",
            "已生成文档",
            "文献清单",
            "手动下载队列",
            "知识库状态",
            "simpleLibrarySearch",
        ]
        for token in expected:
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_normal_library_hides_debug_terms(self) -> None:
        source = read(WEB_CLIENT / "views" / "simplified_library.js")
        forbidden = [
            "chunk list",
            "raw chunks",
            "raw RAG query JSON",
            "backend route",
            "parser_not_connected",
            "SkillRun",
            "Execution Memory",
            "getReferenceChunks",
            "getRagQueries",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_library_renders_artifacts_files_literature_and_kb_status(self) -> None:
        script = textwrap.dedent(
            f"""
            const store = new Map();
            globalThis.localStorage = {{
              getItem: (key) => store.has(key) ? store.get(key) : null,
              setItem: (key, value) => store.set(key, value),
              removeItem: (key) => store.delete(key),
            }};
            globalThis.window = {{ addEventListener() {{}}, dispatchEvent() {{}} }};
            const {{ appState }} = await import({(WEB_CLIENT / "state.js").as_uri()!r});
            const {{ saveArtifactToProject }} = await import({(WEB_CLIENT / "artifact_types.js").as_uri()!r});
            const {{ renderSimplifiedLibraryContent }} = await import({(WEB_CLIENT / "views" / "simplified_library.js").as_uri()!r});
            appState.activeProjectId = "project-a";
            saveArtifactToProject("project-a", {{
              workflow_id: "chat-paper-reader",
              artifact_type: "paper_reading_markdown",
              title: "Chat generated reading",
              content: "markdown",
              source_intent: "paper_reader",
            }});
            saveArtifactToProject("project-a", {{
              workflow_id: "workspace-figure",
              artifact_type: "publication_figure",
              title: "Workspace generated figure",
              content: "<svg></svg>",
              source_intent: "figure_generation",
            }});
            saveArtifactToProject("project-b", {{
              artifact_type: "weekly_report_document",
              title: "Other project",
              content: "not visible",
              source_intent: "weekly_report",
            }});
            const html = renderSimplifiedLibraryContent({{
              projectId: "project-a",
              references: [{{ title: "Reference A", doi: "10.1/a", journal: "Nature" }}],
              files: [{{ file_name: "paper.pdf", path: "/tmp/paper.pdf", status: "uploaded" }}],
              knowledge: [{{ title: "KB Status", summary: "ready", status: "ready" }}],
              paperRequests: [{{ title: "Need full text", doi: "10.1/manual", reason: "non-oa" }}],
            }});
            for (const token of ["Chat generated reading", "Workspace generated figure", "Reference A", "paper.pdf", "Need full text", "知识库状态"]) {{
              if (!html.includes(token)) throw new Error(`missing ${{token}}`);
            }}
            if (html.includes("Other project")) throw new Error("project scoped artifact leaked");
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_library_does_not_show_default_content_without_selected_project(self) -> None:
        script = textwrap.dedent(
            f"""
            const store = new Map();
            globalThis.localStorage = {{
              getItem: (key) => store.has(key) ? store.get(key) : null,
              setItem: (key, value) => store.set(key, value),
              removeItem: (key) => store.delete(key),
            }};
            globalThis.window = {{ addEventListener() {{}}, dispatchEvent() {{}} }};
            const {{ saveArtifactToProject }} = await import({(WEB_CLIENT / "artifact_types.js").as_uri()!r});
            const {{ renderSimplifiedLibraryContent }} = await import({(WEB_CLIENT / "views" / "simplified_library.js").as_uri()!r});
            saveArtifactToProject("default", {{
              artifact_type: "literature_table",
              title: "Unscoped historical paper",
              content: "must stay hidden",
            }});
            const html = renderSimplifiedLibraryContent({{
              projectId: "",
              references: [{{ title: "Returned without project scope" }}],
            }});
            if (!html.includes("请先选择或创建项目")) throw new Error("missing project selection prompt");
            if (html.includes("Unscoped historical paper") || html.includes("Returned without project scope")) {{
              throw new Error("unscoped library content leaked");
            }}
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_library_does_not_request_backend_without_selected_project(self) -> None:
        script = textwrap.dedent(
            f"""
            globalThis.localStorage = {{ getItem: () => null, setItem() {{}}, removeItem() {{}} }};
            globalThis.window = {{ location: {{ protocol: "http:" }}, addEventListener() {{}}, dispatchEvent() {{}} }};
            globalThis.fetch = () => {{ throw new Error("backend must not be queried without a project"); }};
            const {{ appState }} = await import({(WEB_CLIENT / "state.js").as_uri()!r});
            const {{ renderSimplifiedLibraryView }} = await import({(WEB_CLIENT / "views" / "simplified_library.js").as_uri()!r});
            appState.activeProjectId = "";
            const content = {{ innerHTML: "" }};
            const search = {{ addEventListener() {{}} }};
            const root = {{
              innerHTML: "",
              querySelector: (selector) => selector === "#simpleLibraryContent" ? content : selector === "#simpleLibrarySearch" ? search : null,
            }};
            await renderSimplifiedLibraryView({{ root }});
            if (!content.innerHTML.includes("请先选择或创建项目")) throw new Error("missing project selection prompt");
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_developer_library_does_not_request_backend_without_selected_project(self) -> None:
        script = textwrap.dedent(
            f"""
            globalThis.localStorage = {{ getItem: () => null, setItem() {{}}, removeItem() {{}} }};
            globalThis.window = {{ location: {{ protocol: "http:" }}, addEventListener() {{}}, dispatchEvent() {{}} }};
            globalThis.fetch = () => {{ throw new Error("backend must not be queried without a project"); }};
            const {{ appState }} = await import({(WEB_CLIENT / "state.js").as_uri()!r});
            const {{ renderLibraryView }} = await import({(WEB_CLIENT / "views" / "library.js").as_uri()!r});
            appState.activeProjectId = "";
            const workbench = {{ innerHTML: "" }};
            const content = {{ innerHTML: "" }};
            const search = {{ addEventListener() {{}} }};
            const root = {{
              innerHTML: "",
              querySelector: (selector) => selector === "#libraryWorkbench" ? workbench : selector === "#libraryContent" ? content : selector === "#librarySearch" ? search : null,
              querySelectorAll: () => [],
            }};
            await renderLibraryView({{ root }});
            if (!content.innerHTML.includes("请先选择或创建项目")) throw new Error("missing project selection prompt");
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_chat_and_workspace_save_paths_call_project_artifact_storage(self) -> None:
        chat = read(WEB_CLIENT / "views" / "chat.js")
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn("saveWorkflowArtifacts", chat)
        self.assertIn("saveWorkflowArtifacts", workspace)


if __name__ == "__main__":
    unittest.main()
