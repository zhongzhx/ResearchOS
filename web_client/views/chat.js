import * as api from "../api.js";
import {
  appState,
  ensureActiveConversation,
  lastConversationForProject,
  listConversations,
  loadChatMessages,
  projectDisplayName,
  archiveConversation,
  deleteConversation,
  renameConversation,
  saveChatMessage,
  setActiveConversationId,
  setConversationId,
  setConversationProjectId,
  setLastRunResult,
  setSessionId,
  startNewConversation,
} from "../state.js";
import { badge, escapeHtml } from "../components/cards.js";
import { chatAnswerMessage, dualAgentMessage, plainMessage, workflowConfirmationMessage, workflowResultMessage } from "../components/message.js";
import { bindMascotFallbacks, renderMascot, renderMascotFeedback } from "../components/mascot.js";
import { bindWorkflowResultActions } from "../components/workflow_result.js";
import { detectWorkflowIntent } from "../workflow_intents.js";
import {
  buildWorkflowPlan,
  createWorkflowDraft,
  executeWorkflow,
  formatWorkflowResult,
  isWorkflowCancellation,
  isWorkflowConfirmation,
  saveWorkflowArtifacts,
  saveWorkflowHistory,
  updateWorkflowDraft,
  validateWorkflowParams,
  workflowHistoryRecord,
} from "../user_workflows.js";

const chips = [
  { label: "文献采集", prompt: "帮我下载文献构建知识库" },
  { label: "实验设计", prompt: "根据我的项目设计实验方案" },
  { label: "数据分析", prompt: "分析这个数据并给出下一步建议" },
  { label: "SOP 生成", prompt: "根据实验目标整理一份 SOP" },
  { label: "项目复盘", prompt: "帮我复盘当前项目进展和下一步重点" },
];
let chatMessages = [];
let isSending = false;
let activeFeedbackState = "";
let pendingWorkflow = null;
let loadedProjectId = "";
let loadedConversationId = "";
const composerDrafts = new Map();
const welcomeMessage = {
  role: "assistant",
  type: "plain",
  body: "",
  mascotState: "greeting",
};

function renderMessages() {
  const visibleMessages = chatMessages.length ? chatMessages : [welcomeMessage];
  return visibleMessages
    .map((message) => {
      if (message.type === "dual") return dualAgentMessage(message.data);
      if (message.type === "answer") return chatAnswerMessage(message.data, message.fallback);
      if (message.type === "workflow_confirm") return workflowConfirmationMessage(message.workflow);
      if (message.type === "workflow_result") return workflowResultMessage(message.result);
      return plainMessage(message.role, message.body, { mascotState: message.mascotState });
    })
    .join("");
}

function messageContent(message) {
  if (message.type === "answer") return answerText(message.data, message.fallback);
  if (message.type === "dual") return answerText(message.data, "结构化研究任务已返回。");
  if (message.type === "workflow_confirm") return `请确认任务：${message.workflow?.title || "科研任务"}`;
  if (message.type === "workflow_result") return message.result?.message || "任务状态已更新。";
  return message.body || message.content || "";
}

