import * as api from "../api.js";
import { appState, ensureActiveConversation, saveChatMessage, setLastRunResult } from "../state.js";
import { escapeHtml } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { bindMascotFallbacks } from "../components/mascot.js";
import { workflowStatusPanel } from "../components/workflow_status.js";
import { bindWorkflowResultActions, renderWorkflowResult } from "../components/workflow_result.js";
import {
  WORKFLOW_DEFINITIONS,
  WORKFLOW_GROUPS,
  buildWorkflowPlan,
  createWorkflowDraft,
  executeWorkflow,
  formatWorkflowResult,
  groupedWorkflowDefinitions,
  listWorkflowHistory,
  normalizeWorkflowParams,
  saveWorkflowHistory,
  saveWorkflowArtifacts,
  updateWorkflowDraft,
  validateWorkflowParams,
  workflowHistoryRecord,
} from "../user_workflows.js";

let activeDraft = null;
let latestPlan = null;
let latestResult = null;
let formValues = {};
let activeGroup = "全部";
let searchTerm = "";
let renderedProjectId = null;

const STATUS_LABELS = {
  executable: "可执行",
  plan_only: "可生成计划",
  needs_file: "需要上传文件",
  needs_authorization: "需要授权",
  not_ready: "正在接入中",
};

const PARAM_LABELS = {
  query: "主题 / 关键词",
  source: "PDF / 资料",
  goal: "学习目标",
  claim: "需要支撑的论点",
  research_goal: "研究目标",
  model: "模型",
  sample: "样品 / 干预物",
  intervention: "干预条件",
  scenario: "使用场景",
  failure_description: "实验现象",
  protocol: "实验步骤",
  observed_data: "观察结果",
  experiment_notes: "今日实验记录",
  current_progress: "当前进展",
  constraints: "限制条件",
  deadline: "截止时间",
  file_id: "文件 / 表格",
  analysis_goal: "分析目标",
  assay_type: "实验类型",
  control_group: "对照组",
  result_summary: "结果摘要",
  species: "物种",
  pathway_database: "通路库",
  figure_goal: "图表目标",
  data_source: "数据来源",
  modeling_goal: "建模目标",
  target_column: "目标列",
  writing_goal: "写作目标",
  materials: "材料",
  section_type: "段落类型",
  text: "英文文本",
  manuscript_or_summary: "稿件 / 摘要",
  journal: "目标期刊",
  review_comments: "审稿意见",
  revision_notes: "修改说明",
  project_id: "项目",
  time_range: "时间范围",
  focus: "重点事项",
  max_results: "结果数量",
  recent_years: "近几年",
  include_review: "包含综述",
  max_papers: "目标数量",
  oa_only: "只处理开放获取",
  build_kb: "构建知识库",
  non_oa_policy: "非开放获取处理",
  language: "语言",
  output_format: "输出格式",
  include_figure_explanation: "解释图表",
  slide_count: "页数",
  include_speaker_notes: "讲稿备注",
  style: "图表风格",
  check_overclaim: "检查过度表述",
  preserve_meaning: "保留原意",
  require_action_mapping: "映射修改动作",
  require_revision_location: "标注修改位置",
};

const PARAM_PLACEHOLDERS = {
  query: "例如：巨噬细胞炎症因子调控",
  source: "上传文件后填写文件名，或从资料库选择",
  goal: "希望重点提取什么信息",
  claim: "例如：该通路会促进炎症因子释放",
  research_goal: "写下研究问题、假设或预期验证的机制",
  model: "细胞、动物、临床样本等",
  sample: "样品、药物、处理条件或对照",
  scenario: "例如：细胞培养、Western blot、动物给药",
  failure_description: "描述异常结果、失败现象或观察到的问题",
  experiment_notes: "粘贴今天的操作、观察和问题",
  current_progress: "写下已完成内容、阻塞和下一步想法",
  file_id: "先上传表格，或填写资料库文件名",
  analysis_goal: "例如：比较各组差异并绘制柱状图",
  assay_type: "qPCR、ELISA 或 CCK-8",
  result_summary: "粘贴差异代谢物、通路或富集结果",
  figure_goal: "例如：生成分组柱状图和显著性标注",
  modeling_goal: "例如：预测响应组并解释关键特征",
  writing_goal: "例如：写讨论段第一版",
  text: "粘贴需要润色的英文",
  manuscript_or_summary: "粘贴摘要、结果或稿件片段",
  review_comments: "粘贴审稿意见",
  journal: "例如：Nature Communications",
  project_id: "当前项目会自动填写",
  time_range: "例如：最近一周",
  focus: "希望周报重点覆盖的事项",
};

function currentProjectId() {
  return appState.activeProjectId || appState.activeProject?.id || appState.activeProject?.project_id || "";
}

