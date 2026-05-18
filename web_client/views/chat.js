import { routeSkillQuery, runCoordinator, sendLegacyChat } from "../api.js";
import {
  appState,
  ensureActiveConversation,
  lastConversationForProject,
  listConversations,
  loadChatMessages,
  projectDisplayName,
  deleteConversation,
  saveChatMessage,
  setActiveConversationId,
  setConversationId,
  setConversationProjectId,
  setLastRunResult,
  setSessionId,
  startNewConversation,
} from "../state.js";
import { badge, escapeHtml } from "../components/cards.js";
import { chatAnswerMessage, dualAgentMessage, plainMessage } from "../components/message.js";

const chips = ["介绍一下当前项目", "帮我梳理今天的研究思路", "整理一份实验计划", "总结这段结果"];
let chatMessages = [];
let isSending = false;
const welcomeMessage = {
  role: "assistant",
  type: "plain",
  body: "你好，我是 AURA Research。你可以直接告诉我研究问题、实验现象或下一步想法。",
};

function renderMessages() {
  const visibleMessages = chatMessages.length ? chatMessages : [welcomeMessage];
  return visibleMessages
    .map((message) => {
      if (message.type === "dual") return dualAgentMessage(message.data);
      if (message.type === "answer") return chatAnswerMessage(message.data, message.fallback);
      return plainMessage(message.role, message.body);
    })
    .join("");
}

function messageContent(message) {
  if (message.type === "answer") return answerText(message.data, message.fallback);
  if (message.type === "dual") return answerText(message.data, "结构化研究任务已返回。");
  return message.body || message.content || "";
}

function addMessage(message, projectId = resolveChatProjectId(), conversationId = appState.activeConversationId) {
  chatMessages = [...chatMessages, message].slice(-40);
  if (projectId && conversationId) {
    saveChatMessage({
      role: message.role,
      content: messageContent(message),
      created_at: new Date().toISOString(),
      project_id: projectId,
      conversation_id: conversationId,
    });
  }
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

function hasActiveProject() {
  return Boolean(appState.activeProjectId && appState.activeProject);
}

function resolveChatProjectId() {
  const projectId = appState.activeProjectId || appState.activeProject?.id || appState.activeProject?.project_id || "";
  return projectId || "";
}

function projectLabel(project) {
  return projectDisplayName(project);
}

function currentChatSessionIds(projectId) {
  if (appState.activeConversationId && appState.conversationProjectId === projectId) {
    return { conversationId: appState.activeConversationId, sessionId: appState.sessionId || appState.activeConversationId };
  }
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

function answerText(data, fallback = "稳定聊天暂时没有返回回答。") {
  return data?.answer || data?.content || data?.message || data?.result?.answer || data?.data?.answer || fallback;
}

function looksLikeSkillRequest(prompt) {
  const text = String(prompt || "").toLowerCase();
  return [
    "search papers",
    "collect literature",
    "download papers",
    "analyze data",
    "build sop",
    "design experiment",
    "diagnose failure",
    "weekly report",
    "write report",
    "pipeline",
    "skill",
    "搜索文献",
    "检索文献",
    "采集文献",
    "下载文献",
    "分析数据",
    "生成 sop",
    "实验设计",
    "失败复盘",
    "周报",
    "调用技能",
    "调用skill",
  ].some((marker) => text.includes(marker));
}

function skillRoutePayload(result) {
  return result?.data || result || {};
}

function isRunnableSkillRoute(result) {
  const route = skillRoutePayload(result);
  const pipeline = route.pipeline || route.selected_pipeline || route.selected || {};
  const pipelineName = String(pipeline.pipeline_name || pipeline.intent || route.pipeline_name || route.intent || "").toLowerCase();
  const selectedSkill = pipeline.selected_skill || route.selected_skill || route.skill_id || route.skill_name;
  const requiredSkills = route.required_skills || route.execution_skills || route.skills || pipeline.required_skills || [];
  if (selectedSkill) return true;
  if (Array.isArray(requiredSkills) && requiredSkills.length) return true;
  return Boolean(pipelineName && !["chat", "general_chat", "ordinary_chat", "mvp_chat_fallback"].includes(pipelineName));
}

function storedMessageToView(message) {
  return {
    role: message.role === "user" ? "user" : "assistant",
    type: "plain",
    body: message.content || "",
  };
}

function loadActiveMessages() {
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) {
    chatMessages = [];
    return "";
  }
  const conversationId = appState.activeConversationId || lastConversationForProject(activeProjectId);
  if (!conversationId) {
    chatMessages = [];
    return "";
  }
  setActiveConversationId(activeProjectId, conversationId);
  chatMessages = loadChatMessages(activeProjectId, conversationId).map(storedMessageToView);
  return conversationId;
}

function renderConversationList(activeProjectId) {
  const conversations = listConversations(activeProjectId).slice(0, 10);
  const buttons = conversations
    .map(
      (conversation) =>
        `<span class="conversation-entry">
          <button class="conversation-item ${conversation.id === appState.activeConversationId ? "is-active" : ""}" type="button" data-conversation-id="${escapeHtml(conversation.id)}">${escapeHtml(conversation.title || "新对话")}</button>
          <button class="conversation-delete" type="button" data-delete-conversation-id="${escapeHtml(conversation.id)}" title="删除对话">删除</button>
        </span>`,
    )
    .join("");
  return `<div class="conversation-rail">
    <button class="button secondary small" type="button" id="newConversationButton">新对话</button>
    ${buttons}
  </div>`;
}

async function sendStableChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) return false;
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