function addMessage(message, projectId = resolveChatProjectId(), conversationId = appState.activeConversationId) {
  chatMessages = [...chatMessages, message].slice(-40);
  loadedProjectId = projectId || loadedProjectId;
  loadedConversationId = conversationId || loadedConversationId;
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

function composerKey(projectId, conversationId) {
  return `${projectId || ""}::${conversationId || ""}`;
}

function rememberComposerDraft(projectId, conversationId, currentDraft) {
  if (!projectId || !conversationId) return;
  composerDrafts.set(composerKey(projectId, conversationId), String(currentDraft || ""));
}

function composerDraft(projectId, conversationId) {
  return composerDrafts.get(composerKey(projectId, conversationId)) || "";
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

function answerText(data, fallback = "我暂时没有返回回答。") {
  return data?.answer || data?.content || data?.message || data?.result?.answer || data?.data?.answer || fallback;
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
    loadedProjectId = "";
    loadedConversationId = "";
    return "";
  }
  const conversationId = appState.activeConversationId || lastConversationForProject(activeProjectId);
  if (!conversationId) {
    chatMessages = [];
    loadedProjectId = activeProjectId;
    loadedConversationId = "";
    return "";
  }
  if (
    loadedProjectId === activeProjectId &&
    loadedConversationId === conversationId &&
    appState.conversationProjectId === activeProjectId &&
    appState.activeConversationId === conversationId &&
    chatMessages.some((message) => String(message.type || "").startsWith("workflow_"))
  ) {
    return conversationId;
  }
  setActiveConversationId(activeProjectId, conversationId);
  chatMessages = loadChatMessages(activeProjectId, conversationId).map(storedMessageToView);
  loadedProjectId = activeProjectId;
  loadedConversationId = conversationId;
  return conversationId;
}

function renderConversationList(activeProjectId) {
  const conversations = listConversations(activeProjectId).slice(0, 10);
  const buttons = conversations
    .map(
      (conversation) =>
        `<div class="conversation-entry ${conversation.id === appState.activeConversationId ? "is-active" : ""}">
          <details class="conversation-menu">
            <summary title="编辑对话" data-conversation-menu>⋯</summary>
            <div class="conversation-menu-panel">
              <button type="button" data-rename-conversation-id="${escapeHtml(conversation.id)}">重命名</button>
              <button type="button" data-archive-conversation-id="${escapeHtml(conversation.id)}">归档</button>
              <button type="button" data-remove-conversation-id="${escapeHtml(conversation.id)}">删除</button>
            </div>
          </details>
          <button class="conversation-item" type="button" data-conversation-id="${escapeHtml(conversation.id)}">
            <span>${escapeHtml(conversation.title || "新对话")}</span>
            <small>${escapeHtml(new Date(conversation.updated_at || conversation.created_at || Date.now()).toLocaleDateString("zh-CN"))}</small>
          </button>
        </div>`,
    )
    .join("");
  return `<div class="conversation-rail">
    <div class="conversation-rail-header">
      <span>对话记录</span>
      <button class="button secondary small" type="button" id="newConversationButton">新对话</button>
    </div>
    <div class="conversation-list">${buttons || `<p class="conversation-empty">暂无对话</p>`}</div>
  </div>`;
}

async function sendStableChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) return false;
  const { conversationId, sessionId } = currentChatSessionIds(activeProjectId);
  const legacy = await api.sendLegacyChat(prompt, activeProjectId, conversationId, sessionId);
  if (legacy.ok) {
    rememberChatSession(activeProjectId, legacy.data);
    setLastRunResult(legacy.data);
    addMessage({ role: "assistant", type: "answer", data: legacy.data, fallback: "我暂时没有返回回答。" });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  addMessage({
    role: "assistant",
    type: "plain",
    body: "这里出了一点问题，我暂时无法回复。请稍后再试。",
    mascotState: "error",
  });
  return false;
}

async function sendCoordinatorChat(prompt) {
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) return false;
  if (!appState.dualAgentEnabled) return sendStableChat(prompt);
  const { conversationId, sessionId } = currentChatSessionIds(activeProjectId);
  const coordinator = await api.runCoordinator(prompt, activeProjectId, conversationId, sessionId);
  if (coordinator.ok) {
    setLastRunResult(coordinator.data);
    rememberChatSession(activeProjectId, coordinator.data);
    if (coordinator.data?.mode === "mvp_chat_fallback") {
      addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "我暂时没有返回回答。" });
    } else if (canShowDualResult(coordinator)) {
      addMessage({ role: "assistant", type: "dual", data: coordinator.data });
    } else {
      addMessage({ role: "assistant", type: "answer", data: coordinator.data, fallback: "我暂时没有返回回答。" });
    }
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  const legacy = await api.sendLegacyChat(prompt, activeProjectId, conversationId, sessionId);
  if (legacy.ok) {
    rememberChatSession(activeProjectId, legacy.data);
    setLastRunResult({ ...legacy.data, mode: "legacy_after_coordinator_error", coordinator_error: coordinator.error });
    addMessage({ role: "assistant", type: "answer", data: legacy.data, fallback: "我暂时没有返回回答。" });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    return true;
  }
  addMessage({
    role: "assistant",
    type: "plain",
    body: "这里出了一点问题，我暂时无法回复。请稍后再试。",
    mascotState: "error",
  });
  return false;
}

function makePendingWorkflow(detected, projectId) {
  const conversationId = projectId ? ensureActiveConversation(projectId) : "";
  const draft = createWorkflowDraft(detected.intent, detected.params || {}, { projectId, conversationId, source: "chat" });
  saveWorkflowHistory(projectId, workflowHistoryRecord(draft, { status: draft.status, result_summary: draft.next_step }));
  return draft;
}

function addWorkflowConfirmation(workflow) {
  addMessage({ role: "assistant", type: "workflow_confirm", workflow });
}

async function executePendingWorkflow(root) {
  if (!pendingWorkflow) return false;
  const activeProjectId = resolveChatProjectId();
  const { conversationId, sessionId } = currentChatSessionIds(activeProjectId);
  const workflow = { ...pendingWorkflow, status: "confirmed", linked_conversation_id: conversationId };
  pendingWorkflow = null;
  activeFeedbackState = "working";
  saveWorkflowHistory(activeProjectId, workflowHistoryRecord(workflow, { status: "running", result_summary: "任务已确认，正在执行。" }));
  addMessage({
    role: "assistant",
    type: "workflow_result",
    result: {
      status: "running",
      title: "已开始任务",
      message: "我已收到确认，正在提交任务。",
      steps: ["确认参数", "提交任务"],
    },
  });
  renderChatView({ root });
  const rawResult = await executeWorkflow(workflow, api, { projectId: activeProjectId, conversationId, sessionId });
  const result = formatWorkflowResult(rawResult, { developerMode: appState.developerMode });
  setLastRunResult(result);
  saveWorkflowHistory(activeProjectId, workflowHistoryRecord(workflow, result));
  saveWorkflowArtifacts(activeProjectId, workflow, result);
  addMessage({ role: "assistant", type: "workflow_result", result });
  window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
  return true;
}