function resetWorkspaceForProject(projectId) {
  if (renderedProjectId === projectId) return;
  activeDraft = null;
  latestPlan = null;
  latestResult = null;
  formValues = {};
  renderedProjectId = projectId;
}

function currentConversationId(projectId) {
  return ensureActiveConversation(projectId);
}

function selectedWorkflow(intent) {
  return WORKFLOW_DEFINITIONS[intent] || null;
}

function statusLabel(status) {
  return STATUS_LABELS[status] || "可生成计划";
}

function statusTone(status) {
  if (status === "executable") return "success";
  if (status === "not_ready") return "muted";
  if (status === "needs_file" || status === "needs_authorization") return "warning";
  return "muted";
}

function outputHint(definition) {
  return (definition.output_types || []).join(" / ");
}

function inputHint(definition) {
  return [...(definition.required_params || [])].map((key) => PARAM_LABELS[key] || key).join(" / ");
}

function cardMatches(definition) {
  const term = searchTerm.trim().toLowerCase();
  const groupMatch = activeGroup === "全部" || definition.group === activeGroup;
  if (!term) return groupMatch;
  const haystack = [definition.user_title, definition.user_description, definition.group, inputHint(definition), outputHint(definition)].join(" ").toLowerCase();
  return groupMatch && haystack.includes(term);
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

function recentWorkflowMarkup(projectId) {
  const rows = listWorkflowHistory(projectId)
    .filter((item) => selectedWorkflow(item.intent))
    .slice(0, 5);
  if (!rows.length) {
    return `<section class="workspace-recent" aria-label="最近工作流"><div class="section-heading"><h2>最近使用</h2></div><p class="muted-text">还没有最近使用的任务。</p></section>`;
  }
  return `<section class="workspace-recent" aria-label="最近工作流">
    <div class="section-heading"><h2>最近使用</h2></div>
    <div class="recent-workflow-row">
      ${rows
        .map(
          (item) => `<button class="recent-workflow" type="button" data-workflow-intent="${escapeHtml(item.intent)}">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(item.result_summary || "继续这个任务")}</span>
          </button>`,
        )
        .join("")}
    </div>
  </section>`;
}

function groupFilterMarkup() {
  return `<div class="workflow-filter-row" role="list" aria-label="工作台分组筛选">
    ${["全部", ...WORKFLOW_GROUPS]
      .map(
        (group) => `<button class="segmented-button ${activeGroup === group ? "active" : ""}" type="button" data-workflow-group="${escapeHtml(group)}">${escapeHtml(group)}</button>`,
      )
      .join("")}
  </div>`;
}

function workflowCardMarkup(definition) {
  const disabled = definition.current_status === "not_ready" ? "disabled" : "";
  const actionText = definition.current_status === "plan_only" ? "生成计划" : definition.current_status === "not_ready" ? "正在接入" : "打开";
  return `<button class="workflow-card" type="button" data-workflow-intent="${escapeHtml(definition.intent)}" ${disabled}>
    <div class="workflow-card-main">
      <div class="workflow-card-title">
        <strong>${escapeHtml(definition.user_title)}</strong>
        <span class="badge ${statusTone(definition.current_status)}">${escapeHtml(statusLabel(definition.current_status))}</span>
      </div>
      <p>${escapeHtml(definition.user_description)}</p>
      <div class="workflow-card-meta">
        <span>需要：${escapeHtml(inputHint(definition))}</span>
        <span>输出：${escapeHtml(outputHint(definition))}</span>
      </div>
    </div>
    <span class="workflow-card-action">${escapeHtml(actionText)}</span>
  </button>`;
}

function workflowGroupsMarkup() {
  const groups = groupedWorkflowDefinitions()
    .map(({ group, workflows }) => ({ group, workflows: workflows.filter(cardMatches) }))
    .filter(({ workflows }) => workflows.length);
  if (!groups.length) return `<div class="empty-state compact"><strong>没有找到匹配的工作台任务</strong><p>换一个关键词试试，例如“文献、PPT、qPCR”。</p></div>`;
  return groups
    .map(
      ({ group, workflows }) => `<section class="workflow-group">
        <div class="section-heading"><h2>${escapeHtml(group)}</h2></div>
        <div class="workflow-grid">${workflows.map(workflowCardMarkup).join("")}</div>
      </section>`,
    )
    .join("");
}

function paramInputType(param, value) {
  if (typeof value === "boolean") return "checkbox";
  if (["max_results", "recent_years", "max_papers", "slide_count"].includes(param)) return "number";
  if (["query", "source", "file_id", "assay_type", "journal", "project_id", "time_range", "language", "output_format", "style"].includes(param)) return "text";
  return "textarea";
}

