import { runCoordinator, runDualAgentDemo, sendLegacyChat } from "../api.js";
import { appState, setConversationId, setLastRunResult } from "../state.js";
import { badge, escapeHtml, text } from "../components/cards.js";
import { dualAgentMessage, plainMessage } from "../components/message.js";

const chips = ["Collect literature", "Analyze data", "Build SOP", "Review claims", "Generate report", "Diagnose failure"];
let messages = [
  {
    role: "assistant",
    type: "plain",
    body: "Ask AURA to collect literature, analyze data, design an experiment, or review your claims. Dual Agent will run first when the backend API is enabled.",
  },
];
let isSending = false;

function renderMessages() {
  return messages
    .map((message) => {
      if (message.type === "dual") return dualAgentMessage(message.data);
      return plainMessage(message.role, message.body);
    })
    .join("");
}

function addMessage(message) {
  messages = [...messages, message].slice(-40);
}

function canShowDualResult(result) {
  return Boolean(result?.data?.task_spec || result?.data?.execution_result || result?.data?.details);
}

async function submitPrompt(root, prompt) {
  if (!prompt || isSending) return;
  isSending = true;
  addMessage({ role: "user", type: "plain", body: prompt });
  renderChatView({ root });

  const coordinator = await runCoordinator(prompt, appState.activeProjectId);
  if (coordinator.ok || canShowDualResult(coordinator)) {
    setLastRunResult(coordinator.data);
    addMessage({ role: "assistant", type: "dual", data: coordinator.data });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
  } else {
    const legacy = await sendLegacyChat(prompt, appState.activeProjectId, appState.conversationId);
    if (legacy.ok) {
      if (legacy.data?.conversation_id) setConversationId(legacy.data.conversation_id);
      addMessage({
        role: "assistant",
        type: "plain",
        body: text(legacy.data?.answer || legacy.data?.summary || legacy.data?.message, "Legacy chat returned without a summary."),
      });
    } else {
      addMessage({
        role: "assistant",
        type: "plain",
        body: `I could not reach Dual Agent or legacy chat. ${legacy.error || coordinator.error || "Backend unavailable."}`,
      });
    }
  }
  isSending = false;
  renderChatView({ root });
}

async function runDemo(root) {
  if (isSending) return;
  isSending = true;
  addMessage({ role: "user", type: "plain", body: "Run the Dual Agent demo flow." });
  renderChatView({ root });
  const result = await runDualAgentDemo(appState.activeProjectId);
  if (result.ok || canShowDualResult(result)) {
    setLastRunResult(result.data);
    addMessage({ role: "assistant", type: "dual", data: result.data });
  } else {
    addMessage({ role: "assistant", type: "plain", body: `Demo flow is not available. ${result.error || "Dual Agent API may be disabled."}` });
  }
  isSending = false;
  renderChatView({ root });
}

export async function renderChatView({ root }) {
  root.innerHTML = `<section class="chat-page" data-home-chat>
    <div class="chat-log" id="chatLog">${renderMessages()}</div>
    <div class="composer-shell">
      <div class="composer">
        <div class="chip-row">${chips.map((chip) => `<button class="prompt-chip" type="button" data-chip="${escapeHtml(chip)}">${escapeHtml(chip)}</button>`).join("")}</div>
        <textarea id="chatInput" class="chat-input" placeholder="Ask AURA to collect literature, analyze data, design an experiment, or review your claims..."></textarea>
        <div class="composer-actions">
          <div class="badge-row">
            ${badge(appState.activeProject?.title || appState.activeProject?.name || "No project selected")}
            ${badge(appState.dualAgentEnabled ? "Dual Agent first" : "Legacy fallback ready", appState.dualAgentEnabled ? "success" : "warning")}
          </div>
          <div class="inline-actions">
            <button class="button secondary" type="button" id="demoButton">Demo</button>
            <button class="button primary" type="button" id="sendButton"${isSending ? " disabled" : ""}>${isSending ? "Running" : "Send"}</button>
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
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitPrompt(root, input.value.trim());
    }
  });
}
