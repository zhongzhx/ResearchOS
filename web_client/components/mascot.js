const MASCOT_ROOT = "/assets/mascot";
export const DEFAULT_MASCOT_ASSET = `${MASCOT_ROOT}/c57_default.png`;

const STATE_ASSETS = Object.freeze({
  idle: DEFAULT_MASCOT_ASSET,
  greeting: `${MASCOT_ROOT}/c57_greeting.png`,
  thinking: `${MASCOT_ROOT}/c57_thinking.png`,
  routing: `${MASCOT_ROOT}/c57_thinking.png`,
  working: `${MASCOT_ROOT}/c57_working.png`,
  harvesting_literature: `${MASCOT_ROOT}/c57_working.png`,
  parsing_pdf: `${MASCOT_ROOT}/c57_working.png`,
  building_kb: `${MASCOT_ROOT}/c57_working.png`,
  analyzing_data: `${MASCOT_ROOT}/c57_working.png`,
  waiting_user_confirmation: `${MASCOT_ROOT}/c57_listening.png`,
  need_more_info: `${MASCOT_ROOT}/c57_confused.png`,
  confused: `${MASCOT_ROOT}/c57_confused.png`,
  success: `${MASCOT_ROOT}/c57_success.png`,
  completed: `${MASCOT_ROOT}/c57_happy.png`,
  celebrating: `${MASCOT_ROOT}/c57_happy.png`,
  warning: `${MASCOT_ROOT}/c57_surprised.png`,
  error: `${MASCOT_ROOT}/c57_confused.png`,
  onboarding_complete: `${MASCOT_ROOT}/c57_peace.png`,
  ready_to_start: `${MASCOT_ROOT}/c57_peace.png`,
});

const STATE_MESSAGES = Object.freeze({
  idle: "我在这里。",
  greeting: "欢迎使用 Aura Research，有什么可以帮忙的？",
  thinking: "我在整理思路…",
  routing: "我在整理思路…",
  working: "我正在处理任务…",
  harvesting_literature: "我正在帮你检索和整理文献…",
  parsing_pdf: "我正在整理资料…",
  building_kb: "我正在把资料写入知识库…",
  analyzing_data: "我正在分析数据…",
  waiting_user_confirmation: "等你确认后我就开始。",
  need_more_info: "这里还差一点信息。",
  confused: "这里还差一点信息。",
  success: "搞定。",
  completed: "任务完成。",
  celebrating: "任务完成。",
  warning: "结果有些不同，我正在检查。",
  error: "这里出了一点问题，我需要换个方式。",
  onboarding_complete: "准备好了，我们开始吧。",
  ready_to_start: "准备好了，我们开始吧。",
});

const ALT_STATES = Object.freeze({
  onboarding_complete: "success",
  ready_to_start: "success",
});

function normalizeState(state) {
  return String(state || "idle").trim().toLowerCase();
}

function escapeAttribute(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function getMascotForState(state, _context = {}) {
  return STATE_ASSETS[normalizeState(state)] || DEFAULT_MASCOT_ASSET;
}

export function getMascotMessage(state, _context = {}) {
  return STATE_MESSAGES[normalizeState(state)] || STATE_MESSAGES.idle;
}

export function mascotStateForTaskStatus(status) {
  const normalized = normalizeState(status);
  if (["draft", "pending", "pending_confirmation", "confirmed", "needs_file", "needs_authorization"].includes(normalized)) {
    return "waiting_user_confirmation";
  }
  if (["running", "executing", "in_progress"].includes(normalized)) return "working";
  if (["completed", "complete", "done"].includes(normalized)) return "completed";
  if (["success", "submitted", "saved", "plan_only"].includes(normalized)) return "success";
  if (["failed", "failure", "error"].includes(normalized)) return "error";
  if (["warning", "unexpected"].includes(normalized)) return "warning";
  if (["needs_input", "need_more_info", "confused"].includes(normalized)) return "need_more_info";
  return "idle";
}

export function renderMascot(state, { size = "avatar", className = "" } = {}) {
  const normalized = normalizeState(state);
  const altState = ALT_STATES[normalized] || (STATE_ASSETS[normalized] ? normalized : "default");
  const extraClass = className ? ` ${escapeAttribute(className)}` : "";
  return `<img class="mascot-image mascot-${escapeAttribute(size)}${extraClass}" src="${getMascotForState(normalized)}" data-mascot data-mascot-fallback="${DEFAULT_MASCOT_ASSET}" alt="Aura C57 mascot ${escapeAttribute(altState)}" />`;
}

export function renderMascotFeedback(state, context) {
  return `<div class="mascot-feedback" role="status" aria-live="polite">
    ${renderMascot(state, { size: "indicator" })}
    <p>${escapeAttribute(getMascotMessage(state, context))}</p>
  </div>`;
}

export function bindMascotFallbacks(root) {
  root?.querySelectorAll?.("[data-mascot]").forEach((image) => {
    if (image.dataset.mascotFallbackBound === "true") return;
    image.dataset.mascotFallbackBound = "true";
    image.addEventListener("error", () => {
      if (image.dataset.mascotFallbackApplied === "true") return;
      image.dataset.mascotFallbackApplied = "true";
      image.src = image.dataset.mascotFallback || DEFAULT_MASCOT_ASSET;
    });
  });
}
