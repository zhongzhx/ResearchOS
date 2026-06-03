const ACTIVE_PROJECT_KEY = "researchos.activeProjectId";
const VIEW_KEY = "researchos.currentView";
const CHAT_HISTORY_KEY = "researchos.chatHistory.v1";
const DEVELOPER_MODE_KEY = "researchos.developerMode";
const CLIENT_CACHE_SCHEMA_KEY = "researchos.clientCacheSchemaVersion";
export const CLIENT_CACHE_SCHEMA_VERSION = "2";

function safeLocalStorageGet(key, fallback = "") {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function safeLocalStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // UI preferences are optional.
  }
}

function safeLocalStorageRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // UI preferences are optional.
  }
}

function safeLocalStorageBool(key, fallback = false) {
  try {
    return localStorage.getItem(key) === "true" || fallback;
  } catch {
    return fallback;
  }
}

function safeLocalStorageJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

export function clearLegacyProjectCaches() {
  try {
    if (localStorage.getItem(CLIENT_CACHE_SCHEMA_KEY) === CLIENT_CACHE_SCHEMA_VERSION) return;
    for (let index = Number(localStorage.length || 0) - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index);
      if (key?.startsWith("researchos.")) localStorage.removeItem(key);
    }
    localStorage.setItem(CLIENT_CACHE_SCHEMA_KEY, CLIENT_CACHE_SCHEMA_VERSION);
  } catch {
    // The desktop client can continue without browser cache access.
  }
}

clearLegacyProjectCaches();

const initialChatHistory = safeLocalStorageJson(CHAT_HISTORY_KEY, { projects: {} });

function nowIso() {
  return new Date().toISOString();
}

function normalizeProjectId(projectId) {
  return String(projectId || "").trim();
}

function normalizeConversationId(conversationId) {
  return String(conversationId || "").trim();
}

function projectHistory(projectId, create = false) {
  const key = normalizeProjectId(projectId);
  if (!key) return null;
  appState.conversationsByProject[key] = appState.conversationsByProject[key] || { conversations: [], messages: {}, lastConversationId: "" };
  const history = appState.conversationsByProject[key];
  history.conversations = Array.isArray(history.conversations) ? history.conversations : [];
  history.messages = history.messages && typeof history.messages === "object" ? history.messages : {};
  history.lastConversationId = history.lastConversationId || "";
  return create ? history : history;
}

function persistChatHistory() {
  try {
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify({ projects: appState.conversationsByProject }));
  } catch {
    // Backend chat history API can replace this localStorage fallback later.
  }
}

function initialCurrentView() {
  const storedView = safeLocalStorageGet(VIEW_KEY, "chat");
  return storedView || "chat";
}

export const appState = {
  activeProjectId: safeLocalStorageGet(ACTIVE_PROJECT_KEY),
  activeProject: null,
  currentView: initialCurrentView(),
  developerMode: safeLocalStorageBool(DEVELOPER_MODE_KEY, false),
  dualAgentEnabled: false,
  health: null,
  runtimeStatus: null,
  lastRunResult: null,
  cachedProjects: [],
  pendingSkills: [],
  resolverHealth: null,
  activeConversationId: "",
  conversationsByProject: initialChatHistory.projects || {},
  lastConversationByProject: {},
  conversationId: "",
  sessionId: "",
  conversationProjectId: "",
};

appState.lastConversationByProject = Object.fromEntries(
  Object.entries(appState.conversationsByProject).map(([projectId, history]) => [projectId, history?.lastConversationId || ""]),
);

export function setProjects(projects) {
  const previousProjectId = appState.activeProjectId;
  appState.cachedProjects = Array.isArray(projects)
    ? projects.filter((project) => !["archived", "purged"].includes(String(project.status || "").toLowerCase()))
    : [];
  const found = appState.cachedProjects.find((project) => project.id === appState.activeProjectId || project.project_id === appState.activeProjectId);
  appState.activeProject = found || appState.cachedProjects[0] || null;
  appState.activeProjectId = appState.activeProject?.id || appState.activeProject?.project_id || "";
  if (appState.activeProjectId) safeLocalStorageSet(ACTIVE_PROJECT_KEY, appState.activeProjectId);
  else safeLocalStorageRemove(ACTIVE_PROJECT_KEY);
  switchConversationForProject(appState.activeProjectId);
  if (previousProjectId !== appState.activeProjectId) {
    setLastRunResult(null);
    emitActiveProjectChange(previousProjectId, appState.activeProjectId);
  }
}

