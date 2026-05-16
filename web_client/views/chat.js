import { DEFAULT_PROJECT_ID, runCoordinator, runProductDemoFlow, sendLegacyChat } from "../api.js";
import { appState, setConversationId, setConversationProjectId, setDualAgentEnabled, setLastRunResult, setSessionId } from "../state.js";
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

function resolveChatProjectId() {
  const projectId = appState.activeProjectId || appState.activeProject?.id || appState.activeProject?.project_id || "";
  if (projectId) return projectId;
  return DEFAULT_PROJECT_ID;
}

function projectLabel(project) {
  if (!appState.activeProjectId && !project) return `默认项目 ${DEFAULT_PROJECT_ID}`;
  return project?.display_name || project?.title || project?.name || "未命名项目";
}

function currentChatSessionIds(projectId) {
  if (appState.conversationProjectId !== projectId) {
    return { conversationId: "", sessionId: "" };
  }
  return { conversationId: appState.conversationId, sessionId: appState.sessionId };
}

function rememberChatSession(projectId, data) {
  setConversationProjectId(projectId);
  if (data?.conversation_id) setConversationId(data.conversation_id);
  if (data?.session_id) setSessionId(data.session_id);
  if (data?.session_id && !data?.conversation_id) setConversationId(data.session_id);
}

async function sendStableChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  const { conversationId, sessionId } = currentChatSessionIds(activeProjectId);
  const legacy = await sendLegacyChat(prompt, activeProjectId, conversationId, sessionId);
  if (legacy.ok) {
    rememberChatSession(activeProjectId, legacy.data);
    setLastRunResult(legacy.data);
    addMessage({ role: "assistant", type: "answer", data: legacy.data, fallback: "稳定聊天暂时没有返回回答。" });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  addMessage({
    role: "assistant",
    type: "plain",
    body: `后端连接失败：${legacy.error || "稳定聊天暂时不可用。"}`,
  });
  return false;
}

async function sendExperimentalChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  if (!appState.dualAgentEnabled) return sendStableChat(prompt);
  const { conversationId, sessionId } = currentChatSessionIds(activeProjectId);
  const coordinator = await runCoordinator(prompt, activeProjectId, conversationId, sessionId);
  if (coordinator.ok) {
    setLastRunResult(coordinator.data);
    rememberChatSession(activeProjectId, coordinator.data);
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
  const legacy = await sendLegacyChat(prompt, activeProjectId, conversationId, sessionId);
  if (legacy.ok) {
    rememberChatSession(activeProjectId, legacy.data);
    setLastRunResult({ ...legacy.data, mode: "legacy_after_coordinator_error", coordinator_error: coordinator.error });
    addMessage({ role: "assistant", type: "answer", data: legacy.data, fallback: "稳定聊天暂时没有返回回答。" });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  addMessage({
    role: "assistant",
    type: "plain",
    body: `后端连接失败：${legacy.error || coordinator.error || "暂时无法连接双 Agent 或稳定聊天。"}`,
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
  const result = await runProductDemoFlow(resolveChatProjectId());
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
            ${badge(projectLabel(appState.activeProject))}
            ${badge(appState.dualAgentEnabled ? "双 Agent 实验模式" : "稳定聊天", appState.dualAgentEnabled ? "warning" : "success")}
          </div>
          ${appState.dualAgentEnabled ? `<p class="muted">实验模式：可能返回任务执行结果或结构化任务信息。</p>` : ""}
          <div class="inline-actions">
            <label class="check-row" title="仅在需要结构化研究任务时使用协调器。">
              <input type="checkbox" id="experimentalModeToggle"${appState.dualAgentEnabled ? " checked" : ""}>
              双 Agent 实验模式
            </label>
            <button class="button secondary" type="button" id="demoButton" title="demo_only：只读取后端演示流，不触发真实执行链路。">演示 demo_only</button>
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
