from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
API_JS = ROOT / "web_client" / "api.js"
CHAT_JS = ROOT / "web_client" / "views" / "chat.js"
MESSAGE_JS = ROOT / "web_client" / "components" / "message.js"
PROJECT_SWITCHER_JS = ROOT / "web_client" / "components" / "project_switcher.js"
ELECTRON_MAIN = ROOT / "electron" / "main.js"
PYTEST_INI = ROOT / "pytest.ini"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_chat_answer(payload: str) -> str:
    script = textwrap.dedent(
        f"""
        import {{ chatAnswerMessage }} from {MESSAGE_JS.as_uri()!r};
        const html = chatAnswerMessage({payload}, "fallback");
        process.stdout.write(html);
        """
    )
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


class ChatStabilityTests(unittest.TestCase):
    def test_default_chat_uses_legacy_endpoint_and_not_coordinator(self) -> None:
        chat = read(CHAT_JS)
        api = read(API_JS)

        self.assertIn('apiPost("/research-os/agent/chat"', api)
        self.assertIn("currentChatSessionIds(activeProjectId)", chat)
        self.assertIn("sendLegacyChat(prompt, activeProjectId, conversationId, sessionId)", chat)
        self.assertIn("if (appState.dualAgentEnabled)", chat)
        stable_block = chat.split("async function sendStableChat", 1)[1].split("async function sendCoordinatorChat", 1)[0]
        self.assertNotIn("runCoordinator", stable_block)

    def test_experimental_coordinator_only_runs_after_toggle(self) -> None:
        chat = read(CHAT_JS)
        settings = read(ROOT / "web_client" / "views" / "settings.js")

        self.assertIn("dualAgentEnabled: false", read(ROOT / "web_client" / "state.js"))
        self.assertNotIn("experimentalModeToggle", chat + settings)
        self.assertIn("开发者模式", settings)
        self.assertIn("runCoordinator(prompt, activeProjectId, conversationId, sessionId)", chat)

    def test_message_renderer_prefers_answer_then_content_then_message(self) -> None:
        self.assertIn("Answer wins", render_chat_answer('{ answer: "Answer wins", content: "Content loses", message: "Message loses" }'))
        self.assertIn("Content wins", render_chat_answer('{ content: "Content wins", message: "Message loses" }'))
        self.assertIn("Message wins", render_chat_answer('{ message: "Message wins" }'))

    def test_message_renderer_hides_task_handoff_in_default_chat(self) -> None:
        html = render_chat_answer('{ answer: "Research Task Handoff\\ntask_abc123\\ninternal execution notes" }')

        self.assertIn("该内容来自内部任务执行链路，已隐藏技术细节。可在功能导航中查看任务详情。", html)
        self.assertNotIn("task_abc123", html)
        self.assertNotIn("internal execution notes", html)

    def test_structured_object_degrades_to_summary_not_raw_json(self) -> None:
        html = render_chat_answer('{ task_spec: { id: "task_123" }, execution_result: { status: "success" } }')

        self.assertIn("该内容来自内部任务执行链路，已隐藏技术细节。可在功能导航中查看任务详情。", html)
        self.assertNotIn('"task_spec"', html)
        self.assertNotIn("task_123", html)

    def test_markdown_experiment_sections_render_as_readable_blocks(self) -> None:
        html = render_chat_answer('{ answer: "## 实验名称\\nRAW264.7 炎症模型\\n## 实验目的\\n验证干预物影响\\n## 实验试剂\\n- RAW264.7\\n- LPS\\n## 实验模型\\n细胞模型\\n## 实验步骤\\n1. 接种细胞\\n2. 加药处理" }')

        self.assertIn('<h3>实验名称</h3>', html)
        self.assertIn('<h3>实验目的</h3>', html)
        self.assertIn('<li>RAW264.7</li>', html)
        self.assertIn('<li>接种细胞</li>', html)

    def test_missing_project_id_shows_create_project_guide_and_api_rejects_fallback(self) -> None:
        chat = read(CHAT_JS)
        api = read(API_JS)

        self.assertIn("resolveChatProjectId", chat)
        self.assertIn("创建一个项目，开始保存你的研究对话和资料。", chat)
        self.assertIn("if (!activeProjectId) return false", chat)
        self.assertIn("project_id: safeProjectId", api)
        self.assertIn("requireProjectId", api)
        self.assertNotIn('DEFAULT_PROJECT_ID = "default"', api)

    def test_project_display_name_prefers_human_fields(self) -> None:
        switcher = read(PROJECT_SWITCHER_JS)
        chat = read(CHAT_JS)

        self.assertIn("display_name || project.title || project.name", switcher)
        self.assertIn('projectLabel(appState.activeProject)', chat)
        self.assertIn("未命名项目", switcher)
        self.assertIn("projectDisplayName(project)", chat)
        self.assertNotIn("默认项目 ${DEFAULT_PROJECT_ID}", chat)

    def test_direct_file_open_and_proxy_failure_are_user_readable(self) -> None:
        api = read(API_JS)
        chat = read(CHAT_JS)
        electron = read(ELECTRON_MAIN)

        self.assertIn('window.location.protocol === "file:"', api)
        self.assertIn("请通过 Electron 或本地服务启动", api)
        self.assertIn("这里出了一点问题，我暂时无法回复。请稍后再试。", chat)
        self.assertIn("research_agent_api.py", electron)
        self.assertIn('replace(/^\\/api\\/backend/, "")', electron)

    def test_enter_sends_and_shift_enter_inserts_newline(self) -> None:
        chat = read(CHAT_JS)

        self.assertIn('event.key === "Enter" && !event.shiftKey', chat)
        self.assertIn("event.preventDefault()", chat)
        self.assertIn("submitPrompt(root, input.value.trim())", chat)

    def test_pytest_defaults_to_researchos_tests_only(self) -> None:
        config = read(PYTEST_INI)

        self.assertIn("testpaths = tests", config)


if __name__ == "__main__":
    unittest.main()