export function setActiveProjectId(projectId) {
  const previousProjectId = appState.activeProjectId;
  appState.activeProjectId = normalizeProjectId(projectId);
  appState.activeProject = appState.cachedProjects.find((project) => project.id === appState.activeProjectId || project.project_id === appState.activeProjectId) || null;
  if (appState.activeProjectId) safeLocalStorageSet(ACTIVE_PROJECT_KEY, appState.activeProjectId);
  else safeLocalStorageRemove(ACTIVE_PROJECT_KEY);
  switchConversationForProject(appState.activeProjectId);
  if (previousProjectId !== appState.activeProjectId) {
    setLastRunResult(null);
    emitActiveProjectChange(previousProjectId, appState.activeProjectId);
  }
}

function emitActiveProjectChange(previousProjectId, projectId) {
  if (typeof window === "undefined" || typeof CustomEvent !== "function") return;
  window.dispatchEvent?.(new CustomEvent("researchos:active-project-changed", { detail: { previousProjectId, projectId } }));
}

export function setCurrentView(view) {
  const nextView = view || "chat";
  appState.currentView = nextView;
  safeLocalStorageSet(VIEW_KEY, appState.currentView);
}

export function setDeveloperMode(enabled) {
  appState.developerMode = Boolean(enabled);
  safeLocalStorageSet(DEVELOPER_MODE_KEY, appState.developerMode ? "true" : "false");
}

export function setHealth(health) {
  appState.health = health;
}

export function setLastRunResult(result) {
  appState.lastRunResult = result;
}

export function setDualAgentEnabled(enabled) {
  appState.dualAgentEnabled = Boolean(enabled);
}

export function setConversationId(conversationId) {
  appState.conversationId = conversationId || "";
  appState.activeConversationId = conversationId || appState.activeConversationId || "";
}

export function setSessionId(sessionId) {
  appState.sessionId = sessionId || "";
}

export function setConversationProjectId(projectId) {
  appState.conversationProjectId = projectId || "";
}

export function setPendingSkills(skills) {
  appState.pendingSkills = Array.isArray(skills) ? skills : [];
}

export function setResolverHealth(health) {
  appState.resolverHealth = health;
}

export function projectDisplayName(project) {
  return project?.display_name || project?.title || project?.name || "未命名项目";
}

export function lastConversationForProject(projectId) {
  return appState.lastConversationByProject[normalizeProjectId(projectId)] || "";
}

export function listConversations(projectId, options = {}) {
  const history = projectHistory(projectId);
  if (!history) return [];
  return [...history.conversations]
    .filter((conversation) => options.includeArchived || !conversation.archived_at)
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
}