async function handlePendingWorkflowReply(root, prompt) {
  if (!pendingWorkflow) return false;
  if (isWorkflowCancellation(prompt)) {
    pendingWorkflow = null;
    addMessage({ role: "assistant", type: "plain", body: "已取消这次任务。" });
    return true;
  }

  const updated = updateWorkflowDraft(pendingWorkflow, prompt);
  if (updated.status === "cancelled") {
    pendingWorkflow = null;
    addMessage({ role: "assistant", type: "plain", body: "已取消这次任务。" });
    return true;
  }
  if (updated.status === "confirmed" || (pendingWorkflow.status !== "needs_input" && isWorkflowConfirmation(prompt))) {
    pendingWorkflow = { ...updated, status: "confirmed" };
    await executePendingWorkflow(root);
    return true;
  }
  if (JSON.stringify(updated.params || {}) !== JSON.stringify(pendingWorkflow.params || {})) {
    pendingWorkflow = updated;
    const validation = validateWorkflowParams(pendingWorkflow.intent, pendingWorkflow.params);
    if (!validation.ok) {
      addMessage({ role: "assistant", type: "plain", body: validation.questions[0], mascotState: "need_more_info" });
      return true;
    }
    addWorkflowConfirmation(pendingWorkflow);
    return true;
  }

  addMessage({ role: "assistant", type: "plain", body: "请回复“开始”确认执行，或回复“取消”放弃这次任务。" });
  return true;
}

function handleWorkflowIntent(prompt) {
  const activeProjectId = resolveChatProjectId();
  const detected = detectWorkflowIntent(prompt);
  if (!detected) return false;
  pendingWorkflow = makePendingWorkflow(detected, activeProjectId);
  const validation = validateWorkflowParams(pendingWorkflow.intent, pendingWorkflow.params);
  if (!validation.ok) {
    pendingWorkflow.status = "needs_input";
    addMessage({ role: "assistant", type: "plain", body: validation.questions[0], mascotState: "need_more_info" });
    return true;
  }
  const plan = buildWorkflowPlan(pendingWorkflow.intent, pendingWorkflow.params, pendingWorkflow.context || {});
  pendingWorkflow = { ...pendingWorkflow, status: "pending_confirmation", current_step: plan.current_step, next_step: plan.next_step, plan, technical: appState.developerMode ? plan.technical : null };
  addWorkflowConfirmation(pendingWorkflow);
  return true;
}

async function submitPrompt(root, prompt) {
  if (!prompt || isSending) return;
  const activeProjectId = resolveChatProjectId();
  if (!activeProjectId) return;
  const conversationId = ensureActiveConversation(activeProjectId);
  isSending = true;
  activeFeedbackState = "thinking";
  rememberComposerDraft(activeProjectId, conversationId, "");
  addMessage({ role: "user", type: "plain", body: prompt }, activeProjectId, conversationId);
  renderChatView({ root, focusInput: true, preserveComposer: false });

  if (await handlePendingWorkflowReply(root, prompt)) {
    // Pending workflow replies can confirm, cancel, or update parameters without falling through to ordinary chat.
  } else if (handleWorkflowIntent(prompt)) {
    // Explicit user workflow requests create a confirmation card before anything runs.
  } else if (appState.dualAgentEnabled) {
    await sendCoordinatorChat(prompt);
  } else {
    await sendStableChat(prompt);
  }
  isSending = false;
  activeFeedbackState = "";
  renderChatView({ root, focusInput: true });
}

