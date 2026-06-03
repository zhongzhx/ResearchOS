from pathlib import Path
import json
import re
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_CLIENT = ROOT / "web_client"
STATE_JS = WEB_CLIENT / "state.js"
CHAT_JS = WEB_CLIENT / "views" / "chat.js"
API_JS = WEB_CLIENT / "api.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


class ChatHistoryPersistenceTests(unittest.TestCase):
    def test_chat_without_project_shows_create_project_guide(self) -> None:
        source = read(CHAT_JS)

        self.assertIn("创建一个项目，开始保存你的研究对话和资料。", source)
        self.assertIn("newProjectFromChat", source)
        self.assertIn("hasActiveProject()", source)

    def test_state_defines_project_scoped_conversation_storage(self) -> None:
        source = read(STATE_JS)

        self.assertIn('CHAT_HISTORY_KEY = "researchos.chatHistory.v1"', source)
        self.assertIn("activeConversationId", source)
        self.assertIn("conversationsByProject", source)
        self.assertIn("lastConversationByProject", source)
        self.assertIn("loadChatMessages(projectId, conversationId)", source)
        self.assertIn("saveChatMessage(message)", source)
        self.assertIn("deleteConversation(projectId, conversationId)", source)
        self.assertIn("renameConversation(projectId, conversationId, title)", source)
        self.assertIn("archiveConversation(projectId, conversationId)", source)

    def test_save_and_reload_messages_by_project_and_conversation(self) -> None:
        result = run_node(
            f"""
            const store = {{}};
            globalThis.localStorage = {{
              getItem: (key) => Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null,
              setItem: (key, value) => {{ store[key] = String(value); }},
              removeItem: (key) => {{ delete store[key]; }},
            }};
            const state = await import({STATE_JS.as_uri()!r});
            const first = state.startNewConversation("project-a");
            state.saveChatMessage({{ project_id: "project-a", conversation_id: first, role: "user", content: "alpha question", created_at: "2026-01-01T00:00:00.000Z" }});
            state.saveChatMessage({{ project_id: "project-a", conversation_id: first, role: "assistant", content: "alpha answer", created_at: "2026-01-01T00:00:01.000Z" }});
            const second = state.startNewConversation("project-a");
            state.saveChatMessage({{ project_id: "project-a", conversation_id: second, role: "user", content: "second question", created_at: "2026-01-01T00:00:02.000Z" }});
            const beta = state.startNewConversation("project-b");
            state.saveChatMessage({{ project_id: "project-b", conversation_id: beta, role: "user", content: "beta question", created_at: "2026-01-01T00:00:03.000Z" }});
            process.stdout.write(JSON.stringify({{
              first,
              second,
              projectAFirst: state.loadChatMessages("project-a", first),
              projectASecond: state.loadChatMessages("project-a", second),
              projectBWithAConversation: state.loadChatMessages("project-b", first),
              projectB: state.loadChatMessages("project-b", beta),
              projectAConversations: state.listConversations("project-a"),
              projectBConversations: state.listConversations("project-b"),
              lastA: state.lastConversationForProject("project-a"),
              lastB: state.lastConversationForProject("project-b"),
              storageKeys: Object.keys(store),
            }}));
            """
        )

        self.assertNotEqual(result["first"], result["second"])
        self.assertEqual([item["content"] for item in result["projectAFirst"]], ["alpha question", "alpha answer"])
        self.assertEqual([item["content"] for item in result["projectASecond"]], ["second question"])
        self.assertEqual(result["projectBWithAConversation"], [])
        self.assertEqual([item["content"] for item in result["projectB"]], ["beta question"])
        self.assertEqual(len(result["projectAConversations"]), 2)
        self.assertEqual(len(result["projectBConversations"]), 1)
        self.assertEqual(result["lastA"], result["second"])
        self.assertEqual(result["lastB"], result["projectBConversations"][0]["id"])
        self.assertIn("researchos.chatHistory.v1", result["storageKeys"])

    def test_delete_conversation_removes_messages_and_selects_remaining_project_chat(self) -> None:
        result = run_node(
            f"""
            const store = {{}};
            globalThis.localStorage = {{
              getItem: (key) => Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null,
              setItem: (key, value) => {{ store[key] = String(value); }},
              removeItem: (key) => {{ delete store[key]; }},
            }};
            const state = await import({STATE_JS.as_uri()!r});
            const first = state.startNewConversation("project-a");
            state.saveChatMessage({{ project_id: "project-a", conversation_id: first, role: "user", content: "keep this", created_at: "2026-01-01T00:00:00.000Z" }});
            const second = state.startNewConversation("project-a");
            state.saveChatMessage({{ project_id: "project-a", conversation_id: second, role: "user", content: "delete this", created_at: "2026-01-01T00:00:01.000Z" }});
            const deleted = state.deleteConversation("project-a", second);
            const persisted = JSON.parse(store["researchos.chatHistory.v1"]);
            process.stdout.write(JSON.stringify({{
              deleted,
              first,
              second,
              activeConversationId: state.appState.activeConversationId,
              lastA: state.lastConversationForProject("project-a"),
              conversations: state.listConversations("project-a"),
              firstMessages: state.loadChatMessages("project-a", first),
              secondMessages: state.loadChatMessages("project-a", second),
              persistedProject: persisted.projects["project-a"],
            }}));
            """
        )

        self.assertTrue(result["deleted"])
        self.assertEqual(result["activeConversationId"], result["first"])
        self.assertEqual(result["lastA"], result["first"])
        self.assertEqual([item["id"] for item in result["conversations"]], [result["first"]])
        self.assertEqual([item["content"] for item in result["firstMessages"]], ["keep this"])
        self.assertEqual(result["secondMessages"], [])
        self.assertNotIn(result["second"], result["persistedProject"]["messages"])

    def test_rename_and_archive_conversation_keep_history_private_to_project(self) -> None:
        result = run_node(
            f"""
            const store = {{}};
            globalThis.localStorage = {{
              getItem: (key) => Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null,
              setItem: (key, value) => {{ store[key] = String(value); }},
              removeItem: (key) => {{ delete store[key]; }},
            }};
            const state = await import({STATE_JS.as_uri()!r});
            const first = state.startNewConversation("project-a");
            state.saveChatMessage({{ project_id: "project-a", conversation_id: first, role: "user", content: "alpha", created_at: "2026-01-01T00:00:00.000Z" }});
            const second = state.startNewConversation("project-a");
            state.renameConversation("project-a", first, "实验方案讨论");
            const archived = state.archiveConversation("project-a", second);
            process.stdout.write(JSON.stringify({{
              archived,
              visible: state.listConversations("project-a"),
              archivedVisible: state.listConversations("project-a", {{ includeArchived: true }}),
              firstMessages: state.loadChatMessages("project-a", first),
              secondMessages: state.loadChatMessages("project-a", second),
              lastA: state.lastConversationForProject("project-a"),
            }}));
            """
        )

        self.assertTrue(result["archived"])
        self.assertEqual([item["id"] for item in result["visible"]], [result["firstMessages"][0]["conversation_id"]])
        self.assertEqual(result["visible"][0]["title"], "实验方案讨论")
        self.assertEqual(len(result["archivedVisible"]), 2)
        self.assertEqual(result["secondMessages"], [])
        self.assertEqual(result["lastA"], result["firstMessages"][0]["conversation_id"])

    def test_reopening_client_restores_project_conversation_from_local_cache(self) -> None:
        result = run_node(
            f"""
            const store = {{
              "researchos.activeProjectId": "project-cache",
              "researchos.chatHistory.v1": JSON.stringify({{
                projects: {{
                  "project-cache": {{
                    conversations: [{{ id: "conversation-cache", title: "Cached thread", created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:01.000Z" }}],
                    messages: {{
                      "conversation-cache": [
                        {{ project_id: "project-cache", conversation_id: "conversation-cache", role: "user", content: "cached question", created_at: "2026-01-01T00:00:00.000Z" }},
                        {{ project_id: "project-cache", conversation_id: "conversation-cache", role: "assistant", content: "cached answer", created_at: "2026-01-01T00:00:01.000Z" }}
                      ]
                    }},
                    lastConversationId: "conversation-cache"
                  }}
                }}
              }})
            }};
            globalThis.localStorage = {{
              getItem: (key) => Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null,
              setItem: (key, value) => {{ store[key] = String(value); }},
              removeItem: (key) => {{ delete store[key]; }},
            }};
            const state = await import({STATE_JS.as_uri()!r});
            state.setProjects([{{ id: "project-cache", display_name: "Cache Project", status: "active" }}]);
            process.stdout.write(JSON.stringify({{
              activeConversationId: state.appState.activeConversationId,
              last: state.lastConversationForProject("project-cache"),
              conversations: state.listConversations("project-cache"),
              messages: state.loadChatMessages("project-cache", "conversation-cache"),
            }}));
            """
        )

        self.assertEqual(result["activeConversationId"], "conversation-cache")
        self.assertEqual(result["last"], "conversation-cache")
        self.assertEqual([item["title"] for item in result["conversations"]], ["Cached thread"])
        self.assertEqual([item["content"] for item in result["messages"]], ["cached question", "cached answer"])

    def test_chat_view_uses_history_instead_of_module_level_reset(self) -> None:
        source = read(CHAT_JS)

        self.assertNotIn("let messages = [", source)
        self.assertIn("loadChatMessages(activeProjectId, conversationId)", source)
        self.assertIn("saveChatMessage({", source)
        self.assertIn("startNewConversation(activeProjectId)", source)
        self.assertIn("listConversations(activeProjectId)", source)
        self.assertIn("deleteConversation(activeProjectId", source)
        self.assertIn("renameConversation(activeProjectId", source)
        self.assertIn("archiveConversation(activeProjectId", source)
        self.assertIn("data-conversation-menu", source)
        self.assertNotIn("data-delete-conversation-id", source)

    def test_chat_view_preserves_draft_and_reloads_messages_per_active_conversation(self) -> None:
        source = read(CHAT_JS)

        self.assertIn("rememberComposerDraft(activeProjectId, previousConversationId, currentDraft)", source)
        self.assertIn("preserveComposer = true", source)
        self.assertIn("renderChatView({ root, focusInput: true, preserveComposer: false })", source)
        self.assertIn("composerDraft(activeProjectId, conversationId)", source)
        self.assertIn("loadedConversationId === conversationId", source)
        self.assertIn("loadedProjectId === activeProjectId", source)

    def test_default_chat_still_uses_legacy_backend_route(self) -> None:
        chat = read(CHAT_JS)
        api = read(API_JS)
        send_legacy = re.search(r"export const sendLegacyChat = .*?\n};", api, re.S)
        self.assertIsNotNone(send_legacy)

        self.assertIn("sendLegacyChat(prompt, activeProjectId, conversationId, sessionId)", chat)
        self.assertIn('apiPost("/research-os/agent/chat"', api)
        self.assertIn("const safeProjectId = requireProjectId(projectId)", send_legacy.group(0))
        self.assertIn("project_id: safeProjectId", send_legacy.group(0))


if __name__ == "__main__":
    unittest.main()