export function startNewConversation(projectId) {
  const safeProjectId = normalizeProjectId(projectId);
  if (!safeProjectId) return "";
  const history = projectHistory(safeProjectId, true);
  const id = `chat-${safeProjectId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const timestamp = nowIso();
  history.conversations = [{ id, title: "新对话", created_at: timestamp, updated_at: timestamp }, ...history.conversations].slice(0, 20);
  history.messages[id] = [];
  history.lastConversationId = id;
  appState.lastConversationByProject[safeProjectId] = id;
  setConversationProjectId(safeProjectId);
  setConversationId(id);
  setSessionId(id);
  persistChatHistory();
  return id;
}

export function setActiveConversationId(projectId, conversationId) {
  const safeProjectId = normalizeProjectId(projectId);
  const safeConversationId = normalizeConversationId(conversationId);
  if (!safeProjectId || !safeConversationId) return "";
  const history = projectHistory(safeProjectId, true);
  if (!history.conversations.some((conversation) => conversation.id === safeConversationId)) {
    const timestamp = nowIso();
    history.conversations.unshift({ id: safeConversationId, title: "新对话", created_at: timestamp, updated_at: timestamp });
    history.messages[safeConversationId] = history.messages[safeConversationId] || [];
  }
  history.lastConversationId = safeConversationId;
  appState.lastConversationByProject[safeProjectId] = safeConversationId;
  setConversationProjectId(safeProjectId);
  setConversationId(safeConversationId);
  setSessionId(safeConversationId);
  persistChatHistory();
  return safeConversationId;
}

export function deleteConversation(projectId, conversationId) {
  const safeProjectId = normalizeProjectId(projectId);
  const safeConversationId = normalizeConversationId(conversationId);
  const history = projectHistory(safeProjectId);
  if (!history || !safeConversationId) return false;
  const before = history.conversations.length;
  history.conversations = history.conversations.filter((conversation) => conversation.id !== safeConversationId);
  delete history.messages[safeConversationId];
  if (before === history.conversations.length) return false;
  const nextConversation = listConversations(safeProjectId)[0];
  history.lastConversationId = nextConversation?.id || "";
  appState.lastConversationByProject[safeProjectId] = history.lastConversationId;
  if (appState.conversationProjectId === safeProjectId && appState.activeConversationId === safeConversationId) {
    if (history.lastConversationId) {
      setConversationId(history.lastConversationId);
      setSessionId(history.lastConversationId);
    } else {
      setConversationId("");
      setSessionId("");
      appState.activeConversationId = "";
    }
    setConversationProjectId(safeProjectId);
  }
  persistChatHistory();
  return true;
}

export function renameConversation(projectId, conversationId, title) {
  const safeProjectId = normalizeProjectId(projectId);
  const safeConversationId = normalizeConversationId(conversationId);
  const nextTitle = String(title || "").trim();
  const history = projectHistory(safeProjectId);
  if (!history || !safeConversationId || !nextTitle) return false;
  const conversation = history.conversations.find((item) => item.id === safeConversationId);
  if (!conversation) return false;
  conversation.title = nextTitle.length > 48 ? `${nextTitle.slice(0, 48)}...` : nextTitle;
  conversation.updated_at = nowIso();
  persistChatHistory();
  return true;
}

export function archiveConversation(projectId, conversationId) {
  const safeProjectId = normalizeProjectId(projectId);
  const safeConversationId = normalizeConversationId(conversationId);
  const history = projectHistory(safeProjectId);
  if (!history || !safeConversationId) return false;
  const conversation = history.conversations.find((item) => item.id === safeConversationId);
  if (!conversation) return false;
  const timestamp = nowIso();
  conversation.archived_at = timestamp;
  conversation.updated_at = timestamp;
  if (history.lastConversationId === safeConversationId) {
    const nextConversation = listConversations(safeProjectId)[0];
    history.lastConversationId = nextConversation?.id || "";
    appState.lastConversationByProject[safeProjectId] = history.lastConversationId;
  }
  if (appState.conversationProjectId === safeProjectId && appState.activeConversationId === safeConversationId) {
    if (history.lastConversationId) {
      setConversationId(history.lastConversationId);
      setSessionId(history.lastConversationId);
    } else {
      setConversationId("");
      setSessionId("");
      appState.activeConversationId = "";
    }
    setConversationProjectId(safeProjectId);
  }
  persistChatHistory();
  return true;
}

export function ensureActiveConversation(projectId) {
  const safeProjectId = normalizeProjectId(projectId);
  if (!safeProjectId) return "";
  if (appState.conversationProjectId === safeProjectId && appState.activeConversationId) return appState.activeConversationId;
  const last = lastConversationForProject(safeProjectId);
  return last ? setActiveConversationId(safeProjectId, last) : startNewConversation(safeProjectId);
}

export function switchConversationForProject(projectId) {
  const safeProjectId = normalizeProjectId(projectId);
  if (!safeProjectId) {
    setConversationProjectId("");
    setConversationId("");
    setSessionId("");
    appState.activeConversationId = "";
    return "";
  }
  const last = lastConversationForProject(safeProjectId);
  if (last) return setActiveConversationId(safeProjectId, last);
  setConversationProjectId(safeProjectId);
  setConversationId("");
  setSessionId("");
  appState.activeConversationId = "";
  return "";
}

function conversationTitleFromMessage(message) {
  const content = String(message.content || "").trim();
  if (!content) return "新对话";
  return content.length > 32 ? `${content.slice(0, 32)}...` : content;
}

export function saveChatMessage(message) {
  const projectId = normalizeProjectId(message?.project_id);
  const conversationId = normalizeConversationId(message?.conversation_id);
  if (!projectId || !conversationId || !message?.role) return null;
  const history = projectHistory(projectId, true);
  const timestamp = message.created_at || nowIso();
  const record = {
    role: String(message.role),
    content: String(message.content || ""),
    created_at: timestamp,
    project_id: projectId,
    conversation_id: conversationId,
  };
  history.messages[conversationId] = [...(history.messages[conversationId] || []), record].slice(-80);
  const existing = history.conversations.find((conversation) => conversation.id === conversationId);
  if (existing) {
    if (record.role === "user" && (!existing.title || existing.title === "新对话")) existing.title = conversationTitleFromMessage(record);
    existing.updated_at = timestamp;
  } else {
    history.conversations.unshift({
      id: conversationId,
      title: record.role === "user" ? conversationTitleFromMessage(record) : "新对话",
      created_at: timestamp,
      updated_at: timestamp,
    });
  }
  history.conversations = listConversations(projectId).slice(0, 20);
  history.lastConversationId = conversationId;
  appState.lastConversationByProject[projectId] = conversationId;
  setActiveConversationId(projectId, conversationId);
  persistChatHistory();
  return record;
}

export function loadChatMessages(projectId, conversationId) {
  const safeProjectId = normalizeProjectId(projectId);
  const safeConversationId = normalizeConversationId(conversationId);
  const history = projectHistory(safeProjectId);
  if (!history || !safeConversationId) return [];
  return [...(history.messages[safeConversationId] || [])];
}
