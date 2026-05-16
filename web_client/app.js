import { getHealth, getProjects, getResolverHealth, getRuntimeStatus } from "./api.js";
import { appState, setActiveProjectId, setCurrentView, setHealth, setProjects, setResolverHealth } from "./state.js";
import { renderProjectSwitcher } from "./components/project_switcher.js";
import { renderChatView } from "./views/chat.js";
import { renderTaskLifecycleView } from "./views/task_lifecycle.js";
import { renderBrainView } from "./views/brain.js";
import { renderLibraryView } from "./views/library.js";
import { renderSkillsView } from "./views/skills.js";
import { renderRunsView } from "./views/runs.js";
import { renderSettingsView } from "./views/settings.js";

const viewRoot = document.querySelector("#viewRoot");
const projectSwitcher = document.querySelector("#projectSwitcher");
const backendDot = document.querySelector("#backendDot");
const backendText = document.querySelector("#backendText");
const views = {
  chat: renderChatView,
  task_lifecycle: renderTaskLifecycleView,
  brain: renderBrainView,
  library: renderLibraryView,
  skills: renderSkillsView,
  runs: renderRunsView,
  settings: renderSettingsView,
};

function updateNavigation() {
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === appState.currentView);
  });
}

function updatePill(id, label, tone) {
  const pill = document.querySelector(`#${id}`);
  if (!pill) return;
  pill.className = `status-pill ${tone}`;
  pill.textContent = label;
}

function updateShellStatus() {
  const connected = Boolean(appState.health?.ok);
  backendDot.classList.toggle("ok", connected);
  backendText.textContent = connected ? "已连接" : "后端不可用";

  const resolverDisabled = appState.resolverHealth?.error === "dual_agent_api_disabled";
  const resolverOk = Boolean(appState.resolverHealth?.ok);
  updatePill(
    "dualAgentPill",
    resolverDisabled ? "双 Agent 已关闭" : resolverOk ? "双 Agent 就绪" : "双 Agent 不可用",
    resolverDisabled ? "muted" : resolverOk ? "success" : "warning",
  );
  updatePill("runtimePill", connected ? "运行时在线" : "运行时离线", connected ? "success" : "danger");
}

async function refreshProjects() {
  const result = await getProjects();
  const projects = result.ok ? result.data.projects || [] : [];
  setProjects(projects);
  projectSwitcher.innerHTML = renderProjectSwitcher(appState.cachedProjects, appState.activeProjectId);
}

async function refreshShell() {
  const [health, runtime, resolver] = await Promise.all([getHealth(), getRuntimeStatus(appState.activeProjectId), getResolverHealth()]);
  setHealth(health.ok ? { ok: true, ...health.data } : { ok: false, error: health.error });
  appState.runtimeStatus = runtime.ok ? runtime.data : null;
  setResolverHealth(resolver.ok ? { ok: true, ...resolver.data } : { ok: false, error: resolver.error, status: resolver.status });
  updateShellStatus();
}

async function renderCurrentView() {
  updateNavigation();
  const render = views[appState.currentView] || views.chat;
  viewRoot.setAttribute("aria-busy", "true");
  await render({ root: viewRoot, refreshShell, refreshProjects, renderCurrentView });
  viewRoot.setAttribute("aria-busy", "false");
}

function bindShellEvents() {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-view-target]");
    if (!button) return;
    setCurrentView(button.dataset.viewTarget);
    await renderCurrentView();
  });

  projectSwitcher.addEventListener("change", async (event) => {
    if (event.target.matches("[data-project-select]")) {
      setActiveProjectId(event.target.value);
      await refreshShell();
      await renderCurrentView();
    }
  });

  window.addEventListener("researchos:refresh-view", renderCurrentView);
  window.addEventListener("researchos:refresh-shell", refreshShell);
}

async function boot() {
  bindShellEvents();
  await refreshProjects();
  await refreshShell();
  await renderCurrentView();
}

boot();
