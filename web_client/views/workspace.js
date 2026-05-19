import * as api from "../api.js";
import { appState, ensureActiveConversation, saveChatMessage, setLastRunResult } from "../state.js";
import { escapeHtml } from "../components/cards.js";
import { workflowStatusPanel } from "../components/workflow_status.js";
import {
  WORKFLOW_DEFINITIONS,
  buildWorkflowPlan,
  createWorkflowDraft,
  executeWorkflow,
  formatWorkflowResult,
  listWorkflowHistory,
  normalizeWorkflowParams,
  saveWorkflowHistory,
  updateWorkflowDraft,
  validateWorkflowParams,
  workflowHistoryRecord,
} from "../user_workflows.js";

const workflowCards = [
  {
    title: "文献采集与知识库构建",
    intent: "literature_harvest_and_kb",
    description: "输入关键词，检索文献，只处理合法开放获取或你手动下载的全文，并构建项目知识库。",
  },
  {
    title: "上传 PDF 并学习",
    intent: "ingest_uploaded_papers",
    description: "把论文或资料加入当前项目知识库。",
  },
  {
    title: "实验方案设计",
    intent: "experiment_design",
    description: "根据研究目标生成实验路线、分组、指标和注意事项。",
  },
  {
    title: "SOP / Protocol 整理",
    intent: "protocol_to_sop",
    description: "从论文、说明书或你的描述中整理可执行 SOP。",
  },
  {
    title: "数据分析与作图",
    intent: "data_analysis",
    description: "上传表格，生成统计分析、可视化和结果解释计划。",
  },
  {
    title: "写作与审稿",
    intent: "writing_review",
    description: "帮助整理结果、润色段落、模拟审稿意见。",
  },
  {
    title: "实验失败复盘",
    intent: "failure_recovery",
    description: "根据实验现象分析可能原因和下一步排查方案。",
  },
  {
    title: "周报生成",
    intent: "weekly_report",
    description: "汇总最近项目进展、问题和下周计划。",
  },
];

let activeDraft = null;
let latestPlan = null;
let latestResult = null;
let formValues = {};

function currentProjectId() {
  return appState.activeProjectId || appState.activeProject?.id || appState.activeProject?.project_id || "";
}

function currentConversationId(projectId) {
  return ensureActiveConversation(projectId);
}

function selectedWorkflow(intent) {
  return workflowCards.find((card) => card.intent === intent) || workflowCards[0];
}

function startDraft(intent, params = {}) {
  const projectId = currentProjectId();
  const conversationId = projectId ? currentConversationId(projectId) : "";
  const draft = createWorkflowDraft(intent, params, { projectId, conversationId, source: "workspace" });
  activeDraft = draft;
  latestPlan = null;
  latestResult = null;
  formValues = { ...draft.params };
  saveWorkflowHistory(projectId, workflowHistoryRecord(draft, { status: draft.status, result_summary: draft.next_step }));
  return draft;
}

function syncDraftFromForm(root) {
  if (!activeDraft) return null;
  formValues = collectFormValues(root);
  const params = normalizeWorkflowParams(activeDraft.intent, formValues, activeDraft.context || {});
  activeDraft = {
    ...activeDraft,
    params,
    updated_at: new Date().toISOString(),
    validation: validateWorkflowParams(activeDraft.intent, params),
  };
  return activeDraft;
}

function workflowCardsMarkup() {
  return workflowCards
    .map(
      (card, index) => `<button class="workflow-card" type="button" data-workflow-intent="${escapeHtml(card.intent)}">
        <span class="workflow-card-icon" aria-hidden="true">${index + 1}</span>
        <strong>${escapeHtml(card.title)}</strong>
      </button>`,
    )
    .join("");
}

function textField(id, label, value = "", placeholder = "", extra = "") {
  return `<label class="field-label">${escapeHtml(label)}
    <input class="field" id="${escapeHtml(id)}" lang="zh-CN" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}" ${extra} />
  </label>`;
}

function textArea(id, label, value = "", placeholder = "") {
  return `<label class="field-label full-span">${escapeHtml(label)}
    <textarea class="field workflow-textarea" id="${escapeHtml(id)}" lang="zh-CN" placeholder="${escapeHtml(placeholder)}">${escapeHtml(value)}</textarea>
  </label>`;
}

