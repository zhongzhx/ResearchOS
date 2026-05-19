import { escapeHtml } from "./cards.js";

const STATUS_LABELS = {
  draft: "待确认",
  pending_confirmation: "待确认",
  confirmed: "待确认",
  running: "运行中",
  completed: "已完成",
  plan_only: "已完成",
  needs_input: "需要补充信息",
  failed: "失败",
  cancelled: "已取消",
};

function statusLabel(status) {
  return STATUS_LABELS[status] || "待确认";
}

function technicalDetails(details, developerMode) {
  if (!developerMode || !details) return "";
  return `<details class="details workflow-technical">
    <summary>技术详情</summary>
    <pre class="json-view">${escapeHtml(JSON.stringify(details, null, 2))}</pre>
  </details>`;
}

function actionButtons(status) {
  if (status === "completed" || status === "plan_only") {
    return `<button class="button secondary small" type="button" data-workflow-action="view-result">查看结果</button>`;
  }
  if (status === "running") return "";
  if (status === "failed" || status === "cancelled") {
    return `<button class="button secondary small" type="button" data-workflow-action="modify">修改</button>`;
  }
  return `<button class="button primary small" type="button" data-workflow-action="confirm">确认开始</button>
    <button class="button secondary small" type="button" data-workflow-action="modify">修改</button>
    <button class="button ghost small" type="button" data-workflow-action="cancel">取消</button>`;
}

export function workflowStatusPanel(workflow, { developerMode = false } = {}) {
  if (!workflow) {
    return `<section class="workflow-status-card notice soft">
      <strong>选择一个任务开始</strong>
      <p>工作台会先收集必要信息，生成计划，等你确认后再执行。</p>
    </section>`;
  }
  const status = workflow.status || "draft";
  const steps = Array.isArray(workflow.steps) ? workflow.steps : Array.isArray(workflow.plan?.steps) ? workflow.plan.steps : [];
  const stepItems = steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
  const resultSummary = workflow.result_summary || workflow.result?.result_summary || workflow.message || "";
  const technical = workflow.technical || workflow.result?.technical || workflow.plan?.technical;
  return `<section class="workflow-status-card notice ${status === "failed" ? "warning" : "soft"}">
    <div class="workflow-status-heading">
      <strong>${escapeHtml(workflow.title || "科研任务")}</strong>
      <span class="status-pill">${escapeHtml(statusLabel(status))}</span>
    </div>
    ${workflow.current_step ? `<p>当前步骤：${escapeHtml(workflow.current_step)}</p>` : ""}
    ${workflow.next_step ? `<p>下一步：${escapeHtml(workflow.next_step)}</p>` : ""}
    ${resultSummary ? `<p>结果摘要：${escapeHtml(resultSummary)}</p>` : ""}
    ${steps.length ? `<ul>${stepItems}</ul>` : ""}
    <div class="inline-actions">${actionButtons(status)}</div>
    ${technicalDetails(technical, developerMode)}
  </section>`;
}
