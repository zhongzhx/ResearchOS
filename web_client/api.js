const BACKEND_PREFIX = "/api/backend";
const REQUEST_TIMEOUT_MS = 8000;
const MUTATION_TIMEOUT_MS = 60000;
export const DEFAULT_PROJECT_ID = "default";
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
  return `${path}${makeQuery({ project_id: projectId, ...params })}`;
}

function stableId(value, fallback) {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

function defaultChatSessionId(projectId) {
  const normalizedProjectId = String(projectId || DEFAULT_PROJECT_ID)
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${DEFAULT_CHAT_SESSION_ID}-${normalizedProjectId || DEFAULT_PROJECT_ID}`;
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
export const getTasks = (projectId) => apiGet(withProject("/research-os/tasks", projectId, { limit: 100 }));
export const getTask = (taskId) => apiGet(`/research-os/tasks/${encodeURIComponent(taskId)}`);
export const getReferences = (projectId, search = "") => apiGet(withProject("/research-os/references", projectId, { search, limit: 100 }));
export const getMemoryContext = (projectId, query = "Current project summary") =>
  apiGet(withProject("/research-os/memory/context", projectId, { query, limit: 30 }));
export const getMemoryReviewQueue = (projectId) => apiGet(withProject("/research-os/memory/review-queue", projectId, { status: "pending" }));
export const sendLegacyChat = (message, projectId, conversationId = "", sessionId = "") => {
  const safeProjectId = stableId(projectId, DEFAULT_PROJECT_ID);
  const safeConversationId = stableId(conversationId, stableId(sessionId, defaultChatSessionId(safeProjectId)));
  const safeSessionId = stableId(sessionId, safeConversationId);
  return apiPost("/research-os/agent/chat", {
    message,
    project_id: safeProjectId,
    conversation_id: safeConversationId,
    session_id: safeSessionId,
  });
};

// experimental: only call when the user explicitly enables dual-agent mode.
export const runCoordinator = (userQuery, projectId, conversationId = "", sessionId = "") => {
  const safeProjectId = stableId(projectId, DEFAULT_PROJECT_ID);
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

// demo_only: product feature contracts and demo previews. Real product execution is not wired from the UI.
export const getProductFeatures = () => apiGet("/api/product/features");
export const getProductFeature = (featureId) => apiGet(`/api/product/features/${encodeURIComponent(featureId)}`);
export const runProductFeature = (featureId, payload = {}) =>
  notConnected(featureId, "该产品功能入口已预留，当前后端尚未接入真实执行链路；请使用 demo_only 预览。");
export const runProductFeatureDemo = (featureId, projectId) => apiGet(withProject(`/api/product/features/${encodeURIComponent(featureId)}/demo`, projectId));
export const runProductDemoFlow = (projectId) => apiGet(withProject("/api/demo/product-flow", projectId));

// experimental: skill catalog, pipeline registry, route tester, and generated skill review.
export const getSkillCatalog = () => apiGet("/api/skills/catalog");
export const getSkillPipelines = () => apiGet("/api/skills/pipelines");
export const routeSkillQuery = (query, projectId) => apiPost("/api/skills/route", { user_query: query, project_id: projectId });
export const getResolverHealth = () => apiGet("/api/skills/resolver/check");
export const getPendingSkills = () => apiGet("/api/self-evolution/pending-skills");
export const activatePendingSkill = (skillName) => apiPost(`/api/self-evolution/skills/${encodeURIComponent(skillName)}/activate`, {});
export const rejectPendingSkill = (skillName, reason) => apiPost(`/api/self-evolution/skills/${encodeURIComponent(skillName)}/reject`, { reason });

// experimental: MemoryOS read/actions are gated by RESEARCHOS_MEMORYOS_ENABLED.
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
export const getEvidenceReview = (projectId) => apiGet(`/research-os/projects/${encodeURIComponent(projectId || "")}/evidence-review`);
export const getClaimReview = (projectId) => apiGet(`/research-os/projects/${encodeURIComponent(projectId || "")}/claims/review`);
export const getRuntimeStatus = (projectId) => apiGet(withProject("/research-os/runtime/status", projectId));
export const getSchedulerStatus = (projectId) => apiGet(withProject("/research-os/agent/scheduler/status", projectId));
export const getDashboard = () => apiGet("/research-os/dashboard");

// legacy_stable: project/task lifecycle mutations backed by research_os_mvp.
export const createProject = (payload) => apiPost("/research-os/projects", payload);
export const updateProject = (projectId, payload) => apiPut(`/research-os/projects/${encodeURIComponent(projectId)}`, payload);
export const archiveProject = (projectId) => apiPost(`/research-os/projects/${encodeURIComponent(projectId)}/archive`, {});
export const unarchiveProject = (projectId) => apiPost(`/research-os/projects/${encodeURIComponent(projectId)}/unarchive`, {});
export const clearProject = (projectId) => apiPost(`/research-os/projects/${encodeURIComponent(projectId)}/clear`, {});
export const purgeProject = (projectId) => apiPost(`/research-os/projects/${encodeURIComponent(projectId)}/purge`, {});
export const createTask = (payload) => apiPost("/research-os/tasks", payload);
export const runTask = (taskId, payload = {}) => apiPost(`/research-os/tasks/${encodeURIComponent(taskId)}/run`, payload);
export const cancelTask = (taskId, payload = {}) => apiPost(`/research-os/tasks/${encodeURIComponent(taskId)}/cancel`, payload);
export const parseNaturalLanguageTask = (payload) => apiPost("/research-os/tasks/parse-natural-language", payload);
export const createTaskFromNaturalLanguage = (payload) => apiPost("/research-os/tasks/create-from-natural-language", payload);
export const agentHeartbeat = (payload = {}) => apiPost("/agent/messages", payload);
export const watchProject = (payload) => apiPost("/research-os/agent/watch-project", payload);
export const runScheduler = (payload = {}) => apiPost("/research-os/agent/scheduler/run", payload);
export const acceptAgentFeedItem = (itemId) => apiPost(`/research-os/agent-feed/${encodeURIComponent(itemId)}/accept`, {});
export const dismissAgentFeedItem = (itemId) => apiPost(`/research-os/agent-feed/${encodeURIComponent(itemId)}/dismiss`, {});
export const getLegacySkills = () => apiGet("/research-os/skills");
export const upsertLegacySkill = (payload) => apiPost("/research-os/skills", payload);
export const runLegacySkill = (skillId, payload = {}) => apiPost(`/research-os/skills/${encodeURIComponent(skillId)}/run`, payload);
export const simulatePromptRouting = (payload) => apiPost("/research-os/prompt-routing/simulate", payload);
export const promoteExecutionMemory = (memoryId, payload = {}) => apiPost(`/research-os/execution-memory/${encodeURIComponent(memoryId)}/promote`, payload);

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
export const cancelLiteratureSearchTask = (taskId) => apiPost(`/research-os/literature/search-tasks/${encodeURIComponent(taskId)}/cancel`, {});
export const expandLiteratureQuery = (payload) => apiPost("/research-os/literature/expand-query", payload);
export const mineLiteratureKeywords = (payload) => apiPost("/research-os/literature/keyword-mine", payload);
export const runLiteratureSearch = (payload) => apiPost("/research-os/literature/search", payload);
export const createPaperRequest = (payload) => apiPost("/research-os/literature/paper-requests", payload);
export const generatePaperRequests = (payload) => apiPost("/research-os/literature/paper-requests/generate", payload);
export const processPaperRequestWatchFolder = (payload) => apiPost("/research-os/literature/paper-requests/process-watch-folder", payload);
export const upsertReference = (payload) => apiPost("/research-os/references", payload);
export const tagReference = (referenceId, payload) => apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/tag`, payload);
export const noteReference = (referenceId, payload) => apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/note`, payload);
export const markReferenceImportant = (referenceId, payload = {}) => apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/mark-important`, payload);
export const excludeReference = (referenceId, payload = {}) => apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/exclude`, payload);
export const linkReference = (referenceId, payload) => apiPost(`/research-os/references/${encodeURIComponent(referenceId)}/link`, payload);
export const buildKnowledgeBase = (payload) => apiPost("/research-os/knowledge-base/build", payload);
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
export const runWorkflow = (workflowId, payload = {}) => apiPost(`/research-os/workflows/${encodeURIComponent(workflowId)}/run`, payload);
export const approveWorkflowStep = (stepId, payload = {}) => apiPost(`/research-os/workflow-steps/${encodeURIComponent(stepId)}/approve`, payload);
export const detectConflicts = (payload) => apiPost("/research-os/conflicts/detect", payload);
export const createReport = (payload) => apiPost("/research-os/reports", payload);
export const extractReportClaims = (reportId, payload = {}) => apiPost(`/research-os/reports/${encodeURIComponent(reportId)}/claims`, payload);
export const createClaim = (payload) => apiPost("/research-os/claims", payload);
export const confirmClaim = (claimId, payload = {}) => apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/confirm`, payload);
export const rejectClaim = (claimId, payload = {}) => apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/reject`, payload);
export const requestMoreClaimEvidence = (claimId, payload = {}) => apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/needs-more-evidence`, payload);
export const linkClaimEvidence = (claimId, payload) => apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/link-evidence`, payload);
export const unlinkClaimEvidence = (claimId, payload) => apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/unlink-evidence`, payload);
export const supersedeClaim = (claimId, payload) => apiPost(`/research-os/claims/${encodeURIComponent(claimId)}/supersede`, payload);
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
