const BACKEND_PREFIX = "/api/backend";
const REQUEST_TIMEOUT_MS = 8000;
const MUTATION_TIMEOUT_MS = 60000;
const DEFAULT_CHAT_SESSION_ID = "default-chat-session";

function safeError(error) {
  if (!error) return "请求失败";
  if (error.name === "AbortError") return "请求超时，请稍后重试";
  const message = String(error.message || error).replace(/(api[_-]?key|token|secret|password|cookie|authorization)(\s*[:=]\s*)[^\s,;]+/gi, "$1$2[redacted]");
  return message.length > 180 ? `${message.slice(0, 177)}...` : message;
}

function makeQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

function withProject(path, projectId, params = {}) {
  return `${path}${makeQuery({ project_id: requireProjectId(projectId), ...params })}`;
}

function stableId(value, fallback) {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

export function requireProjectId(projectId) {
  const normalized = String(projectId || "").trim();
  if (!normalized) throw new Error("project_id is required");
  return normalized;
}

function projectPath(projectId, suffix = "") {
  return `/research-os/projects/${encodeURIComponent(requireProjectId(projectId))}${suffix}`;
}

function defaultChatSessionId(projectId) {
  const normalizedProjectId = requireProjectId(projectId)
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${DEFAULT_CHAT_SESSION_ID}-${normalizedProjectId}`;
}

async function request(method, path, body, timeoutMs = REQUEST_TIMEOUT_MS) {
  if (window.location.protocol === "file:") {
    return {
      ok: false,
      data: null,
      error: "请通过 Electron 或本地服务启动 AURA Research，直接打开 web_client/index.html 无法连接后端。",
      status: 0,
    };
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BACKEND_PREFIX}${path}`, {
      method,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let payload = {};
    let parsedJson = true;
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      parsedJson = false;
      payload = {};
    }
    if (!parsedJson) {
      return { ok: false, data: null, error: response.ok ? "响应不是有效 JSON" : `HTTP ${response.status}`, status: response.status };
    }
    const error = payload?.error || payload?.message || (response.ok ? "" : `HTTP ${response.status}`);
    const ok = response.ok && payload?.ok !== false;
    return { ok, data: payload, error: ok ? "" : String(error), status: response.status };
  } catch (error) {
    return { ok: false, data: null, error: safeError(error), status: 0 };
  } finally {
    clearTimeout(timeout);
  }
}

function notConnected(feature, detail = "该功能入口已预留，当前后端尚未接入真实执行链路。") {
  return Promise.resolve({
    ok: false,
    data: { ok: false, status: "not_connected", feature, detail },
    error: detail,
    status: 0,
  });
}

export function apiGet(path) {
  return request("GET", path, undefined, REQUEST_TIMEOUT_MS);
}

export function apiPost(path, body = {}) {
  return request("POST", path, body, MUTATION_TIMEOUT_MS);
}

export function apiPut(path, body = {}) {
  return request("PUT", path, body, MUTATION_TIMEOUT_MS);
}

export function apiDelete(path) {
  return request("DELETE", path, undefined, MUTATION_TIMEOUT_MS);
}

// legacy_stable: MVP runtime and ResearchOS local data APIs.
export const getHealth = () => apiGet("/health");
export const getProjects = () => apiGet("/research-os/projects");
export const getProjectStatus = (projectId) => apiGet(projectPath(projectId, "/status"));
export const getProjectPaths = (projectId) => apiGet(projectPath(projectId, "/paths"));
export const getWorkspaceState = (projectId) => apiGet(withProject("/research-os/workspace-state", projectId));
export const getTasks = (projectId) => apiGet(withProject("/research-os/tasks", projectId, { limit: 100 }));
export const getTask = (projectId, taskId) => apiGet(withProject(`/research-os/tasks/${encodeURIComponent(taskId)}`, projectId));
export const getReferences = (projectId, search = "") => apiGet(withProject("/research-os/references", projectId, { search, limit: 100 }));
export const getMemoryContext = (projectId, query = "Current project summary") =>
  apiGet(withProject("/research-os/memory/context", projectId, { query, limit: 30 }));