function fieldMarkup(param, value, required) {
  const label = `${PARAM_LABELS[param] || param}${required ? " *" : ""}`;
  const placeholder = PARAM_PLACEHOLDERS[param] || "";
  const id = `workflow-param-${param}`;
  const type = paramInputType(param, value);
  if (type === "checkbox") {
    return `<label class="check-row"><input id="${escapeHtml(id)}" data-workflow-param="${escapeHtml(param)}" type="checkbox" ${value ? "checked" : ""} /> ${escapeHtml(label)}</label>`;
  }
  if (type === "number") {
    return `<label class="field-label">${escapeHtml(label)}
      <input class="field" id="${escapeHtml(id)}" data-workflow-param="${escapeHtml(param)}" type="number" min="1" value="${escapeHtml(value ?? "")}" placeholder="${escapeHtml(placeholder)}" />
    </label>`;
  }
  if (type === "text") {
    return `<label class="field-label">${escapeHtml(label)}
      <input class="field" id="${escapeHtml(id)}" data-workflow-param="${escapeHtml(param)}" lang="zh-CN" value="${escapeHtml(value ?? "")}" placeholder="${escapeHtml(placeholder)}" />
    </label>`;
  }
  return `<label class="field-label full-span">${escapeHtml(label)}
    <textarea class="field workflow-textarea" id="${escapeHtml(id)}" data-workflow-param="${escapeHtml(param)}" lang="zh-CN" placeholder="${escapeHtml(placeholder)}">${escapeHtml(value ?? "")}</textarea>
  </label>`;
}

function renderWorkflowFields(definition, values) {
  const params = [...new Set([...(definition.required_params || []), ...(definition.optional_params || [])])];
  return params.map((param) => fieldMarkup(param, values[param], definition.required_params.includes(param))).join("");
}

function statusPrompt(definition) {
  if (definition.current_status === "needs_file") return `<p class="workflow-hint">请先上传文件或选择资料库文件。</p>`;
  if (definition.current_status === "needs_authorization") return `<p class="workflow-hint">需要授权后执行。</p>`;
  if (definition.current_status === "not_ready") return `<p class="workflow-hint">该功能正在接入中。</p>`;
  return "";
}

function developerDetails(definition) {
  if (!(appState.developerMode && definition?.developer_notes)) return "";
  return `<details class="details workflow-technical">
    <summary>技术详情</summary>
    <p>${escapeHtml(definition.developer_notes)}</p>
  </details>`;
}

function actionMarkup(definition) {
  const disabled = definition.current_status === "not_ready" ? "disabled" : "";
  const planText = definition.current_status === "plan_only" ? "生成计划" : "生成计划";
  const confirmDisabled = ["plan_only", "not_ready", "needs_file", "needs_authorization"].includes(definition.current_status) ? "disabled" : "";
  const confirmLabel =
    definition.current_status === "not_ready"
      ? "该功能正在接入中"
      : definition.current_status === "needs_file"
        ? "需要上传文件"
        : definition.current_status === "needs_authorization"
          ? "需要授权后执行"
          : "确认开始";
  return `<div class="inline-actions full-span">
    <button class="button secondary" type="button" data-workflow-action="plan" ${disabled}>${planText}</button>
    <button class="button primary" type="button" data-workflow-action="confirm" ${confirmDisabled}>${confirmLabel}</button>
  </div>`;
}

function renderWorkflowDetailPage(projectId) {
  if (!activeDraft) return "";
  const definition = selectedWorkflow(activeDraft.intent);
  if (!definition) return "";
  const values = formValues || {};
  const planMarkup = latestPlan
    ? `<div class="workflow-preview">
        <strong>计划预览</strong>
        <p>${escapeHtml(latestPlan.message)}</p>
        <ul>${(latestPlan.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ul>
      </div>`
    : "";
  const resultMarkup = latestResult ? renderWorkflowResult(latestResult, { projectId }) : "";
  return `<section class="workflow-detail-page" id="workflowDetailPage">
    <div class="section-heading">
      <div>
        <span class="badge ${statusTone(definition.current_status)}">${escapeHtml(statusLabel(definition.current_status))}</span>
        <h2>${escapeHtml(definition.user_title)}</h2>
        <p>${escapeHtml(definition.user_description)}</p>
      </div>
      <button class="button ghost small" type="button" id="backToWorkflowList">返回工作台</button>
    </div>
    ${statusPrompt(definition)}
    <form class="form-grid" id="workflowForm">
      ${renderWorkflowFields(definition, values)}
      ${actionMarkup(definition)}
    </form>
    ${planMarkup}
    ${resultMarkup}
    ${developerDetails(definition)}
  </section>`;
}