export async function renderChatView({ root, focusInput = false, preserveComposer = true }) {
  if (!hasActiveProject()) {
    chatMessages = [];
    root.innerHTML = `<section class="chat-page" data-home-chat>
      <div class="empty-state">
        <div>
          ${renderMascot("greeting", { size: "illustration" })}
          <strong>创建一个项目，开始保存你的研究对话和资料。</strong>
          <p>项目会保存聊天、资料和研究上下文。</p>
          <div class="inline-actions" style="justify-content: center; margin-top: 14px;">
            <button class="button primary" type="button" id="newProjectFromChat" data-view-target="projects">创建项目</button>
          </div>
        </div>
      </div>
    </section>`;
    bindMascotFallbacks(root);
    return;
  }
  const activeProjectId = resolveChatProjectId();
  const previousInput = root.querySelector("#chatInput");
  const previousConversationId = loadedConversationId || appState.activeConversationId || lastConversationForProject(activeProjectId);
  if (preserveComposer && previousInput && previousConversationId) {
    const currentDraft = previousInput.value;
    rememberComposerDraft(activeProjectId, previousConversationId, currentDraft);
  }
  const conversationId = loadActiveMessages();
  const isEmptyState = chatMessages.length === 0;
  const draft = composerDraft(activeProjectId, conversationId);
  root.innerHTML = `<section class="chat-page ${isEmptyState ? "is-empty" : "has-messages"}" data-home-chat>
    <header class="chat-hero">
      <div class="chat-stage">
        <h1>欢迎使用 Aura Research，有什么可以帮忙的？</h1>
      </div>
      <div class="chat-sidepanel">
        ${renderConversationList(activeProjectId)}
      </div>
    </header>
    <div class="chat-log" id="chatLog">${renderMessages()}${isSending ? renderMascotFeedback(activeFeedbackState || "thinking") : ""}</div>
    <div class="composer-shell">
      <div class="composer">
        <div class="chip-row">${chips
          .map(
            (chip) =>
              `<button class="prompt-chip" type="button" data-chip="${escapeHtml(chip.prompt)}">${escapeHtml(chip.label)}</button>`,
          )
          .join("")}</div>
        <textarea id="chatInput" class="chat-input" lang="zh-CN" spellcheck="false" placeholder="输入你的研究问题、关键词、实验现象或数据分析需求">${escapeHtml(draft)}</textarea>
        <div class="composer-actions">
          <div class="badge-row composer-meta">
            ${badge("当前项目", "muted")}
            ${badge(projectLabel(appState.activeProject))}
          </div>
          <div class="inline-actions">
            <button class="button primary" type="button" id="sendButton"${isSending ? " disabled" : ""}>${isSending ? "运行中" : "发送"}</button>
          </div>
        </div>
      </div>
    </div>
  </section>`;

  bindMascotFallbacks(root);
  const log = root.querySelector("#chatLog");
  log.scrollTop = log.scrollHeight;
  const input = root.querySelector("#chatInput");
  root.querySelectorAll("[data-chip]").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.dataset.chip;
      rememberComposerDraft(activeProjectId, conversationId, input.value);
      input.focus();
    });
  });
  root.querySelectorAll("[data-workflow-reply]").forEach((button) => {
    button.addEventListener("click", () => submitPrompt(root, button.dataset.workflowReply));
  });
  root.querySelectorAll("[data-workflow-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      input.placeholder = "例如：改成50篇、只要近五年、主题改成神经炎症天然产物";
      input.focus();
    });
  });
  root.querySelector("#sendButton").addEventListener("click", () => submitPrompt(root, input.value.trim()));
  root.querySelector("#newConversationButton").addEventListener("click", () => {
    startNewConversation(activeProjectId);
    chatMessages = [];
    loadedProjectId = activeProjectId;
    loadedConversationId = appState.activeConversationId;
    renderChatView({ root, focusInput: true });
  });
  root.querySelectorAll("[data-conversation-id]").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveConversationId(activeProjectId, button.dataset.conversationId);
      renderChatView({ root, focusInput: true });
    });
  });
  root.querySelectorAll("[data-rename-conversation-id]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const targetConversationId = button.dataset.renameConversationId;
      const title = prompt("新的对话名称");
      if (!targetConversationId || !title) return;
      renameConversation(activeProjectId, targetConversationId, title);
      renderChatView({ root, focusInput: true });
    });
  });
  root.querySelectorAll("[data-archive-conversation-id]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const targetConversationId = button.dataset.archiveConversationId;
      if (!targetConversationId) return;
      archiveConversation(activeProjectId, targetConversationId);
      chatMessages = [];
      renderChatView({ root, focusInput: true });
    });
  });
  root.querySelectorAll("[data-remove-conversation-id]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const targetConversationId = button.dataset.removeConversationId;
      if (!targetConversationId) return;
      if (!confirm("确定删除这段对话吗？")) return;
      deleteConversation(activeProjectId, targetConversationId);
      chatMessages = [];
      renderChatView({ root, focusInput: true });
    });
  });
  input.addEventListener("input", () => {
    rememberComposerDraft(activeProjectId, conversationId, input.value);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitPrompt(root, input.value.trim());
    }
  });
  const lastWorkflowResult = [...chatMessages].reverse().find((message) => message.type === "workflow_result")?.result;
  if (lastWorkflowResult?.artifacts?.length) {
    bindWorkflowResultActions(root, { projectId: activeProjectId, artifacts: lastWorkflowResult.artifacts });
  }
  if (focusInput) focusComposer(root);
}