function renderWorkflowFields(intent, values) {
  if (intent === "literature_harvest_and_kb") {
    return `
      ${textField("workflow-query", "研究主题 / 关键词", values.query || "", "例如：巨噬细胞炎症因子调控")}
      ${textField("workflow-max-papers", "目标数量", values.max_papers || 20, "", 'type="number" min="1" max="20"')}
      <label class="check-row"><input id="workflow-oa-only" type="checkbox" ${values.oa_only === false ? "" : "checked"} /> 只处理开放获取或手动下载全文</label>
      <label class="check-row"><input id="workflow-build-kb" type="checkbox" ${values.build_kb === false ? "" : "checked"} /> 构建知识库</label>
    `;
  }
  if (intent === "ingest_uploaded_papers") {
    return `
      ${textField("workflow-source", "论文或资料", values.source || "", "文件名、DOI、标题或资料说明")}
      ${textArea("workflow-goal", "学习目标", values.goal || "", "希望重点提取什么信息")}
    `;
  }
  if (intent === "data_analysis") {
    return `
      ${textField("workflow-file-id", "数据文件", values.file_id || values.uploaded_file || "", "填写文件名，或先在项目中上传表格")}
      ${textArea("workflow-analysis-goal", "分析目标", values.analysis_goal || "", "例如：比较各组差异并绘制柱状图")}
    `;
  }
  if (intent === "experiment_design") {
    return `
      ${textArea("workflow-research-goal", "研究目标", values.research_goal || "", "写下研究问题、假设或预期验证的机制")}
      ${textField("workflow-model", "模型", values.model || "", "细胞、动物、临床样本等")}
      ${textField("workflow-sample", "样品 / 干预物", values.sample || values.intervention || "", "样品、药物、处理条件或对照")}
    `;
  }
  if (intent === "protocol_to_sop") {
    return `
      ${textArea("workflow-source", "论文、说明书或描述", values.source || "", "粘贴步骤、材料或来源说明")}
      ${textField("workflow-scenario", "使用场景", values.scenario || "", "例如：细胞培养、Western blot、动物给药")}
    `;
  }
  if (intent === "writing_review") {
    return `
      ${textArea("workflow-writing-goal", "写作目标或材料", values.writing_goal || "", "粘贴需要整理、润色或审稿的内容")}
    `;
  }
  if (intent === "failure_recovery") {
    return `
      ${textArea("workflow-failure-description", "实验失败现象", values.failure_description || "", "描述异常结果、失败现象或观察到的问题")}
    `;
  }
  if (intent === "weekly_report") {
    return `
      ${textField("workflow-time-range", "时间范围", values.time_range || "recent", "例如：最近一周")}
      ${textArea("workflow-focus", "重点事项", values.focus || "", "可选：希望周报重点覆盖的进展或问题")}
    `;
  }
  return textArea("workflow-notes", "补充说明", values.notes || "");
}

function renderWorkflowForm() {
  if (!activeDraft) return "";
  const workflow = selectedWorkflow(activeDraft.intent);
  const values = formValues || {};
  const planMarkup = latestPlan
    ? `<div class="workflow-preview">
        <strong>计划预览</strong>
        <p>${escapeHtml(latestPlan.message)}</p>
        <ul>${(latestPlan.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul>
      </div>`
    : "";
  return `<aside class="workflow-drawer" id="workflowDrawer">
    <div class="section-heading">
      <div><h2>${escapeHtml(workflow.title)}</h2><p>${escapeHtml(workflow.description)}</p></div>
      <button class="button ghost small" type="button" id="closeWorkflowDrawer">关闭</button>
    </div>
    <form class="form-grid" id="workflowForm">
      ${renderWorkflowFields(activeDraft.intent, values)}
      <div class="inline-actions full-span">
        <button class="button secondary" type="button" data-workflow-action="plan">生成计划</button>
        <button class="button primary" type="button" data-workflow-action="confirm">确认开始</button>
      </div>
    </form>
    ${planMarkup}
  </aside>`;
}

function collectFormValues(root) {
  const get = (selector) => root.querySelector(selector)?.value?.trim() || "";
  const checked = (selector) => Boolean(root.querySelector(selector)?.checked);
  const intent = activeDraft?.intent || "";
  if (intent === "literature_harvest_and_kb") {
    return {
      query: get("#workflow-query"),
      max_papers: Number(get("#workflow-max-papers") || 20),
      oa_only: checked("#workflow-oa-only"),
      build_kb: checked("#workflow-build-kb"),
      non_oa_policy: "manual_queue",
    };
  }
  if (intent === "ingest_uploaded_papers") return { source: get("#workflow-source"), goal: get("#workflow-goal") };
  if (intent === "data_analysis") return { file_id: get("#workflow-file-id"), analysis_goal: get("#workflow-analysis-goal") };
  if (intent === "experiment_design") return { research_goal: get("#workflow-research-goal"), model: get("#workflow-model"), sample: get("#workflow-sample") };
  if (intent === "protocol_to_sop") return { source: get("#workflow-source"), scenario: get("#workflow-scenario") };
  if (intent === "writing_review") return { writing_goal: get("#workflow-writing-goal") };
  if (intent === "failure_recovery") return { failure_description: get("#workflow-failure-description") };
  if (intent === "weekly_report") return { project_id: currentProjectId(), time_range: get("#workflow-time-range"), focus: get("#workflow-focus") };
  return { notes: get("#workflow-notes") };
}

