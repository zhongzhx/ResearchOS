const BACKEND_PREFIX = "/api/backend";

function safeError(error) {
  if (!error) return "Request failed";
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

async function request(method, path, body) {
  try {
    const response = await fetch(`${BACKEND_PREFIX}${path}`, {
      method,
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
      return { ok: false, data: null, error: response.ok ? "invalid_json_response" : `HTTP ${response.status}`, status: response.status };
    }
    const error = payload?.error || payload?.message || (response.ok ? "" : `HTTP ${response.status}`);
    const ok = response.ok && payload?.ok !== false;
    return { ok, data: payload, error: ok ? "" : String(error), status: response.status };
  } catch (error) {
    return { ok: false, data: null, error: safeError(error), status: 0 };
  }
}

export function apiGet(path) {
  return request("GET", path);
}

export function apiPost(path, body = {}) {
  return request("POST", path, body);
}

export const getHealth = () => apiGet("/health");
export const getProjects = () => apiGet("/research-os/projects");
export const getTasks = (projectId) => apiGet(withProject("/research-os/tasks", projectId, { limit: 100 }));
export const getTask = (taskId) => apiGet(`/research-os/tasks/${encodeURIComponent(taskId)}`);
export const getReferences = (projectId, search = "") => apiGet(withProject("/research-os/references", projectId, { search, limit: 100 }));
export const getMemoryContext = (projectId, query = "Current project summary") =>
  apiGet(withProject("/research-os/memory/context", projectId, { query, limit: 30 }));
export const getMemoryReviewQueue = (projectId) => apiGet(withProject("/research-os/memory/review-queue", projectId, { status: "pending" }));
export const sendLegacyChat = (message, projectId, conversationId = "") =>
  apiPost("/research-os/agent/chat", { message, project_id: projectId, conversation_id: conversationId });
export const runCoordinator = (userQuery, projectId) => apiPost("/api/agents/coordinator/run", { user_query: userQuery, project_id: projectId });
export const runDualAgentDemo = (projectId) => apiGet(withProject("/api/demo/dual-agent", projectId));
export const getProductFeatures = () => apiGet("/api/product/features");
export const getProductFeature = (featureId) => apiGet(`/api/product/features/${encodeURIComponent(featureId)}`);
export const runProductFeature = (featureId, payload = {}) => apiPost(`/api/product/features/${encodeURIComponent(featureId)}/run`, payload);
export const runProductFeatureDemo = (featureId, projectId) => apiGet(withProject(`/api/product/features/${encodeURIComponent(featureId)}/demo`, projectId));
export const runProductDemoFlow = (projectId) => apiPost("/api/demo/product-flow/run", { project_id: projectId });
export const getSkillCatalog = () => apiGet("/api/skills/catalog");
export const getSkillPipelines = () => apiGet("/api/skills/pipelines");
export const routeSkillQuery = (query, projectId) => apiPost("/api/skills/route", { user_query: query, project_id: projectId });
export const getResolverHealth = () => apiGet("/api/skills/resolver/check");
export const getPendingSkills = () => apiGet("/api/self-evolution/pending-skills");
export const activatePendingSkill = (skillName) => apiPost(`/api/self-evolution/skills/${encodeURIComponent(skillName)}/activate`, {});
export const rejectPendingSkill = (skillName, reason) => apiPost(`/api/self-evolution/skills/${encodeURIComponent(skillName)}/reject`, { reason });
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
export const getReferenceChunks = (projectId) => apiGet(withProject("/research-os/reference-chunks", projectId, { limit: 100 }));
export const getKnowledgeBaseEntries = (projectId) => apiGet(withProject("/research-os/knowledge-base-entries", projectId, { limit: 100 }));
export const getRagQueries = (projectId) => apiGet(withProject("/research-os/rag-queries", projectId, { limit: 50 }));
export const getLiteratureSearchTasks = (projectId) => apiGet(withProject("/research-os/literature/search-tasks", projectId, { limit: 50 }));
export const getPaperRequests = (projectId) => apiGet(withProject("/research-os/literature/paper-requests", projectId, { limit: 50 }));
export const getUnmatchedPdfs = (projectId) => apiGet(withProject("/research-os/literature/unmatched-pdfs", projectId, { limit: 50 }));
export const getAgentFeed = (projectId) => apiGet(withProject("/research-os/agent-feed", projectId, { limit: 50 }));
export const getWorkflowBoard = (projectId) => apiGet(withProject("/research-os/workflow-board", projectId));
export const getLlmSettings = () => apiGet("/api/settings/llm");
export const saveLlmSettings = (payload) => apiPost("/api/settings/llm", payload);
export const testLlmSettings = (payload) => apiPost("/api/settings/llm/test", payload);