export const getMemoryReviewQueue = (projectId) => apiGet(withProject("/research-os/memory/review-queue", projectId, { status: "pending" }));
export const sendLegacyChat = (message, projectId, conversationId = "", sessionId = "") => {
  const safeProjectId = requireProjectId(projectId);
  const safeConversationId = stableId(conversationId, stableId(sessionId, defaultChatSessionId(safeProjectId)));
  const safeSessionId = stableId(sessionId, safeConversationId);
  return apiPost("/research-os/agent/chat", {
    message,
    project_id: safeProjectId,
    conversation_id: safeConversationId,
    session_id: safeSessionId,
  });
};

// Internal coordinator entry; only call after the user enables developer controls.
export const runCoordinator = (userQuery, projectId, conversationId = "", sessionId = "") => {
  const safeProjectId = requireProjectId(projectId);
  const safeConversationId = stableId(conversationId, stableId(sessionId, defaultChatSessionId(safeProjectId)));
  const safeSessionId = stableId(sessionId, safeConversationId);
  return apiPost("/api/agents/coordinator/run", {
    user_query: userQuery,
    project_id: safeProjectId,
    conversation_id: safeConversationId,
    session_id: safeSessionId,
  });
};
export const runDualAgentDemo = (projectId) => apiGet(withProject("/api/demo/dual-agent", projectId));

// Product feature contracts and previews are developer-facing until real execution is connected.
export const getProductFeatures = () => apiGet("/api/product/features");
export const getProductFeature = (featureId) => apiGet(`/api/product/features/${encodeURIComponent(featureId)}`);
export const runProductFeature = (featureId, payload = {}) =>
  notConnected(featureId, "该产品功能入口已预留，当前后端尚未接入真实执行链路；请在功能导航中查看预览。");
export const runProductFeatureDemo = (featureId, projectId) => apiGet(withProject(`/api/product/features/${encodeURIComponent(featureId)}/demo`, projectId));
export const runProductDemoFlow = (projectId) => apiGet(withProject("/api/demo/product-flow", projectId));

// Developer console APIs for catalogs, workflow registry, route checks, and generated-skill review.
export const getSkillCatalog = () => apiGet("/api/skills/catalog");
export const getSkillPipelines = () => apiGet("/api/skills/pipelines");
export const routeSkillQuery = (query, projectId) => apiPost("/api/skills/route", { user_query: query, project_id: projectId });
export const getResolverHealth = () => apiGet("/api/skills/resolver/check");
export const getPendingSkills = () => apiGet("/api/self-evolution/pending-skills");
export const activatePendingSkill = (skillName) => apiPost(`/api/self-evolution/skills/${encodeURIComponent(skillName)}/activate`, {});
export const rejectPendingSkill = (skillName, reason) => apiPost(`/api/self-evolution/skills/${encodeURIComponent(skillName)}/reject`, { reason });

// MemoryOS read/actions are gated by RESEARCHOS_MEMORYOS_ENABLED.
export const getWorkingMemory = (projectId) => apiGet(withProject("/api/memory/working", projectId));
export const getCognitiveState = (projectId) => apiGet(withProject("/api/memory/cognitive-state", projectId));
export const refreshCognitiveState = (projectId, taskId = "") => apiPost("/api/memory/cognitive-state/refresh", { project_id: projectId, task_id: taskId });
export const getMemoryEpisodes = (projectId) => apiGet(withProject("/api/memory/episodes", projectId, { limit: 20 }));
export const getMemoryItems = (projectId) => apiGet(withProject("/api/memory/items", projectId, { limit: 50 }));
export const searchMemoryOs = (projectId, query) => apiPost("/api/memory/search", { project_id: projectId, query });
export const getMemoryHealth = (projectId) => apiGet(withProject("/api/memory/health", projectId));
export const runMemoryMaintenance = (projectId, dryRun = true) => apiPost("/api/memory/maintenance/run", { project_id: projectId, dry_run: dryRun });
export const getMemoryEvents = (projectId) => apiGet(withProject("/api/memory/events", projectId, { limit: 100 }));
export const checkAutonomousLearning = (projectId) => apiPost("/api/memory/autonomous-learning/check", { project_id: projectId, dry_run: true });

