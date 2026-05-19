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

    def test_workspace_displays_eight_user_task_cards(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        expected_cards = [
            "文献采集与知识库构建",
            "上传 PDF 并学习",
            "实验方案设计",
            "SOP / Protocol 整理",
            "数据分析与作图",
            "写作与审稿",
            "实验失败复盘",
            "周报生成",
        ]
        for title in expected_cards:
            with self.subTest(title=title):
                self.assertIn(title, workspace)

        card_block = re.search(r"const workflowCards = \[(.*?)\];", workspace, re.S)
        self.assertIsNotNone(card_block)
        self.assertEqual(card_block.group(1).count("title:"), 8)

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
            "demo_only",
            "not_connected",
            "parser_not_connected",
            "raw JSON",
            "resolver",
            "backend route",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, render_source.group(0))

    def test_literature_card_opens_form_with_defaults(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn('intent: "literature_harvest_and_kb"', workspace)
        self.assertIn('data-workflow-intent="${escapeHtml(card.intent)}"', workspace)
        self.assertIn("研究主题 / 关键词", workspace)
        self.assertIn('id="${escapeHtml(id)}"', workspace)
        self.assertIn("workflow-max-papers", workspace)
        self.assertIn("values.max_papers || 20", workspace)
        self.assertIn("workflow-oa-only", workspace)
        self.assertIn('id="workflow-build-kb"', workspace)
        self.assertIn("生成计划", workspace)
        self.assertIn("确认开始", workspace)

    def test_confirmation_before_execution(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        plan_handler = re.search(r'id === "plan".*?buildWorkflowPlan', workspace, re.S)
        confirm_handler = re.search(r'id === "confirm".*?await executeWorkflow', workspace, re.S)
        self.assertIsNotNone(plan_handler)
        self.assertIsNotNone(confirm_handler)
        self.assertNotIn("executeWorkflow(", plan_handler.group(0))

    def test_start_user_workflow_uses_controller(self) -> None:
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn("export async function startUserWorkflow(intent, params = {})", workspace)
        self.assertIn("createWorkflowDraft", workspace)
        self.assertIn("executeWorkflow", workspace)
        start_block = re.search(r"export async function startUserWorkflow\(.*?\n}\n", workspace, re.S)
        self.assertIsNotNone(start_block)
        self.assertNotIn("skill_id", start_block.group(0))

    def test_developer_mode_can_show_technical_details(self) -> None:
        app = read(WEB_CLIENT / "app.js")
        state = read(WEB_CLIENT / "state.js")
        workspace = read(WEB_CLIENT / "views" / "workspace.js")

        self.assertIn("developerMode", state)
        self.assertIn("setDeveloperMode", state)
        self.assertIn("developerOnly: true", app)
        status = read(WEB_CLIENT / "components" / "workflow_status.js")
        self.assertIn("技术详情", status)


if __name__ == "__main__":
    unittest.main()
