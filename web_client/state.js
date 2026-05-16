const ACTIVE_PROJECT_KEY = "researchos.activeProjectId";
const VIEW_KEY = "researchos.currentView";

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

export const appState = {
  activeProjectId: safeLocalStorageGet(ACTIVE_PROJECT_KEY),
  activeProject: null,
  currentView: safeLocalStorageGet(VIEW_KEY, "chat"),
  dualAgentEnabled: false,
  health: null,
  runtimeStatus: null,
  lastRunResult: null,
  cachedProjects: [],
  pendingSkills: [],
  resolverHealth: null,
  conversationId: "",
};

export function setProjects(projects) {
  appState.cachedProjects = Array.isArray(projects) ? projects : [];
  const found = appState.cachedProjects.find((project) => project.id === appState.activeProjectId || project.project_id === appState.activeProjectId);
  appState.activeProject = found || appState.cachedProjects[0] || null;
  appState.activeProjectId = appState.activeProject?.id || appState.activeProject?.project_id || "";
  if (appState.activeProjectId) safeLocalStorageSet(ACTIVE_PROJECT_KEY, appState.activeProjectId);
}

export function setActiveProjectId(projectId) {
  appState.activeProjectId = projectId || "";
  appState.activeProject = appState.cachedProjects.find((project) => project.id === appState.activeProjectId || project.project_id === appState.activeProjectId) || null;
  if (appState.activeProjectId) safeLocalStorageSet(ACTIVE_PROJECT_KEY, appState.activeProjectId);
}

export function setCurrentView(view) {
  appState.currentView = view || "chat";
  safeLocalStorageSet(VIEW_KEY, appState.currentView);
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
}

export function setPendingSkills(skills) {
  appState.pendingSkills = Array.isArray(skills) ? skills : [];
}

export function setResolverHealth(health) {
  appState.resolverHealth = health;
}