// legacy_stable: execution visibility and ResearchOS project records.
export const getSkillRuns = (projectId) => apiGet(withProject("/research-os/skill-runs", projectId, { limit: 100 }));
export const getExecutionMemory = (projectId) => apiGet(withProject("/research-os/execution-memory", projectId, { limit: 100 }));
export const getClaims = (projectId) => apiGet(withProject("/research-os/claims", projectId));
export const getDecisions = (projectId) => apiGet(withProject("/research-os/decisions", projectId));
export const getFailures = (projectId) => apiGet(withProject("/research-os/failures", projectId));
export const getProtocols = (projectId) => apiGet(withProject("/research-os/protocols", projectId));
export const getReports = (projectId) => apiGet(withProject("/research-os/reports", projectId));
export const getRelationships = (projectId) => apiGet(withProject("/research-os/relationships", projectId));
export const getFiles = (projectId) => apiGet(withProject("/research-os/files", projectId));
export const getProjectArtifacts = (projectId, sourceType = "") => apiGet(projectPath(projectId, `/artifacts${makeQuery({ source_type: sourceType })}`));
export const getArtifactOpenInfo = (projectId, artifactId) => apiGet(projectPath(projectId, `/artifacts/${encodeURIComponent(artifactId)}/open-info`));
export const registerArtifactFile = (payload) => apiPost("/research-os/files/register", payload);
export const uploadArtifactFile = (payload) => apiPost("/research-os/files/upload", payload);
export const ingestArtifactFile = (projectId, artifactId, payload = {}) =>
  apiPost(`/research-os/files/${encodeURIComponent(artifactId)}/ingest`, { ...payload, project_id: requireProjectId(projectId) });
export const deleteArtifactFile = (projectId, artifactId, payload = {}) =>
  apiPost(`/research-os/files/${encodeURIComponent(artifactId)}/delete`, { ...payload, project_id: requireProjectId(projectId) });
export const getWorkflowRegistry = () => apiGet("/research-os/workflow-registry");
export const planWorkflowExecution = (payload) => apiPost("/research-os/workflow-executions/plan", payload);
export const executeWorkflowExecution = (payload) => apiPost("/research-os/workflow-executions", payload);
export const routeChatWorkflow = (payload) => apiPost("/research-os/workflow-executions/chat-route", payload);
export const getEvidenceReview = (projectId) => apiGet(projectPath(projectId, "/evidence-review"));
export const getClaimReview = (projectId) => apiGet(projectPath(projectId, "/claims/review"));
export const getRuntimeStatus = (projectId) => apiGet(withProject("/research-os/runtime/status", projectId));
export const getSchedulerStatus = (projectId) => apiGet(withProject("/research-os/agent/scheduler/status", projectId));
export const getDashboard = () => apiGet("/research-os/dashboard");

// legacy_stable: project/task lifecycle mutations backed by research_os_mvp.
export const createProject = (payload) => apiPost("/research-os/projects", payload);
export const archiveProjectArtifact = (payload) => apiPost("/research-os/artifacts", payload);
export const updateProject = (projectId, payload) => apiPut(projectPath(projectId), payload);
export const archiveProject = (projectId) => apiPost(projectPath(projectId, "/archive"), {});
export const unarchiveProject = (projectId) => apiPost(projectPath(projectId, "/unarchive"), {});
export const clearProject = (projectId, payload = {}) => apiPost(projectPath(projectId, "/clear"), payload);
export const purgeProject = (projectId, payload = {}) => apiPost(projectPath(projectId, "/purge"), payload);
export const createTask = (payload) => apiPost("/research-os/tasks", payload);
export const runTask = (projectId, taskId, payload = {}) =>
  apiPost(`/research-os/tasks/${encodeURIComponent(taskId)}/run`, { ...payload, project_id: requireProjectId(projectId) });
