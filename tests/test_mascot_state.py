from pathlib import Path
import json
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"


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


class MascotStateTests(unittest.TestCase):
    def test_agent_states_map_to_stable_asset_paths_and_messages(self) -> None:
        module_url = (WEB_CLIENT / "components" / "mascot.js").as_uri()
        script = textwrap.dedent(
            f"""
            const {{ getMascotForState, getMascotMessage, mascotStateForTaskStatus }} = await import({module_url!r});
            const result = {{
              idle: getMascotForState("idle"),
              routing: getMascotForState("routing"),
              harvesting: getMascotForState("harvesting_literature"),
              waiting: getMascotForState("waiting_user_confirmation"),
              error: getMascotForState("error"),
              unknown: getMascotForState("unmapped_state"),
              workingText: getMascotMessage("working"),
              waitingText: getMascotMessage("waiting_user_confirmation"),
              pendingTask: getMascotForState(mascotStateForTaskStatus("pending")),
              runningTask: getMascotForState(mascotStateForTaskStatus("running")),
              completedTask: getMascotForState(mascotStateForTaskStatus("completed")),
              failedTask: getMascotForState(mascotStateForTaskStatus("failed")),
              warningTask: getMascotForState(mascotStateForTaskStatus("warning")),
            }};
            console.log(JSON.stringify(result));
            """
        )
        values = json.loads(run_node(script))

        self.assertEqual(values["idle"], "/assets/mascot/c57_default.png")
        self.assertEqual(values["routing"], "/assets/mascot/c57_thinking.png")
        self.assertEqual(values["harvesting"], "/assets/mascot/c57_working.png")
        self.assertEqual(values["waiting"], "/assets/mascot/c57_listening.png")
        self.assertEqual(values["error"], "/assets/mascot/c57_confused.png")
        self.assertEqual(values["unknown"], "/assets/mascot/c57_default.png")
        self.assertEqual(values["workingText"], "我正在处理任务…")
        self.assertEqual(values["waitingText"], "等你确认后我就开始。")
        self.assertEqual(values["pendingTask"], "/assets/mascot/c57_listening.png")
        self.assertEqual(values["runningTask"], "/assets/mascot/c57_working.png")
        self.assertEqual(values["completedTask"], "/assets/mascot/c57_happy.png")
        self.assertEqual(values["failedTask"], "/assets/mascot/c57_confused.png")
        self.assertEqual(values["warningTask"], "/assets/mascot/c57_surprised.png")

    def test_missing_mascot_image_switches_to_default_asset(self) -> None:
        module_url = (WEB_CLIENT / "components" / "mascot.js").as_uri()
        script = textwrap.dedent(
            f"""
            const {{ bindMascotFallbacks, renderMascot }} = await import({module_url!r});
            let errorHandler;
            const image = {{
              dataset: {{ mascotFallback: "/assets/mascot/c57_default.png" }},
              src: "/assets/mascot/c57_peace.png",
              addEventListener: (type, handler) => {{ if (type === "error") errorHandler = handler; }},
            }};
            bindMascotFallbacks({{ querySelectorAll: () => [image] }});
            errorHandler();
            console.log(JSON.stringify({{
              src: image.src,
              applied: image.dataset.mascotFallbackApplied,
              markup: renderMascot("onboarding_complete"),
            }}));
            """
        )
        values = json.loads(run_node(script))

        self.assertEqual(values["src"], "/assets/mascot/c57_default.png")
        self.assertEqual(values["applied"], "true")
        self.assertIn('src="/assets/mascot/c57_peace.png"', values["markup"])
        self.assertIn('data-mascot-fallback="/assets/mascot/c57_default.png"', values["markup"])

    def test_visual_surfaces_use_mascot_display_layer(self) -> None:
        message = (WEB_CLIENT / "components" / "message.js").read_text(encoding="utf-8")
        workflow_status = (WEB_CLIENT / "components" / "workflow_status.js").read_text(encoding="utf-8")
        chat = (WEB_CLIENT / "views" / "chat.js").read_text(encoding="utf-8")

        self.assertIn("renderMascot", message)
        self.assertIn("waiting_user_confirmation", message)
        self.assertIn("renderMascot", workflow_status)
        self.assertIn("renderMascotFeedback", chat)
        self.assertIn("bindMascotFallbacks", chat)
        self.assertIn("这里出了一点问题，我暂时无法回复。请稍后再试。", chat)
        self.assertNotIn("后端连接失败", chat)
        self.assertNotIn("内部协调器", chat)
        self.assertNotIn("稳定聊天", chat)

    def test_empty_chat_header_keeps_one_welcome_line_without_status_labels(self) -> None:
        chat = (WEB_CLIENT / "views" / "chat.js").read_text(encoding="utf-8")

        self.assertEqual(chat.count("欢迎使用 Aura Research，有什么可以帮忙的？"), 1)
        self.assertNotIn("可以直接输入文献方向、实验问题、分析需求或下一步任务", chat)
        self.assertNotIn("chat-context-row", chat)
        self.assertNotIn('<p class="eyebrow">', chat)
        self.assertNotIn('appState.dualAgentEnabled ? "研究模式" : "标准模式"', chat)


if __name__ == "__main__":
    unittest.main()
