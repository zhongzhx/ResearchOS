from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ChatDefaultModeTests(unittest.TestCase):
    def test_chat_default_uses_stable_mvp_chat_before_coordinator(self) -> None:
        source = (ROOT / "web_client" / "views" / "chat.js").read_text(encoding="utf-8")
        submit_match = re.search(r"async function submitPrompt\(.*?\n}\n", source, re.S)
        stable_match = re.search(r"async function sendStableChat\(.*?\n}\n", source, re.S)
        experimental_match = re.search(r"async function sendExperimentalChat\(.*?\n}\n", source, re.S)
        self.assertIsNotNone(submit_match)
        self.assertIsNotNone(stable_match)
        self.assertIsNotNone(experimental_match)
        submit_source = submit_match.group(0)
        stable_source = stable_match.group(0)
        experimental_source = experimental_match.group(0)

        self.assertIn("sendLegacyChat(prompt, appState.activeProjectId, appState.conversationId)", stable_source)
        self.assertIn("runCoordinator(prompt, appState.activeProjectId, appState.conversationId)", experimental_source)
        self.assertIn("if (appState.dualAgentEnabled)", submit_source)
        self.assertIn("await sendStableChat(prompt)", submit_source)
        self.assertLess(submit_source.index("if (appState.dualAgentEnabled)"), submit_source.index("await sendStableChat(prompt)"))

    def test_dual_agent_is_explicit_experimental_mode(self) -> None:
        source = (ROOT / "web_client" / "views" / "chat.js").read_text(encoding="utf-8")
        state_source = (ROOT / "web_client" / "state.js").read_text(encoding="utf-8")

        self.assertIn("experimentalModeToggle", source)
        self.assertIn("双 Agent 实验模式", source)
        self.assertIn("setDualAgentEnabled", source)
        self.assertIn("dualAgentEnabled: false", state_source)
        self.assertNotIn("safeLocalStorageGet(DUAL_AGENT_KEY", state_source)

    def test_stable_chat_answer_shows_only_answer_by_default(self) -> None:
        source = (ROOT / "web_client" / "components" / "message.js").read_text(encoding="utf-8")
        match = re.search(r"export function chatAnswerMessage\(.*?\n}\n", source, re.S)

        self.assertIsNotNone(match)
        chat_answer_source = match.group(0)
        self.assertIn("mainAnswer(data, fallback)", chat_answer_source)
        self.assertIn("shouldShowChatDiagnostics(data)", chat_answer_source)
        self.assertNotIn('const details = [answerSourceDetails(data), taskStatusDetails(data)].join("");', chat_answer_source)
        self.assertNotIn("Raw JSON", chat_answer_source)
        self.assertNotIn("Workspace State", chat_answer_source)

    def test_stable_chat_can_show_compact_answer_source_badge_when_diagnostics_are_enabled(self) -> None:
        source = (ROOT / "web_client" / "components" / "message.js").read_text(encoding="utf-8")
        chat_answer_source = source.split("export function dualAgentMessage", 1)[0]

        self.assertIn("answerSourceBadge", chat_answer_source)
        self.assertIn("回答来源", chat_answer_source)
        self.assertIn("answer_source", chat_answer_source)
        self.assertIn("llm_output_used", chat_answer_source)
        self.assertIn("show_diagnostics", chat_answer_source)
        self.assertNotIn('jsonDetails("Raw JSON"', chat_answer_source)

    def test_chat_input_is_chinese_first_and_focus_is_restored_after_rerender(self) -> None:
        source = (ROOT / "web_client" / "views" / "chat.js").read_text(encoding="utf-8")

        self.assertIn('lang="zh-CN"', source)
        self.assertIn("focusComposer", source)
        self.assertIn("focusInput", source)

    def test_api_contract_preserves_legacy_and_coordinator_paths(self) -> None:
        api_js = (ROOT / "web_client" / "api.js").read_text(encoding="utf-8")
        electron = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")

        self.assertIn('apiPost("/research-os/agent/chat"', api_js)
        self.assertIn('apiPost("/api/agents/coordinator/run"', api_js)
        self.assertIn("conversation_id: conversationId", api_js)
        self.assertIn('replace(/^\\/api\\/backend/, "")', electron)

    def test_electron_proxy_preserves_post_body(self) -> None:
        electron = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")

        self.assertIn('request.on("data"', electron)
        self.assertIn('"Content-Length": body.length', electron)
        self.assertIn("proxy.write(body)", electron)
        self.assertNotIn("request.pipe(proxy)", electron)


if __name__ == "__main__":
    unittest.main()