export const cancelTask = (projectId, taskId, payload = {}) =>
  apiPost(`/research-os/tasks/${encodeURIComponent(taskId)}/cancel`, { ...payload, project_id: requireProjectId(projectId) });
export const parseNaturalLanguageTask = (payload) => apiPost("/research-os/tasks/parse-natural-language", payload);
export const createTaskFromNaturalLanguage = (payload) => apiPost("/research-os/tasks/create-from-natural-language", payload);
export const agentHeartbeat = (payload = {}) => apiPost("/agent/messages", payload);
export const watchProject = (payload) => apiPost("/research-os/agent/watch-project", payload);
export const runScheduler = (payload = {}) => apiPost("/research-os/agent/scheduler/run", payload);
export const acceptAgentFeedItem = (projectId, itemId) =>
  apiPost(`/research-os/agent-feed/${encodeURIComponent(itemId)}/accept`, { project_id: requireProjectId(projectId) });
export const dismissAgentFeedItem = (projectId, itemId) =>
  apiPost(`/research-os/agent-feed/${encodeURIComponent(itemId)}/dismiss`, { project_id: requireProjectId(projectId) });
export const getLegacySkills = () => apiGet("/research-os/skills");
export const upsertLegacySkill = (payload) => apiPost("/research-os/skills", payload);
export const runLegacySkill = (skillId, payload = {}) => apiPost(`/research-os/skills/${encodeURIComponent(skillId)}/run`, payload);
export const simulatePromptRouting = (payload) => apiPost("/research-os/prompt-routing/simulate", payload);
export const promoteExecutionMemory = (projectId, memoryId, payload = {}) =>
  apiPost(`/research-os/execution-memory/${encodeURIComponent(memoryId)}/promote`, { ...payload, project_id: requireProjectId(projectId) });

// legacy_stable: RAG, literature, reference, and evidence read APIs.
export const getReferenceChunks = (projectId) => apiGet(withProject("/research-os/reference-chunks", projectId, { limit: 100 }));
export const getKnowledgeBaseEntries = (projectId) => apiGet(withProject("/research-os/knowledge-base-entries", projectId, { limit: 100 }));
export const getRagQueries = (projectId) => apiGet(withProject("/research-os/rag-queries", projectId, { limit: 50 }));
export const getLiteratureSearchTasks = (projectId) => apiGet(withProject("/research-os/literature/search-tasks", projectId, { limit: 50 }));
export const getPaperRequests = (projectId) => apiGet(withProject("/research-os/literature/paper-requests", projectId, { limit: 50 }));
export const getUnmatchedPdfs = (projectId) => apiGet(withProject("/research-os/literature/unmatched-pdfs", projectId, { limit: 50 }));
export const getAgentFeed = (projectId) => apiGet(withProject("/research-os/agent-feed", projectId, { limit: 50 }));
export const getWorkflowBoard = (projectId) => apiGet(withProject("/research-os/workflow-board", projectId));

// implemented: LLM settings API backed by backend.researchos.settings.
export const getLlmSettings = () => apiGet("/api/settings/llm");
export const saveLlmSettings = (payload) => apiPost("/api/settings/llm", payload);
export const testLlmSettings = (payload) => apiPost("/api/settings/llm/test", payload);

// legacy_stable: RAG, literature, reference, and evidence mutation APIs.
export const createLiteratureSearchTask = (payload) => apiPost("/research-os/literature/search-tasks", payload);
export const cancelLiteratureSearchTask = (projectId, taskId) =>
  apiPost(`/research-os/literature/search-tasks/${encodeURIComponent(taskId)}/cancel`, { project_id: requireProjectId(projectId) });
