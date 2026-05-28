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
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def render_chat_answer(payload: str) -> str:
    return run_node(
        f"""
        const {{ chatAnswerMessage }} = await import({(WEB_CLIENT / "components" / "message.js").as_uri()!r});
        process.stdout.write(chatAnswerMessage({payload}, "fallback"));
        """
    )


class FrontendCopyCleanlinessTests(unittest.TestCase):
    def test_display_text_maps_internal_status_codes_to_chinese(self) -> None:
        output = run_node(
            f"""
            const {{ displayStatus }} = await import({(WEB_CLIENT / "ui_text.js").as_uri()!r});
            const values = ["demo_only", "not_connected", "partial", "needs_authorization", "parser_not_connected", "experimental", "legacy_stable", "safe_to_promote", "failed", "completed", "running"];
            process.stdout.write(values.map((value) => `${{value}}:${{displayStatus(value)}}`).join("\\n"));
            """
        )

        self.assertIn("demo_only:演示预览", output)
        self.assertIn("not_connected:尚未接入", output)
        self.assertIn("needs_authorization:需要授权", output)
        self.assertIn("parser_not_connected:数据解析器尚未接入", output)
        self.assertIn("legacy_stable:稳定聊天", output)
        self.assertIn("safe_to_promote:可加入项目记忆", output)

    def test_plain_chat_template_contains_no_internal_copy(self) -> None:
        source = read(WEB_CLIENT / "views" / "chat.js")
        render_match = re.search(r"export async function renderChatView\(.*?\n}\n", source, re.S)
        self.assertIsNotNone(render_match)
        render_source = render_match.group(0).lower()

        forbidden = [
            "demo_only",
            "not_connected",
            "dual-agent",
            "experimental",
            "product flow",
            "backend route",
            "skillrun",
            "pipeline",
            "resolver",
            "raw json",
            "taskspec",
            "executionresult",
            "execution memory",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, render_source)
        for label in ["新对话", "发送", "创建项目", "当前项目", "输入你的研究问题"]:
            self.assertIn(label, source)

    def test_message_hides_internal_task_payload_with_chinese_notice(self) -> None:
        html = render_chat_answer('{ answer: "Research Task Handoff\\nTaskSpec: task_123\\nExecutionResult: success\\nSkillRun abc" }')

        self.assertIn("该内容来自内部任务执行链路，已隐藏技术细节。可在功能导航中查看任务详情。", html)
        self.assertNotIn("TaskSpec", html)
        self.assertNotIn("SkillRun", html)

    def test_plain_explanation_of_task_spec_is_not_hidden(self) -> None:
        html = render_chat_answer('{ answer: "TaskSpec 是任务规格，用来描述目标、输入和成功标准。" }')

        self.assertIn("TaskSpec 是任务规格", html)
        self.assertNotIn("已隐藏技术细节", html)

    def test_raw_json_only_appears_behind_developer_mode_guard(self) -> None:
        message = read(WEB_CLIENT / "components" / "message.js")

        self.assertNotIn('jsonDetails("Raw JSON"', message)
        self.assertIn("jsonDetails", message)
        self.assertIn("原始数据", message)

    def test_no_user_visible_debug_sentence_left_in_web_client_sources(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in WEB_CLIENT.rglob("*") if path.suffix in {".js", ".html", ".css"})

        forbidden = [
            "Real product execution is not wired from the UI.",
            "Dual Agent Runtime",
            "Runtime Settings",
            "Library / Evidence",
            "Skills / Pipelines",
            "Runs / Execution",
            "Task Lifecycle",
            "Research Brain",
            "Raw JSON",
            "Not connected",
            "Experimental",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