function historyMarkup(projectId) {
  const rows = listWorkflowHistory(projectId)
    .slice(0, 6)
    .map(
      (item) => `<li>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.result_summary || item.status || "")}</span>
      </li>`,
    )
    .join("");
  return `<section class="workflow-preview">
    <strong>最近工作流</strong>
    ${rows ? `<ul>${rows}</ul>` : `<p>暂无历史。</p>`}
  </section>`;
}

async function handleWorkflowAction(root, id) {
  const projectId = currentProjectId();
  if (!activeDraft) return;
  if (id === "cancel") {
    activeDraft = updateWorkflowDraft(activeDraft, "取消");
    saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, { status: "cancelled", result_summary: "用户取消了任务。" }));
    renderWorkspaceView({ root });
    return;
  }
  syncDraftFromForm(root);
  if (id === "plan") {
    latestPlan = buildWorkflowPlan(activeDraft.intent, activeDraft.params, activeDraft.context || {});
    activeDraft = {
      ...activeDraft,
      status: latestPlan.status,
      current_step: latestPlan.current_step,
      next_step: latestPlan.next_step,
      plan: latestPlan,
    };
    saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, { status: activeDraft.status, result_summary: latestPlan.message }));
  }
  if (id === "confirm") {
    latestPlan = latestPlan || buildWorkflowPlan(activeDraft.intent, activeDraft.params, activeDraft.context || {});
    if (!latestPlan.ok) {
      activeDraft = {
        ...activeDraft,
        status: "needs_input",
        current_step: "需要补充信息",
        next_step: latestPlan.next_step,
        plan: latestPlan,
      };
      saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, { status: activeDraft.status, result_summary: latestPlan.message }));
      renderWorkspaceView({ root });
      return;
    }
    const conversationId = currentConversationId(projectId);
    activeDraft = { ...activeDraft, status: "confirmed", current_step: "已确认", next_step: "开始执行。", linked_conversation_id: conversationId, plan: latestPlan };
    saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, { status: "running", result_summary: "任务已确认，正在执行。" }));
    renderWorkspaceView({ root });
    const rawResult = await executeWorkflow(activeDraft, api, { projectId, conversationId, sessionId: appState.sessionId || conversationId });
    const result = formatWorkflowResult(rawResult, { developerMode: appState.developerMode });
    latestResult = result;
    activeDraft = { ...activeDraft, status: result.status, current_step: result.current_step, next_step: result.next_step, result };
    setLastRunResult(result);
    saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, result));
    saveChatMessage({
      role: "assistant",
      content: result.result_summary || result.message,
      created_at: new Date().toISOString(),
      project_id: projectId,
      conversation_id: conversationId,
    });
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
  }
  renderWorkspaceView({ root });
}

export async function renderWorkspaceView({ root }) {
  const projectId = currentProjectId();
  const statusModel = latestResult ? { ...activeDraft, ...latestResult, result: latestResult } : activeDraft;
  root.innerHTML = `<section class="page workspace-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">科研工作台</h1>
      </div>
      ${workflowStatusPanel(statusModel, { developerMode: appState.developerMode })}
    </header>
    <div class="page-scroll">
      <div class="workflow-layout workspace-layout">
        <div>
          <div class="workflow-grid">${workflowCardsMarkup()}</div>
        </div>
        ${renderWorkflowForm()}
      </div>
    </div>
  </section>`;

  root.querySelectorAll("[data-workflow-intent]").forEach((button) => {
    button.addEventListener("click", () => {
      startDraft(button.dataset.workflowIntent);
      renderWorkspaceView({ root });
    });
  });
  root.querySelector("#closeWorkflowDrawer")?.addEventListener("click", () => {
    activeDraft = null;
    latestPlan = null;
    latestResult = null;
    renderWorkspaceView({ root });
  });
  root.querySelectorAll("[data-workflow-action]").forEach((button) => {
    button.addEventListener("click", () => handleWorkflowAction(root, button.dataset.workflowAction));
  });
  window.addEventListener(
    "researchos:workflow-history-updated",
    () => {
      if (!activeDraft) renderWorkspaceView({ root });
    },
    { once: true },
  );
}

export async function startUserWorkflow(intent, params = {}) {
  const draft = startDraft(intent, params);
  const plan = buildWorkflowPlan(intent, draft.params, draft.context || {});
  if (!plan.ok) return formatWorkflowResult(plan, { developerMode: appState.developerMode });
  const confirmed = { ...draft, status: "confirmed", plan };
  const rawResult = await executeWorkflow(confirmed, api, { projectId: currentProjectId(), conversationId: draft.linked_conversation_id });
  return formatWorkflowResult(rawResult, { developerMode: appState.developerMode });
}