export const expandLiteratureQuery = (payload) => apiPost("/research-os/literature/expand-query", payload);
export const mineLiteratureKeywords = (payload) => apiPost("/research-os/literature/keyword-mine", payload);
export const runLiteratureSearch = (payload) => apiPost("/research-os/literature/search", payload);
export const createPaperRequest = (payload) => apiPost("/research-os/literature/paper-requests", payload);
export const generatePaperRequests = (payload) => apiPost("/research-os/literature/paper-requests/generate", payload);
export const processPaperRequestWatchFolder = (payload) => apiPost("/research-os/literature/paper-requests/process-watch-folder", payload);
export const upsertReference = (payload) => apiPost("/research-os/references", payload);
export const tagReference = (projectId, referenceId, payload) =>
  apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/tag`, { ...payload, project_id: requireProjectId(projectId) });
export const noteReference = (projectId, referenceId, payload) =>
  apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/note`, { ...payload, project_id: requireProjectId(projectId) });
export const markReferenceImportant = (projectId, referenceId, payload = {}) =>
  apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/mark-important`, { ...payload, project_id: requireProjectId(projectId) });
export const excludeReference = (projectId, referenceId, payload = {}) =>
  apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/exclude`, { ...payload, project_id: requireProjectId(projectId) });
