const WORKFLOW_HISTORY_PREFIX = "researchos.workflowHistory.v1.";
const CONFIRM_WORDS = ["好", "可以", "开始", "确认", "执行", "就按这个", "没问题"];
const CANCEL_WORDS = ["取消", "不要", "先不做", "停止"];

function nowIso() {
  return new Date().toISOString();
}

function normalize(value) {
  return String(value ?? "").trim();
}

function safeNumber(value, fallback) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
}

function compactId(value) {
  return normalize(value)
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function workflowId(intent) {
  return `workflow-${compactId(intent) || "task"}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function historyKey(projectId) {
  return `${WORKFLOW_HISTORY_PREFIX}${compactId(projectId) || "default"}`;
}

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Workflow history is a local convenience cache; failure should not block the task.
  }
}

function cnBool(value) {
  return value ? "是" : "否";
}

function visibleParamValue(value, fallback = "待补充") {
  const text = normalize(value);
  return text || fallback;
}

export const WORKFLOW_DEFINITIONS = {
  literature_harvest_and_kb: {
    user_title: "文献采集与知识库构建",
    user_description: "围绕一个研究主题检索文献，只处理合法开放获取或用户手动下载的全文，并构建项目知识库。",
    required_params: ["query"],
    default_params: { max_papers: 20, oa_only: true, build_kb: true, non_oa_policy: "manual_queue" },
    confirmation_template: "我将检索“{query}”相关文献，最多 {max_papers} 篇，仅处理合法开放获取或用户手动下载的全文，并在完成后构建知识库。",
    execution_strategy: "legacy_literature_api",
    user_visible_steps: ["确认检索主题", "创建文献采集任务", "检索开放获取文献", "整理手动下载队列", "构建项目知识库"],
    risk_level: "medium",
    requires_confirmation: true,
    developer_notes: "Uses createLiteratureSearchTask -> runLiteratureSearch -> generatePaperRequests -> buildKnowledgeBase. Non-OA material stays in manual queue.",
  },
  ingest_uploaded_papers: {
    user_title: "上传 PDF 并学习",
    user_description: "把用户已上传或手动提供的论文加入项目资料库，并整理成知识库可用材料。",
    required_params: ["source"],
    default_params: {},
    confirmation_template: "我将处理你提供的资料“{source}”，提取摘要、关键结论和可入库信息。",
    execution_strategy: "plan_only",
    user_visible_steps: ["确认资料来源", "检查可处理文件", "提取论文信息", "写入项目知识库"],
    risk_level: "low",
    requires_confirmation: true,
    developer_notes: "No stable uploaded-paper ingestion API is wired in the client yet.",
  },
  data_analysis: {
    user_title: "数据分析与作图",
    user_description: "根据数据文件和分析目标生成统计分析、可视化和结果解释计划。",
    required_params: ["file_id", "analysis_goal"],
    default_params: {},
    confirmation_template: "我将根据“{analysis_goal}”生成数据分析计划，并等待数据分析入口接入后执行。",
    execution_strategy: "plan_only",
    user_visible_steps: ["确认数据文件", "确认分析目标", "生成分析计划", "等待执行入口接入"],
    risk_level: "medium",
    requires_confirmation: true,
    developer_notes: "Parser/data-analysis execution is not fully connected; return plan_only instead of reporting fake success.",
  },
  experiment_design: {
    user_title: "实验方案设计",
    user_description: "根据研究目标生成实验路线、分组、指标、风险和下一步确认清单。",
    required_params: ["research_goal"],
    default_params: {},
    confirmation_template: "我将围绕“{research_goal}”生成实验设计方案。",
    execution_strategy: "coordinator_or_chat",
    user_visible_steps: ["确认研究目标", "梳理实验变量", "生成方案", "列出风险和确认清单"],
    risk_level: "medium",
    requires_confirmation: true,
    developer_notes: "Use coordinator when available; otherwise return plan_only/chat-style plan, never label it as a skill run.",
  },
  protocol_to_sop: {
    user_title: "SOP / Protocol 整理",
    user_description: "把论文、说明书或实验描述整理成可执行 SOP。",
    required_params: ["source"],
    default_params: { target_format: "step_by_step_sop" },
    confirmation_template: "我将把“{source}”整理成可执行 SOP。",
    execution_strategy: "plan_only",
    user_visible_steps: ["确认来源材料", "提取关键步骤", "整理 SOP", "列出质控点"],
    risk_level: "medium",
    requires_confirmation: true,
    developer_notes: "Real protocol extraction/SOP APIs may exist but are not yet unified behind this user controller.",
  },
  writing_review: {
    user_title: "写作与审稿",
    user_description: "整理结果、润色段落，或模拟审稿意见。",
    required_params: ["writing_goal"],
    default_params: {},
    confirmation_template: "我将按“{writing_goal}”处理写作任务。",
    execution_strategy: "plan_only",
    user_visible_steps: ["确认写作目标", "整理材料", "生成修改建议", "输出可继续编辑的文本"],
    risk_level: "low",
    requires_confirmation: true,
    developer_notes: "Keep user-facing copy clean; do not expose writing skill internals.",
  },
  failure_recovery: {
    user_title: "实验失败复盘",
    user_description: "根据实验现象、失败结果和已排查条件，生成可能原因和下一步排查方案。",
    required_params: ["failure_description"],
    default_params: {},
    confirmation_template: "我将根据“{failure_description}”做失败复盘。",
    execution_strategy: "plan_only",
    user_visible_steps: ["确认失败现象", "梳理已排查条件", "排列可能原因", "给出下一步排查方案"],
    risk_level: "medium",
    requires_confirmation: true,
    developer_notes: "Plan-only until a stable failure recovery route is available.",
  },
  weekly_report: {
    user_title: "周报生成",
    user_description: "汇总当前项目最近进展、问题、风险和下一步计划。",
    required_params: ["project_id"],
    default_params: { time_range: "recent" },
    confirmation_template: "我将汇总当前项目的最近进展并生成周报。",
    execution_strategy: "plan_only",
    user_visible_steps: ["确认项目", "汇总最近记录", "整理风险和阻塞", "生成周报"],
    risk_level: "low",
    requires_confirmation: true,
    developer_notes: "Plan-only in this controller unless weekly report API is wired later.",
  },
};

export function normalizeWorkflowParams(intent, params = {}, context = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent] || {};
  const normalized = { ...(definition.default_params || {}), ...(params || {}) };
  if (normalized.topic && !normalized.query) normalized.query = normalized.topic;
  if (normalized.goal && intent === "experiment_design" && !normalized.research_goal) normalized.research_goal = normalized.goal;
  if (normalized.goal && intent === "data_analysis" && !normalized.analysis_goal) normalized.analysis_goal = normalized.goal;
  if (normalized.file && intent === "data_analysis" && !normalized.file_id) normalized.file_id = normalized.file;
  if (normalized.material && intent === "writing_review" && !normalized.writing_goal) normalized.writing_goal = normalized.goal || normalized.material;
  if (normalized.phenomenon && intent === "failure_recovery" && !normalized.failure_description) normalized.failure_description = normalized.phenomenon;
  if (context.projectId && !normalized.project_id) normalized.project_id = context.projectId;
  if (intent === "literature_harvest_and_kb") {
    normalized.max_papers = Math.min(safeNumber(normalized.max_papers || normalized.targetCount, 20), 20);
    normalized.oa_only = normalized.oa_only !== false && normalized.openAccessOnly !== false;
    normalized.build_kb = normalized.build_kb !== false && normalized.buildKnowledgeBase !== false;
    normalized.non_oa_policy = normalized.non_oa_policy || "manual_queue";
  }
  return normalized;
}

export function createWorkflowDraft(intent, initialParams = {}, context = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  if (!definition) {
    return {
      workflow_id: workflowId("unknown"),
      intent,
      title: "未知科研任务",
      params: { ...(initialParams || {}) },
      status: "failed",
      current_step: "无法识别任务",
      next_step: "请换一种方式描述你想完成的科研工作。",
      created_at: nowIso(),
      updated_at: nowIso(),
      context: { ...(context || {}) },
    };
  }
  const timestamp = nowIso();
  const params = normalizeWorkflowParams(intent, initialParams, context);
  const validation = validateWorkflowParams(intent, params);
  return {
    workflow_id: workflowId(intent),
    intent,
    title: definition.user_title,
    user_description: definition.user_description,
    params,
    status: validation.ok ? "draft" : "needs_input",
    required_params: [...definition.required_params],
    current_step: validation.ok ? "已收集必要信息" : "需要补充信息",
    next_step: validation.ok ? "生成计划并请你确认。" : validation.questions[0],
    created_at: timestamp,
    updated_at: timestamp,
    linked_conversation_id: context.conversationId || "",
    context: { ...(context || {}) },
    validation,
  };
}

export function validateWorkflowParams(intent, params = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  const missing = [];
  const questions = [];
  if (!definition) {
    return { ok: false, missing: ["intent"], questions: ["我还不能识别这个任务，请换一种方式描述。"] };
  }
  const normalized = normalizeWorkflowParams(intent, params, {});
  for (const key of definition.required_params) {
    if (intent === "data_analysis" && key === "file_id" && (normalized.uploaded_file || normalized.file)) continue;
    if (!normalize(normalized[key])) missing.push(key);
  }
  if (missing.includes("query")) questions.push("请告诉我文献检索主题或关键词。");
  if (missing.includes("source")) questions.push("请告诉我需要处理的论文、PDF、protocol 或资料来源。");
  if (missing.includes("file_id")) questions.push("请告诉我数据文件，或先上传/选择一个数据表。");
  if (missing.includes("analysis_goal")) questions.push("请告诉我分析目标，例如比较哪些组、输出什么图。");
  if (missing.includes("research_goal")) questions.push("请补充实验目标、模型或想验证的机制。");
  if (missing.includes("writing_goal")) questions.push("请告诉我写作目标或需要处理的段落。");
  if (missing.includes("failure_description")) questions.push("请描述实验失败现象、异常结果或已经排查过的条件。");
  if (missing.includes("project_id")) questions.push("请先选择一个项目。");
  return {
    ok: missing.length === 0,
    missing,
    questions: questions.length ? questions : ["请补充执行这个任务所需的关键信息。"],
  };
}

function fillTemplate(template, params) {
  return String(template || "").replace(/\{([A-Za-z0-9_]+)\}/g, (_, key) => visibleParamValue(params[key]));
}

export function buildWorkflowPlan(intent, params = {}, context = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  const normalized = normalizeWorkflowParams(intent, params, context);
  const validation = validateWorkflowParams(intent, normalized);
  if (!definition) {
    return {
      ok: false,
      status: "failed",
      title: "未知科研任务",
      message: "我还不能识别这个任务。",
      steps: [],
      next_step: "请换一种方式描述你想完成的科研工作。",
      validation,
    };
  }
  if (!validation.ok) {
    return {
      ok: false,
      status: "needs_input",
      title: definition.user_title,
      message: validation.questions[0],
      steps: ["补充必要信息"],
      next_step: validation.questions[0],
      params: normalized,
      validation,
    };
  }
  const plan = {
    ok: true,
    status: "pending_confirmation",
    intent,
    title: definition.user_title,
    message: fillTemplate(definition.confirmation_template, normalized),
    steps: [...definition.user_visible_steps],
    current_step: "待确认",
    next_step: definition.requires_confirmation ? "确认后开始执行。" : "可以直接生成结果。",
    risk_level: definition.risk_level,
    params: normalized,
    technical: {
      execution_strategy: definition.execution_strategy,
      developer_notes: definition.developer_notes,
    },
  };
  return plan;
}

function extractCount(text) {
  const match = text.match(/(?:改成|调整为|设置为|最多|前)\s*(\d+)\s*篇/);
  return match ? Number(match[1]) : null;
}

function extractQuery(text) {
  return normalize(text)
    .replace(/^(请|麻烦|帮我|给我|可以)?/g, "")
    .replace(/(下载文献并入库|下载文献|检索文献|采集文献|构建知识库|查一下|方向的论文|文献)/g, "")
    .trim();
}

export function updateWorkflowDraft(draft, userMessage) {
  const text = normalize(userMessage);
  const params = { ...(draft?.params || {}) };
  const intent = draft?.intent || "";
  const lower = text.toLowerCase();
  if (CANCEL_WORDS.some((word) => lower.includes(word))) {
    return { ...draft, status: "cancelled", updated_at: nowIso(), current_step: "已取消", next_step: "" };
  }
  const count = extractCount(text);
  if (intent === "literature_harvest_and_kb" && count) params.max_papers = Math.min(count, 20);
  if (intent === "literature_harvest_and_kb" && text.includes("近五年")) params.recent_years = 5;
  if (intent === "literature_harvest_and_kb" && !params.query) params.query = extractQuery(text) || text;
  if (intent === "experiment_design" && !params.research_goal) params.research_goal = text;
  if (intent === "data_analysis") {
    if (!params.analysis_goal) params.analysis_goal = text;
    if (!params.file_id && !params.uploaded_file) params.uploaded_file = text;
  }
  if (intent === "ingest_uploaded_papers" && !params.source) params.source = text;
  if (intent === "protocol_to_sop" && !params.source) params.source = text;
  if (intent === "writing_review" && !params.writing_goal) params.writing_goal = text;
  if (intent === "failure_recovery" && !params.failure_description) params.failure_description = text;
  const normalized = normalizeWorkflowParams(intent, params, draft?.context || {});
  const validation = validateWorkflowParams(intent, normalized);
  const confirmed = CONFIRM_WORDS.some((word) => lower === word || lower.includes(word));
  return {
    ...draft,
    params: normalized,
    status: confirmed && validation.ok ? "confirmed" : validation.ok ? "draft" : "needs_input",
    current_step: validation.ok ? (confirmed ? "已确认" : "已更新参数") : "需要补充信息",
    next_step: validation.ok ? "确认后开始执行。" : validation.questions[0],
    updated_at: nowIso(),
    validation,
  };
}

function resultSummary(result) {
  return normalize(result?.message || result?.result_summary || result?.title || "任务状态已更新。");
}

function asTechnical(response) {
  return response?.data || response || {};
}

function backendMessage(response) {
  return normalize(response?.error || response?.data?.message || response?.data?.error || response?.message || "后端没有返回成功状态");
}

function failedWorkflowStep(intent, title, result, completedSteps = []) {
  return {
    ok: false,
    status: "failed",
    intent,
    title: "任务执行失败",
    message: `${title}没有完成：${backendMessage(result)}。已停止后续步骤。`,
    steps: [...completedSteps, `${title}失败`],
    current_step: `${title}失败`,
    next_step: "请检查项目、文件或后端服务状态后重试。",
    result_summary: `${title}没有完成，任务已停止。`,
    technical: asTechnical(result),
  };
}

function manualQueueCount(result) {
  const payload = result?.data || {};
  const rows = payload.paper_requests || payload.requests || payload.manual_queue || [];
  if (Array.isArray(rows)) return rows.length;
  return Number(payload.manual_queue_count || 0);
}

async function executeLiteratureWorkflow(draft, api) {
  const params = normalizeWorkflowParams(draft.intent, draft.params, draft.context || {});
  const projectId = params.project_id || draft.context?.projectId || "default";
  const payload = {
    project_id: projectId,
    query: params.query,
    keywords: [params.query].filter(Boolean),
    max_results: Math.min(safeNumber(params.max_papers, 20), 20),
    oa_only: params.oa_only !== false,
    non_oa_policy: params.non_oa_policy || "manual_queue",
  };
  const completed = [];
  const createTask = await api.createLiteratureSearchTask(payload);
  if (!createTask?.ok) return failedWorkflowStep(draft.intent, "创建文献采集任务", createTask, completed);
  completed.push("创建文献采集任务");
  const search = await api.runLiteratureSearch(payload);
  if (!search?.ok) return failedWorkflowStep(draft.intent, "检索文献", search, completed);
  completed.push("检索开放获取文献");
  const paperRequests = await api.generatePaperRequests({ project_id: projectId });
  if (!paperRequests?.ok) return failedWorkflowStep(draft.intent, "整理手动下载队列", paperRequests, completed);
  completed.push("整理手动下载队列");
  let kb = null;
  if (params.build_kb !== false) {
    kb = await api.buildKnowledgeBase({ project_id: projectId });
    if (!kb?.ok) return failedWorkflowStep(draft.intent, "构建知识库", kb, completed);
    completed.push("构建项目知识库");
  } else {
    completed.push("跳过知识库构建");
  }
  const manualCount = manualQueueCount(paperRequests);
  return {
    ok: true,
    status: "completed",
    intent: draft.intent,
    title: WORKFLOW_DEFINITIONS[draft.intent].user_title,
    message:
      manualCount > 0
        ? `文献检索已完成，可合法开放获取的文献已处理；有 ${manualCount} 篇非开放获取或无法下载的文献已进入手动下载队列。`
        : "文献检索已完成，可合法开放获取的文献已处理，并已按设置构建知识库。",
    steps: completed,
    current_step: "已完成",
    next_step: manualCount > 0 ? "请在手动下载队列中补充无法自动获取的全文。" : "可以在资料库和知识库中查看结果。",
    manual_queue_count: manualCount,
    result_summary: manualCount > 0 ? `完成文献采集；${manualCount} 篇需要手动下载。` : "完成文献采集和知识库构建。",
    technical: { createTask: createTask.data, search: search.data, paperRequests: paperRequests.data, kb: kb?.data },
  };
}

async function executePlanOnlyWorkflow(draft, api, options = {}) {
  const definition = WORKFLOW_DEFINITIONS[draft.intent];
  const plan = buildWorkflowPlan(draft.intent, draft.params, draft.context || {});
  if (draft.intent === "experiment_design" && api?.runCoordinator) {
    const prompt = [
      `请根据用户确认的科研工作流生成方案：${definition.user_title}`,
      ...Object.entries(draft.params || {}).map(([key, value]) => `${key}: ${value}`),
      "请用中文输出方案，不要声称已经运行内部 skill 或 pipeline。",
    ].join("\n");
    const coordinator = await api.runCoordinator(prompt, draft.params?.project_id || options.projectId || "default", options.conversationId || "", options.sessionId || "");
    if (coordinator?.ok) {
      return {
        ok: true,
        status: "completed",
        intent: draft.intent,
        title: definition.user_title,
        message: coordinator.data?.answer || coordinator.data?.message || "已生成实验方案。",
        steps: plan.steps,
        current_step: "已完成",
        next_step: "请根据方案确认分组、样本量和关键质控点。",
        result_summary: "已生成实验设计方案。",
        technical: coordinator.data,
      };
    }
  }
  const dataAnalysisMessage = "数据分析执行入口仍在接入中，我可以先帮你生成分析计划。";
  return {
    ok: draft.intent !== "data_analysis",
    status: "plan_only",
    intent: draft.intent,
    title: definition.user_title,
    message: draft.intent === "data_analysis" ? dataAnalysisMessage : `当前工作流先返回计划：${plan.message}`,
    steps: plan.steps,
    current_step: "已生成计划",
    next_step: "真实执行入口接入后即可继续执行；现在可以先完善参数或使用计划推进。",
    result_summary: draft.intent === "data_analysis" ? "已生成数据分析计划，执行入口仍在接入中。" : "已生成工作流计划。",
    technical: { execution_strategy: definition.execution_strategy, plan_only: true },
  };
}

export async function executeWorkflow(draft, api, options = {}) {
  if (!draft || draft?.status !== "confirmed") {
    return {
      ok: false,
      status: "pending_confirmation",
      intent: draft?.intent || "",
      title: draft?.title || "科研任务",
      message: "请先确认任务设置，我不会在确认前执行。",
      steps: ["等待用户确认"],
      current_step: "待确认",
      next_step: "点击确认开始，或继续修改参数。",
      result_summary: "任务等待确认。",
    };
  }
  const validation = validateWorkflowParams(draft.intent, draft.params || {});
  if (!validation.ok) {
    return {
      ok: false,
      status: "needs_input",
      intent: draft.intent,
      title: draft.title,
      message: validation.questions[0],
      steps: ["补充必要信息"],
      current_step: "需要补充信息",
      next_step: validation.questions[0],
      result_summary: "任务需要补充信息。",
    };
  }
  if (draft.intent === "literature_harvest_and_kb") return executeLiteratureWorkflow(draft, api);
  return executePlanOnlyWorkflow(draft, api, options);
}

export function formatWorkflowResult(result, { developerMode = false } = {}) {
  const clean = {
    ok: Boolean(result?.ok),
    status: result?.status || "failed",
    intent: result?.intent || "",
    title: result?.title || "科研任务",
    message: result?.message || "任务状态已更新。",
    steps: Array.isArray(result?.steps) ? result.steps : [],
    current_step: result?.current_step || "",
    next_step: result?.next_step || "",
    manual_queue_count: result?.manual_queue_count || 0,
    result_summary: resultSummary(result),
  };
  if (developerMode && result?.technical) clean.technical = result.technical;
  return clean;
}

export function workflowHistoryRecord(draft, result = {}) {
  const timestamp = nowIso();
  return {
    workflow_id: draft?.workflow_id || workflowId(draft?.intent || "workflow"),
    intent: draft?.intent || result?.intent || "",
    title: draft?.title || result?.title || "科研任务",
    params: { ...(draft?.params || {}) },
    status: result?.status || draft?.status || "draft",
    created_at: draft?.created_at || timestamp,
    updated_at: timestamp,
    result_summary: resultSummary(result),
    linked_conversation_id: draft?.linked_conversation_id || draft?.context?.conversationId || "",
  };
}

export function saveWorkflowHistory(projectId, record) {
  const key = historyKey(projectId || record?.params?.project_id);
  const existing = readJson(key, []);
  const nextRecord = { ...(record || {}), updated_at: record?.updated_at || nowIso() };
  const withoutDuplicate = existing.filter((item) => item.workflow_id !== nextRecord.workflow_id);
  const next = [nextRecord, ...withoutDuplicate].slice(0, 50);
  writeJson(key, next);
  if (typeof window !== "undefined") {
    window.dispatchEvent?.(new CustomEvent("researchos:workflow-history-updated", { detail: { projectId, workflow: nextRecord } }));
  }
  return nextRecord;
}

export function listWorkflowHistory(projectId) {
  return readJson(historyKey(projectId), []).sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
}

export function detectWorkflowIntent(message) {
  const text = normalize(message).toLowerCase();
  if (!text || text.includes("什么是阿尔茨海默症")) return null;
  const rules = [
    ["literature_harvest_and_kb", ["下载文献", "检索文献", "采集文献", "构建知识库", "查一下", "查一些", "方向的论文"]],
    ["ingest_uploaded_papers", ["学习我上传", "pdf 加入知识库", "解析这些文献"]],
    ["data_analysis", ["分析这个表格", "做统计", "做图", "分析数据"]],
    ["experiment_design", ["设计实验", "实验方案", "raw264.7"]],
    ["protocol_to_sop", ["整理 sop", "protocol", "生成实验步骤"]],
    ["writing_review", ["润色论文", "写结果", "模拟审稿", "整理讨论"]],
    ["failure_recovery", ["实验失败", "数据不对", "没有结果", "排查"]],
    ["weekly_report", ["生成周报", "总结本周", "下周计划"]],
  ];
  const matches = rules.filter(([, triggers]) => triggers.some((trigger) => text.includes(trigger.toLowerCase())));
  if (matches.length !== 1) return null;
  const intent = matches[0][0];
  const params = {};
  if (intent === "literature_harvest_and_kb") params.query = extractQuery(message);
  if (intent === "experiment_design") params.research_goal = message;
  if (intent === "data_analysis") params.analysis_goal = message;
  if (intent === "protocol_to_sop") params.source = message;
  if (intent === "writing_review") params.writing_goal = message;
  if (intent === "failure_recovery") params.failure_description = message;
  return { intent, title: WORKFLOW_DEFINITIONS[intent].user_title, params };
}

export function isWorkflowConfirmation(message) {
  const text = normalize(message).toLowerCase();
  return CONFIRM_WORDS.some((word) => text === word || text.includes(word));
}

export function isWorkflowCancellation(message) {
  const text = normalize(message).toLowerCase();
  return CANCEL_WORDS.some((word) => text.includes(word));
}
