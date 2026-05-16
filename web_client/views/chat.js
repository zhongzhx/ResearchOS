import { runCoordinator, runProductDemoFlow, sendLegacyChat } from "../api.js";
import { appState, setConversationId, setDualAgentEnabled, setLastRunResult } from "../state.js";
import { badge, escapeHtml } from "../components/cards.js";
import { chatAnswerMessage, dualAgentMessage, plainMessage } from "../components/message.js";

const chips = ["你好", "你可以为我做什么", "介绍一下当前项目", "收集文献", "分析数据", "设计实验", "生成报告"];
let messages = [
  {
    role: "assistant",
    type: "plain",
    body: "稳定聊天已就绪。可以直接问 AURA 普通问题；需要结构化研究任务时，再手动开启双 Agent 实验模式。",
  },
];
let isSending = false;

function renderMessages() {
  return messages
    .map((message) => {
      if (message.type === "dual") return dualAgentMessage(message.data);
      if (message.type === "answer") return chatAnswerMessage(message.data, message.fallback);
      return plainMessage(message.role, message.body);
    })
    .join("");
}

function addMessage(message) {
  messages = [...messages, message].slice(-40);
}

function canShowDualResult(result) {
  if (result?.data?.mode === "mvp_chat_fallback") return false;
  return Boolean(result?.data?.task_spec || result?.data?.execution_result || result?.data?.details);
}

function focusComposer(root) {
  const input = root.querySelector("#chatInput");
  if (!input) return;
  requestAnimationFrame(() => input.focus({ preventScroll: true }));
}

async function sendStableChat(prompt) {
  const legacy = await sendLegacyChat(prompt, appState.activeProjectId, appState.conversationId);
  if (legacy.ok) {
    if (legacy.data?.conversation_id) setConversationId(legacy.data.conversation_id);
    setLastRunResult(legacy.data);
    addMessage({ role: "assistant", type: "answer", data: legacy.data, fallback: "稳定聊天暂时没有返回回答。" });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  addMessage({
    role: "assistant",
    type: "plain",
    body: `稳定聊天暂时不可用。${legacy.error || "后端不可用。"}`,
  });
  return false;
}

async function sendExperimentalChat(prompt) {
  const coordinator = await runCoordinator(prompt, appState.activeProjectId, appState.conversationId);
  if (coordinator.ok) {
    setLastRunResult(coordinator.data);
    if (coordinator.data?.conversation_id) setConversationId(coordinator.data.conversation_id);
    if (coordinator.data?.mode === "mvp_chat_fallback") {
      addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "稳定聊天暂时没有返回回答。" });
    } else if (canShowDualResult(coordinator)) {
      addMessage({ role: "assistant", type: "dual", data: coordinator.data });
    } else {
      addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "双 Agent 暂时没有返回回答。" });
    }
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  const legacy = await sendLegacyChat(prompt, appState.activeProjectId, appState.conversationId);
  if (legacy.ok) {
    if (legacy.data?.conversation_id) setConversationId(legacy.data.conversation_id);
    setLastRunResult({ ...legacy.data, mode: "legacy_after_coordinator_error", coordinator_error: coordinator.error });
    addMessage({ role: "assistant", type: "answer", data: legacy.data, fallback: "稳定聊天暂时没有返回回答。" });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  addMessage({
    role: "assistant",
    type: "plain",
    body: `暂时无法连接双 Agent 或稳定聊天。${legacy.error || coordinator.error || "后端不可用。"}`,
  });
  return false;
}

async function submitPrompt(root, prompt) {
  if (!prompt || isSending) return;
  isSending = true;
  addMessage({ role: "user", type: "plain", body: prompt });
  renderChatView({ root, focusInput: true });

  if (appState.dualAgentEnabled) {
    await sendExperimentalChat(prompt);
  } else {
    await sendStableChat(prompt);
  }
  isSending = false;
  renderChatView({ root, focusInput: true });
}

async function runDemo(root) {
  if (isSending) return;
  isSending = true;
  addMessage({ role: "user", type: "plain", body: "运行双 Agent 演示流程。" });
  renderChatView({ root, focusInput: true });
  const result = await runProductDemoFlow(appState.activeProjectId);
  if (result.ok || canShowDualResult(result)) {
    setLastRunResult(result.data);
    addMessage({ role: "assistant", type: "dual", data: result.data });
  } else {
    addMessage({ role: "assistant", type: "plain", body: `演示流程暂时不可用。${result.error || "产品演示接口可能未启用。"}` });
  }
  isSending = false;
  renderChatView({ root, focusInput: true });
}

export async function renderChatView({ root, focusInput = false }) {
  root.innerHTML = `<section class="chat-page" data-home-chat>
    <div class="chat-log" id="chatLog">${renderMessages()}</div>
    <div class="composer-shell">
      <div class="composer">
        <div class="chip-row">${chips.map((chip) => `<button class="prompt-chip" type="button" data-chip="${escapeHtml(chip)}">${escapeHtml(chip)}</button>`).join("")}</div>
        <textarea id="chatInput" class="chat-input" lang="zh-CN" spellcheck="false" placeholder="向 AURA 提问，例如：你好、你可以为我做什么、介绍一下当前项目..."></textarea>
        <div class="composer-actions">
          <div class="badge-row">
            ${badge(appState.activeProject?.title || appState.activeProject?.name || "未选择项目")}
            ${badge(appState.dualAgentEnabled ? "双 Agent 实验模式" : "稳定聊天", appState.dualAgentEnabled ? "warning" : "success")}
          </div>
          <div class="inline-actions">
            <label class="check-row" title="仅在需要结构化研究任务时使用协调器。">
              <input type="checkbox" id="experimentalModeToggle"${appState.dualAgentEnabled ? " checked" : ""}>
              双 Agent 实验模式
            </label>
            <button class="button secondary" type="button" id="demoButton">演示</button>
            <button class="button primary" type="button" id="sendButton"${isSending ? " disabled" : ""}>${isSending ? "运行中" : "发送"}</button>
          </div>
        </div>
      </div>
    </div>
  </section>`;

  const log = root.querySelector("#chatLog");
  log.scrollTop = log.scrollHeight;
  const input = root.querySelector("#chatInput");
  root.querySelectorAll("[data-chip]").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.dataset.chip;
      input.focus();
    });
  });
  root.querySelector("#sendButton").addEventListener("click", () => submitPrompt(root, input.value.trim()));
  root.querySelector("#demoButton").addEventListener("click", () => runDemo(root));
  root.querySelector("#experimentalModeToggle").addEventListener("change", (event) => {
    setDualAgentEnabled(event.target.checked);
    renderChatView({ root, focusInput: true });
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitPrompt(root, input.value.trim());
    }
  });
  if (focusInput) focusComposer(root);
}
