from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
API_JS = ROOT / "web_client" / "api.js"
CHAT_JS = ROOT / "web_client" / "views" / "chat.js"
LIBRARY_JS = ROOT / "web_client" / "views" / "library.js"
MESSAGE_JS = ROOT / "web_client" / "components" / "message.js"
API_ALIGNMENT = ROOT / "API_ALIGNMENT.md"


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
        import {{ chatAnswerMessage }} from {MESSAGE_JS.as_uri()!r};
        process.stdout.write(chatAnswerMessage({payload}, "fallback"));
        """
    )


class ChatRealContractTests(unittest.TestCase):
    def test_renderer_displays_answer_content_message_and_nested_answers(self) -> None:
        self.assertIn("你好，我是 AURA Research。", render_chat_answer('{ ok: true, answer: "你好，我是 AURA Research。" }'))
        self.assertIn("正常 content 回复", render_chat_answer('{ ok: true, content: "正常 content 回复" }'))
        self.assertIn("正常 message 回复", render_chat_answer('{ ok: true, message: "正常 message 回复" }'))
        self.assertIn("nested result answer", render_chat_answer('{ ok: true, result: { answer: "nested result answer" } }'))
        self.assertIn("nested data answer", render_chat_answer('{ ok: true, data: { answer: "nested data answer" } }'))

    def test_renderer_hides_internal_task_handoff_but_not_explanations(self) -> None:
        hidden = render_chat_answer('{ ok: true, answer: "Research Task Handoff\\nTaskSpec: task_123\\nExecutionResult: success\\nMemory: internal" }')
        self.assertIn("该响应来自任务执行链路，已隐藏内部交接内容。请在实验模式或任务页查看详情。", hidden)
        self.assertNotIn("task_123", hidden)
        self.assertNotIn("ExecutionResult: success", hidden)

        explanation = render_chat_answer('{ ok: true, answer: "TaskSpec 是任务规格，用来描述目标、输入和成功标准。" }')
        self.assertIn("TaskSpec 是任务规格", explanation)
        self.assertNotIn("已隐藏内部交接内容", explanation)

    def test_api_payload_contracts_and_product_demo_methods(self) -> None:
        output = run_node(
            f"""
            globalThis.window = {{ location: {{ protocol: "http:" }} }};
            const calls = [];
            globalThis.fetch = async (url, options) => {{
              calls.push({{ url, method: options.method, body: options.body ? JSON.parse(options.body) : null }});
              return {{ ok: true, status: 200, text: async () => JSON.stringify({{ ok: true, answer: "ok" }}) }};
            }};
            const api = await import({API_JS.as_uri()!r});
            await api.sendLegacyChat("你好", "", "conversation-1", "session-1");
            await api.runCoordinator("实验任务", "project-1", "conversation-2", "session-2");
            await api.runProductDemoFlow("project-3");
            const productRun = await api.runProductFeature("literature_harvest_workflow", {{ project_id: "project-4" }});
            process.stdout.write(JSON.stringify({{ calls, productRun }}));
            """
        )

        import json

        result = json.loads(output)
        calls = result["calls"]
        self.assertEqual(calls[0]["method"], "POST")
        self.assertTrue(calls[0]["url"].endswith("/research-os/agent/chat"))
        self.assertEqual(calls[0]["body"]["message"], "你好")
        self.assertEqual(calls[0]["body"]["project_id"], "default")
        self.assertEqual(calls[0]["body"]["conversation_id"], "conversation-1")
        self.assertEqual(calls[0]["body"]["session_id"], "session-1")

        self.assertEqual(calls[1]["method"], "POST")
        self.assertTrue(calls[1]["url"].endswith("/api/agents/coordinator/run"))
        self.assertEqual(calls[1]["body"]["user_query"], "实验任务")
        self.assertEqual(calls[1]["body"]["project_id"], "project-1")
        self.assertEqual(calls[1]["body"]["conversation_id"], "conversation-2")
        self.assertEqual(calls[1]["body"]["session_id"], "session-2")

        self.assertEqual(calls[2]["method"], "GET")
        self.assertIn("/api/demo/product-flow?project_id=project-3", calls[2]["url"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["productRun"]["data"]["status"], "not_connected")

    def test_default_conversation_ids_are_scoped_by_project(self) -> None:
        output = run_node(
            f"""
            globalThis.window = {{ location: {{ protocol: "http:" }} }};
            const calls = [];
            globalThis.fetch = async (url, options) => {{
              calls.push({{ url, method: options.method, body: options.body ? JSON.parse(options.body) : null }});
              return {{ ok: true, status: 200, text: async () => JSON.stringify({{ ok: true, answer: "ok" }}) }};
            }};
            const api = await import({API_JS.as_uri()!r});
            await api.sendLegacyChat("你好", "project-a", "", "");
            await api.sendLegacyChat("你好", "project-b", "", "");
            process.stdout.write(JSON.stringify(calls));
            """
        )
        import json

        calls = json.loads(output)
        self.assertNotEqual(calls[0]["body"]["conversation_id"], calls[1]["body"]["conversation_id"])
        self.assertIn("project-a", calls[0]["body"]["conversation_id"])
        self.assertIn("project-b", calls[1]["body"]["conversation_id"])

    def test_default_chat_ui_does_not_call_coordinator_or_product_run(self) -> None:
        chat = read(CHAT_JS)
        stable_block = chat.split("async function sendStableChat", 1)[1].split("async function sendExperimentalChat", 1)[0]
        submit_block = chat.split("async function submitPrompt", 1)[1].split("async function runDemo", 1)[0]

        self.assertIn("sendLegacyChat(prompt", stable_block)
        self.assertNotIn("runCoordinator", stable_block)
        self.assertIn("if (appState.dualAgentEnabled)", submit_block)
        self.assertIn("await sendStableChat(prompt)", submit_block)
        self.assertNotIn("runProductFeature(", chat + read(LIBRARY_JS))
        self.assertNotIn("/api/demo/product-flow/run", read(API_JS) + chat)
        self.assertNotIn("/api/product/features/${encodeURIComponent(featureId)}/run", read(API_JS))

    def test_default_chat_send_hello_calls_only_legacy_chat_and_displays_answer(self) -> None:
        output = run_node(
            f"""
            globalThis.requestAnimationFrame = (callback) => callback();
            globalThis.CustomEvent = class CustomEvent {{ constructor(name) {{ this.type = name; }} }};
            globalThis.window = {{
              location: {{ protocol: "http:" }},
              dispatchEvent: () => undefined,
            }};
            class FakeElement {{
              constructor(id = "") {{
                this.id = id;
                this.value = "";
                this.checked = false;
                this.dataset = {{}};
                this.listeners = {{}};
                this.scrollTop = 0;
                this.scrollHeight = 0;
              }}
              addEventListener(type, listener) {{
                this.listeners[type] = this.listeners[type] || [];
                this.listeners[type].push(listener);
              }}
              focus() {{}}
              async click() {{
                for (const listener of this.listeners.click || []) {{
                  await listener({{ target: this }});
                }}
              }}
            }}
            class FakeRoot {{
              constructor() {{
                this.elements = {{}};
                this.html = "";
              }}
              set innerHTML(value) {{
                this.html = value;
                this.elements.chatLog = new FakeElement("chatLog");
                this.elements.chatInput = new FakeElement("chatInput");
                this.elements.sendButton = new FakeElement("sendButton");
                this.elements.demoButton = new FakeElement("demoButton");
                this.elements.experimentalModeToggle = new FakeElement("experimentalModeToggle");
              }}
              get innerHTML() {{ return this.html; }}
              querySelector(selector) {{
                if (selector.startsWith("#")) return this.elements[selector.slice(1)];
                return null;
              }}
              querySelectorAll(selector) {{ return []; }}
            }}
            const calls = [];
            globalThis.fetch = async (url, options) => {{
              calls.push({{ url, method: options.method, body: options.body ? JSON.parse(options.body) : null }});
              return {{
                ok: true,
                status: 200,
                text: async () => JSON.stringify({{
                  ok: true,
                  answer: "你好，我是 AURA Research。",
                  conversation_id: "conversation-ui",
                  session_id: "session-ui",
                }}),
              }};
            }};
            const {{ appState }} = await import({(ROOT / "web_client" / "state.js").as_uri()!r});
            appState.activeProjectId = "";
            appState.activeProject = null;
            appState.dualAgentEnabled = false;
            appState.conversationId = "";
            appState.sessionId = "";
            const {{ renderChatView }} = await import({CHAT_JS.as_uri()!r});
            const root = new FakeRoot();
            await renderChatView({{ root }});
            root.querySelector("#chatInput").value = "你好";
            await root.querySelector("#sendButton").click();
            process.stdout.write(JSON.stringify({{ calls, html: root.innerHTML }}));
            """
        )
        import json

        result = json.loads(output)
        self.assertEqual(len(result["calls"]), 1)
        self.assertTrue(result["calls"][0]["url"].endswith("/research-os/agent/chat"))
        self.assertEqual(result["calls"][0]["method"], "POST")
        self.assertEqual(result["calls"][0]["body"]["message"], "你好")
        self.assertEqual(result["calls"][0]["body"]["project_id"], "default")
        self.assertIn("你好，我是 AURA Research。", result["html"])
        self.assertNotIn("/api/agents/coordinator/run", result["calls"][0]["url"])

    def test_api_alignment_matches_product_demo_contract(self) -> None:
        api = read(API_JS)
        doc = read(API_ALIGNMENT)

        self.assertIn('runProductDemoFlow = (projectId) => apiGet(withProject("/api/demo/product-flow"', api)
        self.assertIn("runProductFeature = (featureId", api)
        self.assertIn("notConnected(featureId", api)
        self.assertIn("GET `/api/demo/product-flow`", doc)
        self.assertIn("returns local `not_connected` response", doc)
        self.assertNotIn('apiPost("/api/demo/product-flow/run"', api)


if __name__ == "__main__":
    unittest.main()