export const linkReference = (projectId, referenceId, payload) =>
  apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/link`, { ...payload, project_id: requireProjectId(projectId) });
export const buildKnowledgeBase = (payload) => apiPost("/research-os/knowledge-base/build", payload);

function workflowPrompt(intent, params) {
  return [
    `请执行用户确认过的科研工作流：${intent}`,
    ...Object.entries(params || {}).map(([key, value]) => `${key}: ${value}`),
    "请用中文返回执行进度、成功/失败原因、下一步建议，不要展示内部技术对象。",
  ].join("\n");
}

function workflowNotConnected(intent, detail = "真实执行入口尚未接入") {
  return {
    ok: false,
    status: "not_connected",
    intent,
    title: "暂不能执行",
    message: `当前只能生成执行计划，${detail}。`,
    steps: ["已完成用户确认", "尚未连接真实执行入口"],
    next_step: "可以先在工作台或对话中继续完善参数。",
    technical: { intent, detail },
  };
}

function failedWorkflowStep(intent, label, result) {
  const status = result?.data?.status || "";
  if (status === "not_connected" || status === "partial" || status === "demo_only") return workflowNotConnected(intent);
  return {
    ok: false,
    status: "failed",
    intent,
    title: "任务执行失败",
    message: `${label}没有完成：${result?.error || result?.data?.message || "后端没有返回成功状态"}`,
    steps: [`${label}失败`],
    next_step: "请检查项目、文件或后端服务状态后重试。",
    technical: result?.data || result,
  };
}

function manualQueueCount(result) {
  const payload = result?.data || {};
  const rows = payload.paper_requests || payload.requests || payload.manual_queue || [];
  return Array.isArray(rows) ? rows.length : Number(payload.manual_queue_count || 0);
}

export async function executeConfirmedWorkflow(intent, params = {}, context = {}) {
  const projectId = requireProjectId(params.project_id || context.projectId);
  if (intent === "literature_harvest_and_kb") {
    const payload = {
      project_id: projectId,
      query: params.topic || params.query,
      keywords: [params.topic || params.query].filter(Boolean),
      max_results: Number(params.max_papers || 20),
      oa_only: params.oa_only !== false,
      non_oa_policy: params.non_oa_policy || "manual_queue",
    };
    const createTask = await createLiteratureSearchTask(payload);
    if (!createTask.ok) return failedWorkflowStep(intent, "创建文献采集任务", createTask);
    const search = await runLiteratureSearch(payload);
    if (!search.ok) return failedWorkflowStep(intent, "检索文献", search);
    const paperRequests = await generatePaperRequests({ project_id: projectId });
    if (!paperRequests.ok) return failedWorkflowStep(intent, "整理手动下载队列", paperRequests);
    let kb = null;
    if (params.build_kb !== false) {
      kb = await buildKnowledgeBase({ project_id: projectId });
      if (!kb.ok) return failedWorkflowStep(intent, "构建知识库", kb);
    }
    return {
      ok: true,
      status: "completed",
      intent,
      title: "文献采集步骤已完成",
      message: "已创建文献采集任务，并完成当前可执行步骤。",
      run_id: createTask.data?.id || createTask.data?.task_id || "",
      steps: ["创建文献采集任务", "检索文献", "整理手动下载队列", params.build_kb === false ? "跳过知识库构建" : "构建知识库"],
      manual_queue_count: manualQueueCount(paperRequests),
      next_step: "你可以在资料库查看文献和知识条目，手动补充无法开放获取的全文。",
      technical: { createTask: createTask.data, search: search.data, paperRequests: paperRequests.data, kb: kb?.data },
    };
  }

  const execution = await executeWorkflowExecution({
    project_id: projectId,
    intent,
    params,
    conversation_id: context.conversationId || "",
  });
  const result = execution?.data || {};
  if (!execution.ok || !result.ok) {
    return {
      ...workflowNotConnected(intent, result.message || execution.error || "真实 workflow service 未返回可验证结果"),
      status: result.status || "failed",
      run_id: result.run_id || "",
      artifacts: Array.isArray(result.artifacts) ? result.artifacts : [],
      technical: result.developer_diagnostics || result,
    };
  }
  return result;
}
export const queryResearchOsRag = (payload) => apiPost("/research-os/rag/query", payload);
export const queryResearchContext = (payload) => apiPost("/research-os/research-context/query", payload);
export const searchResearchOsMemory = (payload) => apiPost("/research-os/memory/search", payload);
export const mergeResearchOsMemory = (payload) => apiPost("/research-os/memory/merge", payload);
export const extractExperimentMemory = (payload) => apiPost("/research-os/memory/extract-experiment", payload);
export const submitUserCorrection = (payload) => apiPost("/research-os/memory/user-correction", payload);
export const registerFile = (payload) => apiPost("/research-os/files", payload);
export const runExtraction = (payload) => apiPost("/memory/extract", payload);
export const parseProtocolText = (payload) => apiPost("/research-os/protocols/parse", payload);
export const storeProtocol = (payload) => apiPost("/research-os/protocols", payload);
export const generateExecutionPackage = (payload) => apiPost("/research-os/protocol-execution-package", payload);
export const runCalculator = (payload) => apiPost("/research-os/calculator", payload);
export const createWorkflow = (payload) => apiPost("/research-os/workflows", payload);
export const runWorkflow = (projectId, workflowId, payload = {}) =>
  apiPost(`/research-os/workflows/${encodeURIComponent(workflowId)}/run`, { ...payload, project_id: requireProjectId(projectId) });
export const approveWorkflowStep = (projectId, stepId, payload = {}) =>
  apiPost(`/research-os/workflow-steps/${encodeURIComponent(stepId)}/approve`, { ...payload, project_id: requireProjectId(projectId) });
export const detectConflicts = (payload) => apiPost("/research-os/conflicts/detect", payload);
export const createReport = (payload) => apiPost("/research-os/reports", payload);
export const extractReportClaims = (projectId, reportId, payload = {}) =>
  apiPost(`/research-os/reports/${encodeURIComponent(reportId)}/claims`, { ...payload, project_id: requireProjectId(projectId) });
export const createClaim = (payload) => apiPost("/research-os/claims", payload);
export const confirmClaim = (projectId, claimId, payload = {}) =>
  apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/confirm`, { ...payload, project_id: requireProjectId(projectId) });
export const rejectClaim = (projectId, claimId, payload = {}) =>
  apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/reject`, { ...payload, project_id: requireProjectId(projectId) });
export const requestMoreClaimEvidence = (projectId, claimId, payload = {}) =>
  apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/needs-more-evidence`, { ...payload, project_id: requireProjectId(projectId) });
export const linkClaimEvidence = (projectId, claimId, payload) =>
  apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/link-evidence`, { ...payload, project_id: requireProjectId(projectId) });
export const unlinkClaimEvidence = (projectId, claimId, payload) =>
  apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/unlink-evidence`, { ...payload, project_id: requireProjectId(projectId) });