function renderWorkflowHome(projectId) {
  return `<div class="workspace-layout">
    <div class="workspace-main">
      ${recentWorkflowMarkup(projectId)}
      <section class="workspace-tools">
        <input class="search-input" id="workflowSearch" value="${escapeHtml(searchTerm)}" placeholder="搜索功能，例如：文献、PPT、qPCR" />
        ${groupFilterMarkup()}
      </section>
      ${workflowGroupsMarkup()}
    </div>
  </div>`;
}

function renderWorkspaceContent(projectId) {
  if (!projectId) {
    return `<div class="workspace-layout">${emptyState("请先选择或创建项目", "每个项目拥有独立资料库，选择项目后才能开始科研任务。")}</div>`;
  }
  return activeDraft ? renderWorkflowDetailPage(projectId) : renderWorkflowHome(projectId);
}

function collectFormValues(root) {
  const values = {};
  root.querySelectorAll("[data-workflow-param]").forEach((field) => {
    const key = field.dataset.workflowParam;
    if (!key) return;
    if (field.type === "checkbox") values[key] = Boolean(field.checked);
    else if (field.type === "number") values[key] = Number(field.value || 0);
    else values[key] = field.value?.trim() || "";
  });
  return values;
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
    const planResult = formatWorkflowResult(
      {
        ok: true,
        status: "plan_only",
        intent: activeDraft.intent,
        title: activeDraft.title,
        message: latestPlan.message,
        steps: latestPlan.steps || [],
        current_step: latestPlan.current_step,
        next_step: latestPlan.next_step,
        params: activeDraft.params,
        project_id: projectId,
      },
      { developerMode: appState.developerMode },
    );
    latestResult = planResult;
    saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, { status: activeDraft.status, result_summary: latestPlan.message }));
    saveWorkflowArtifacts(projectId, activeDraft, planResult);
  }
  if (id === "confirm") {
    const definition = selectedWorkflow(activeDraft.intent);
    if (!definition || ["plan_only", "not_ready", "needs_file", "needs_authorization"].includes(definition.current_status)) return;
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
    const confirmedDraft = { ...activeDraft, status: "confirmed", current_step: "已确认", next_step: "开始执行。", linked_conversation_id: conversationId, plan: latestPlan };
    activeDraft = { ...confirmedDraft, status: "running", current_step: "正在执行", next_step: "完成后将显示结果。" };
    saveWorkflowHistory(projectId, workflowHistoryRecord(confirmedDraft, { status: "running", result_summary: "任务已确认，正在执行。" }));
    renderWorkspaceView({ root });
    const rawResult = await executeWorkflow(confirmedDraft, api, { projectId, conversationId, sessionId: appState.sessionId || conversationId });
    const result = formatWorkflowResult(rawResult, { developerMode: appState.developerMode });
    latestResult = result;
    activeDraft = { ...activeDraft, status: result.status, current_step: result.current_step, next_step: result.next_step, result };
    setLastRunResult(result);
    saveWorkflowHistory(projectId, workflowHistoryRecord(activeDraft, result));
    saveWorkflowArtifacts(projectId, activeDraft, result);
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

function bindWorkspaceEvents(root) {
  root.querySelector("#workflowSearch")?.addEventListener("input", (event) => {
    searchTerm = event.target.value || "";
    renderWorkspaceView({ root });
  });
  root.querySelectorAll("[data-workflow-group]").forEach((button) => {
    button.addEventListener("click", () => {
      activeGroup = button.dataset.workflowGroup || "全部";
      renderWorkspaceView({ root });
    });
  });
  root.querySelectorAll("[data-workflow-intent]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      startDraft(button.dataset.workflowIntent);
      renderWorkspaceView({ root });
    });
  });
  root.querySelector("#backToWorkflowList")?.addEventListener("click", () => {
    activeDraft = null;
    latestPlan = null;
    latestResult = null;
    renderWorkspaceView({ root });
  });
  root.querySelectorAll("[data-workflow-action]").forEach((button) => {
    button.addEventListener("click", () => handleWorkflowAction(root, button.dataset.workflowAction));
  });
  if (latestResult?.artifacts?.length) {
    bindWorkflowResultActions(root, { projectId: currentProjectId(), artifacts: latestResult.artifacts });
  }
}

export async function renderWorkspaceView({ root }) {
  const projectId = currentProjectId();
  resetWorkspaceForProject(projectId);
  const statusModel = latestResult ? { ...activeDraft, ...latestResult, result: latestResult } : activeDraft;
  root.innerHTML = `<section class="page workspace-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">科研工作台</h1>
        <p class="page-subtitle">选择一个科研交付物，先生成计划，确认后再开始可执行任务。</p>
      </div>
      ${workflowStatusPanel(statusModel, { developerMode: appState.developerMode })}
    </header>
    <div class="page-scroll">
      ${renderWorkspaceContent(projectId)}
    </div>
  </section>`;

  bindMascotFallbacks(root);
  bindWorkspaceEvents(root);
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
