import { escapeHtml } from "./cards.js";

export function renderWorkflowCard(workflow = {}) {
  const status = workflow.current_status || "not_connected";
  const action = status === "executable" ? "开始任务" : status === "needs_file" ? "先上传/选择文件" : "生成计划";
  return `<button class="workflow-card" type="button" data-workflow-intent="${escapeHtml(workflow.intent || "")}">
    <strong>${escapeHtml(workflow.user_title || workflow.intent || "科研任务")}</strong>
    <span class="badge">${escapeHtml(status)}</span>
    <p>${escapeHtml(workflow.user_description || "")}</p>
    <span>${escapeHtml(action)}</span>
  </button>`;
}