export const supersedeClaim = (projectId, claimId, payload) =>
  apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/supersede`, { ...payload, project_id: requireProjectId(projectId) });
export const queryRelationships = (payload) => apiPost("/research-os/relationships/query", payload);
export const validateResearchOsPayload = (payload) => apiPost("/research-os/validator", payload);
export const createClaimReferenceLink = (payload) => apiPost("/research-os/claim-reference-links", payload);
export const writeConclusion = (payload) => apiPost("/research-os/conclusions", payload);
export const writeDecision = (payload) => apiPost("/research-os/decisions", payload);
export const writeFailureLog = (payload) => apiPost("/research-os/failure-logs", payload);
export const writeFailure = (payload) => apiPost("/research-os/failures", payload);
export const ingestExperimentLog = (payload) => apiPost("/research-os/experiment-logs/ingest", payload);
export const generateRetrospective = (payload) => apiPost("/research-os/retrospectives/generate", payload);
export const assistWriting = (payload) => apiPost("/research-os/writing/assist", payload);
export const upsertWeeklyDigestConfig = (payload) => apiPost("/research-os/weekly-digest/configs", payload);
export const generateWeeklyDigest = (payload) => apiPost("/research-os/weekly-digest/generate", payload);
export const upsertAgentMemory = (payload) => apiPost("/research-os/agent-memory", payload);
export const parseKitTemplate = (payload) => apiPost("/research-os/kit-templates/parse", payload);
export const createMemory = (payload) => apiPost("/memory/create", payload);
export const retrieveMemory = (payload) => apiPost("/memory/retrieve", payload);
export const buildMemoryContext = (payload) => apiPost("/memory/context", payload);
export const consolidateMemory = (payload) => apiPost("/memory/consolidate", payload);
export const extractMemory = (payload) => apiPost("/memory/extract", payload);
export const archiveMemory = (payload) => apiPost("/memory/archive", payload);
export const createMemoryProject = (payload) => apiPost("/memory/projects", payload);
export const updateMemoryProject = (projectId, payload) => apiPut(`/memory/projects/${encodeURIComponent(projectId)}`, payload);
export const createResearchInterest = (payload) => apiPost("/research-interests", payload);
export const updateResearchInterest = (interestId, payload) => apiPut(`/research-interests/${encodeURIComponent(interestId)}`, payload);
export const deleteResearchInterest = (interestId) => apiDelete(`/research-interests/${encodeURIComponent(interestId)}`);
export const createFailureRecord = (payload) => apiPost("/failure-records", payload);
export const updateFailureRecord = (recordId, payload) => apiPut(`/failure-records/${encodeURIComponent(recordId)}`, payload);
export const deleteFailureRecord = (recordId) => apiDelete(`/failure-records/${encodeURIComponent(recordId)}`);
export const matchFailureRecords = (payload) => apiPost("/failure-records/match", payload);
export const extractProtocol = (payload) => apiPost("/protocol-extract", payload);
export const generateSop = (payload) => apiPost("/sop-generate", payload);
export const runPeerReview = (payload) => apiPost("/peer-review", payload);
export const parseScientificData = (payload) => apiPost("/data-parse", payload);
export const generateResultNarrative = (payload) => apiPost("/result-narrative", payload);
export const ingestRagDocument = (payload) => apiPost("/rag/documents", payload);
export const ingestRagPdfs = (payload) => apiPost("/rag/ingest-pdfs", payload);
export const queryLegacyRag = (payload) => apiPost("/rag/query", payload);
export const createSearchJob = (payload) => apiPost("/search-jobs", payload);
export const queryKnowledgeBase = (payload) => apiPost("/kb/query", payload);
export const sendFeedback = (payload) => apiPost("/feedback", payload);
export const getArticles = (projectName) => apiGet(`/articles${makeQuery({ project_name: projectName })}`);
export const getArticle = (articleId, projectName) => apiGet(`/articles/${encodeURIComponent(articleId)}${makeQuery({ project_name: projectName })}`);
export const getBrowserLearning = (projectName) => apiGet(`/browser-learning${makeQuery({ project_name: projectName })}`);
