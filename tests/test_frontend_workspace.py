from pathlib import Path
import re
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


def nav_entry(source: str, view: str) -> str:
    match = re.search(r"\{[^{}]*view:\s*\"" + re.escape(view) + r"\"[^{}]*\}", source)
    return match.group(0) if match else ""


class FrontendWorkspaceTests(unittest.TestCase):
    def test_normal_navigation_contains_user_pages(self) -> None:
        app = read(WEB_CLIENT / "app.js")

        expected = {
            "chat": "对话",
            "workspace": "工作台",
            "projects": "项目",
            "simplified_library": "资料库",
            "settings": "设置",
        }
        for view, label in expected.items():
            with self.subTest(view=view):
                entry = nav_entry(app, view)
                self.assertIn(f'label: "{label}"', entry)
                self.assertNotIn("developerOnly: true", entry)

    def test_normal_navigation_hides_developer_pages(self) -> None:
        app = read(WEB_CLIENT / "app.js")

        expected = {
            "task_lifecycle": "任务调试",
            "brain": "研究记忆",
            "skills": "技能目录",
            "runs": "运行记录",
            "library": "知识库调试",
        }
        for view, label in expected.items():
            with self.subTest(view=view):
                entry = nav_entry(app, view)
                self.assertIn(f'label: "{label}"', entry)
                self.assertIn("developerOnly: true", entry)

        visible_nav_source = re.search(r"function visibleNavItems\(.*?\n}\n", app, re.S)
        self.assertIsNotNone(visible_nav_source)
        self.assertIn("!item.developerOnly", visible_nav_source.group(0))

    def test_workspace_displays_four_user_groups_and_all_task_titles(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        workflows = read(WEB_CLIENT / "user_workflows.js")
        combined = workspace + workflows

        for group in ["找资料", "做实验", "分析数据", "写论文"]:
            with self.subTest(group=group):
                self.assertIn(group, combined)

        expected_titles = [
            "找文献",
            "下载文献并构建知识库",
            "上传 PDF 并学习",
            "论文精读",
            "找支撑引用",
            "生成组会 PPT",
            "设计实验方案",
            "生成 SOP",
            "实验失败复盘",
            "记录今天实验",
            "生成下一步计划",
            "上传表格分析",
            "qPCR / ELISA / CCK-8 数据分析",
            "代谢组结果解释",
            "生成论文图表",
            "机器学习建模助手",
            "写论文段落",
            "英文润色",
            "模拟审稿",
            "审稿回复",
            "投稿材料检查",
            "项目周报",
        ]
        for title in expected_titles:
            with self.subTest(title=title):
                self.assertIn(title, combined)

    def test_workspace_has_search_filters_recent_and_detail_page(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn('placeholder="搜索功能，例如：文献、PPT、qPCR"', workspace)
        self.assertIn("最近使用", workspace)
        self.assertIn('id="workflowDetailPage"', workspace)
        self.assertIn("activeDraft ? renderWorkflowDetailPage(projectId) : renderWorkflowHome(projectId)", workspace)
        styles = read(WEB_CLIENT / "styles.css")
        self.assertNotIn("workspace-layout:has(#workflowDrawer)", styles)
        self.assertNotIn("grid-template-columns: minmax(0, 1fr) minmax(340px, 430px)", styles)
        self.assertIn("data-workflow-intent", workspace)
        self.assertIn("buildWorkflowPlan", workspace)

    def test_workspace_requires_selected_project_before_offering_workflows(self) -> None:
        script = textwrap.dedent(
            f"""
            globalThis.localStorage = {{ getItem: () => null, setItem() {{}}, removeItem() {{}} }};
            globalThis.window = {{ addEventListener() {{}}, dispatchEvent() {{}} }};
            const {{ appState }} = await import({(WEB_CLIENT / "state.js").as_uri()!r});
            const {{ renderWorkspaceView }} = await import({(WEB_CLIENT / "views" / "workspace.js").as_uri()!r});
            appState.activeProjectId = "";
            appState.activeProject = null;
            const root = {{
              innerHTML: "",
              querySelector: () => null,
              querySelectorAll: () => [],
            }};
            await renderWorkspaceView({{ root }});
            if (!root.innerHTML.includes("请先选择或创建项目")) throw new Error("missing project selection prompt");
            if (root.innerHTML.includes("data-workflow-intent")) throw new Error("workflow actions visible without project");
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_workspace_clears_transient_task_state_when_project_changes(self) -> None:
        script = textwrap.dedent(
            f"""
            globalThis.localStorage = {{ getItem: () => null, setItem() {{}}, removeItem() {{}} }};
            globalThis.window = {{ addEventListener() {{}}, dispatchEvent() {{}} }};
            const {{ appState }} = await import({(WEB_CLIENT / "state.js").as_uri()!r});
            const {{ renderWorkspaceView }} = await import({(WEB_CLIENT / "views" / "workspace.js").as_uri()!r});
            let openWorkflow = null;
            const workflowButton = {{
              disabled: false,
              dataset: {{ workflowIntent: "literature_search" }},
              addEventListener: (event, handler) => {{ if (event === "click") openWorkflow = handler; }},
            }};
            const root = {{
              innerHTML: "",
              querySelector: () => null,
              querySelectorAll: (selector) => selector === "[data-workflow-intent]" ? [workflowButton] : [],
            }};
            appState.activeProjectId = "project-a";
            appState.activeProject = {{ id: "project-a" }};
            await renderWorkspaceView({{ root }});
            openWorkflow();
            if (!root.innerHTML.includes('id="workflowDetailPage"')) throw new Error("project A task did not open");
            appState.activeProjectId = "project-b";
            appState.activeProject = {{ id: "project-b" }};
            await renderWorkspaceView({{ root }});
            if (root.innerHTML.includes('id="workflowDetailPage"')) throw new Error("project A task remained visible in project B");
            console.log("ok");
            """
        )
        self.assertEqual(run_node(script), "ok")

    def test_workspace_hides_internal_terms_from_normal_ui(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        render_source = re.search(r"export async function renderWorkspaceView\(.*?\n}\n", workspace, re.S)
        self.assertIsNotNone(render_source)

        forbidden = [
            "skill_id",
            "pipeline_id",
            "SkillRun",
            "TaskSpec",
            "ExecutionResult",
            "Raw JSON",
            "demo_only",
            "not_connected",
            "parser_not_connected",
            "backend route",
            "resolver",
            "internal/control",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, render_source.group(0))

    def test_card_metadata_is_user_level_chinese(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn("需要：", workspace)
        self.assertIn("输出：", workspace)
        self.assertIn("可执行", workspace)
        self.assertIn("可生成计划", workspace)
        self.assertIn("需要上传文件", workspace)
        self.assertIn("正在接入中", workspace)

    def test_confirmation_before_execution(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        plan_handler = re.search(r'id === "plan".*?buildWorkflowPlan', workspace, re.S)
        confirm_handler = re.search(r'id === "confirm".*?await executeWorkflow', workspace, re.S)
        self.assertIsNotNone(plan_handler)
        self.assertIsNotNone(confirm_handler)
        self.assertNotIn("executeWorkflow(", plan_handler.group(0))

    def test_plan_only_workflow_does_not_show_success_copy(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        status = read(WEB_CLIENT / "components" / "workflow_status.js")

        self.assertIn('definition.current_status === "plan_only" ? "生成计划"', workspace)
        self.assertNotIn('plan_only: "已完成"', status)
        self.assertIn('plan_only: "已生成计划"', status)

    def test_not_ready_workflow_button_is_disabled(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn('definition.current_status === "not_ready"', workspace)
        self.assertIn("该功能正在接入中", workspace)
        self.assertIn("disabled", workspace)

    def test_needs_file_and_authorization_have_user_prompts(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn("请先上传文件或选择资料库文件。", workspace)
        self.assertIn("需要授权后执行。", workspace)

    def test_developer_notes_visible_only_in_developer_mode(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")
        status = read(WEB_CLIENT / "components" / "workflow_status.js")

        self.assertIn("developerMode", workspace)
        self.assertIn("developer_notes", workspace)
        self.assertIn("developerMode &&", workspace)
        self.assertIn("技术详情", status)


if __name__ == "__main__":
    unittest.main()