async function sendCoordinatorChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) return false;
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
      addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "内部协调器暂时没有返回回答。" });
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
    body: `服务连接失败：${legacy.error || coordinator.error || "暂时无法连接内部协调器或稳定聊天。"}`,
  });
  return false;
}

async function sendSkillAwareChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId || !looksLikeSkillRequest(prompt)) return false;
  const { conversationId, sessionId } = currentChatSessionIds(activeProjectId);
  const route = await routeSkillQuery(prompt, activeProjectId);
  if (!route.ok || !isRunnableSkillRoute(route)) return false;
  const coordinator = await runCoordinator(prompt, activeProjectId, conversationId, sessionId);
  if (!coordinator.ok) return false;
  setLastRunResult(coordinator.data);
  rememberChatSession(activeProjectId, coordinator.data);
  if (coordinator.data?.mode === "mvp_chat_fallback") {
    addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "稳定聊天暂时没有返回回答。" });
  } else if (canShowDualResult(coordinator)) {
    addMessage({ role: "assistant", type: "dual", data: coordinator.data });
  } else {
    addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "已完成技能路由，但暂时没有返回可展示回答。" });
  }
  window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
  return true;
}

async function submitPrompt(root, prompt) {
  if (!prompt || isSending) return;
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) return;
  const conversationId = ensureActiveConversation(activeProjectId);
  isSending = true;
  addMessage({ role: "user", type: "plain", body: prompt }, activeProjectId, conversationId);
  renderChatView({ root, focusInput: true });

  if (await sendSkillAwareChat(prompt)) {
    // Skill-like requests can route directly from chat without requiring a manual mode switch.
  } else if (appState.dualAgentEnabled) {
    await sendCoordinatorChat(prompt);
  } else {
    await sendStableChat(prompt);
  }
  isSending = false;
  renderChatView({ root, focusInput: true });
}

export async function renderChatView({ root, focusInput = false }) {
  if (!hasActiveProject()) {
    chatMessages = [];
    root.innerHTML = `<section class="chat-page" data-home-chat>
      <div class="empty-state">
        <div>
          <strong>创建一个项目，开始保存你的研究对话和资料。</strong>
          <p>项目会保存聊天、资料和研究上下文。</p>
          <div class="inline-actions" style="justify-content: center; margin-top: 14px;">
            <button class="button primary" type="button" id="newProjectFromChat" data-view-target="projects">创建项目</button>
          </div>
        </div>
      </div>
    </section>`;
    return;
  }
  const activeProjectId = resolveChatProjectId();
  loadActiveMessages();
  root.innerHTML = `<section class="chat-page" data-home-chat>
    <header class="chat-hero">
      <div>
        <p class="eyebrow">${escapeHtml(projectLabel(appState.activeProject))}</p>
        <h1>和 AURA 讨论你的研究</h1>
        <p>把问题、文献线索、实验结果或下一步计划发给我。</p>
      </div>
      ${renderConversationList(activeProjectId)}
    </header>
    <div class="chat-log" id="chatLog">${renderMessages()}</div>
    <div class="composer-shell">
      <div class="composer">
        <div class="chip-row">${chips.map((chip) => `<button class="prompt-chip" type="button" data-chip="${escapeHtml(chip)}">${escapeHtml(chip)}</button>`).join("")}</div>
        <textarea id="chatInput" class="chat-input" lang="zh-CN" spellcheck="false" placeholder="输入你的研究问题"></textarea>
        <div class="composer-actions">
          <div class="badge-row">${badge(projectLabel(appState.activeProject))}</div>
          <div class="inline-actions">
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
  root.querySelector("#newConversationButton").addEventListener("click", () => {
    startNewConversation(activeProjectId);
    chatMessages = [];
    renderChatView({ root, focusInput: true });
  });
  root.querySelectorAll("[data-conversation-id]").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveConversationId(activeProjectId, button.dataset.conversationId);
      renderChatView({ root, focusInput: true });
    });
  });
  root.querySelectorAll("[data-delete-conversation-id]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const conversationId = button.dataset.deleteConversationId;
      if (!conversationId) return;
      if (!confirm("确定删除这段对话吗？")) return;
      deleteConversation(activeProjectId, conversationId);
      chatMessages = [];
      renderChatView({ root, focusInput: true });
    });
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitPrompt(root, input.value.trim());
    }
  });
  if (focusInput) focusComposer(root);
}
