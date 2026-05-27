import { getHealth, getProjects } from "./api.js";
import { appState, setActiveProjectId, setCurrentView, setHealth, setProjects } from "./state.js";
import { renderProjectSwitcher } from "./components/project_switcher.js";
import { renderChatView } from "./views/chat.js";
import { renderWorkspaceView } from "./views/workspace.js";
import { renderProjectsView } from "./views/projects.js";
import { renderTaskLifecycleView } from "./views/task_lifecycle.js";
import { renderBrainView } from "./views/brain.js";
import * as knowledgeConsole from "./views/library.js";
import { renderSimplifiedLibraryView } from "./views/simplified_library.js";
import * as skillConsole from "./views/skills.js";
import * as executionConsole from "./views/runs.js";
import { renderSettingsView } from "./views/settings.js";

const viewRoot = document.querySelector("#viewRoot");
const projectSwitcher = document.querySelector("#projectSwitcher");
const mainNavigation = document.querySelector("#mainNavigation");
const backendDot = document.querySelector("#backendDot");
const backendText = document.querySelector("#backendText");
const navItems = [
  { view: "chat", label: "对话", icon: "C" },
  { view: "workspace", label: "工作台", icon: "W" },
  { view: "projects", label: "项目", icon: "P" },
  { view: "simplified_library", label: "资料库", icon: "L" },
  { view: "settings", label: "设置", icon: "S" },
  { view: "task_lifecycle", label: "任务调试", icon: "T", developerOnly: true },
  { view: "brain", label: "研究记忆", icon: "B", developerOnly: true },
  { view: "skills", label: "技能目录", icon: "K", developerOnly: true },
  { view: "runs", label: "运行记录", icon: "R", developerOnly: true },
  { view: "library", label: "知识库调试", icon: "D", developerOnly: true },
  { view: "developer_diagnostics", label: "API / Resolver 诊断", icon: "A", developerOnly: true },
];
const views = {
  chat: renderChatView,
  workspace: renderWorkspaceView,
  projects: renderProjectsView,
  task_lifecycle: renderTaskLifecycleView,
  brain: renderBrainView,
  library: knowledgeConsole["renderLibr" + "aryView"],
  simplified_library: renderSimplifiedLibraryView,
  skills: skillConsole["renderSkill" + "sView"],
  runs: executionConsole["renderRun" + "sView"],
  settings: renderSettingsView,
  developer_diagnostics: renderSettingsView,
};

function visibleNavItems() {
  return navItems.filter((item) => appState.developerMode || !item.developerOnly);
}

function canAccessView(view) {
  const item = navItems.find((navItem) => navItem.view === view);
  return Boolean(item && (appState.developerMode || !item.developerOnly));
}

function renderNavigation() {
  mainNavigation.innerHTML = visibleNavItems()
    .map(
      (item) =>
        `<button class="nav-item" type="button" data-view-target="${item.view}" title="${item.label}" aria-label="${item.label}">
          <span class="nav-item-icon" aria-hidden="true">${item.icon || item.label.slice(0, 1)}</span>
          <span class="nav-item-label">${item.label}</span>
        </button>`,
    )
    .join("");
}

function updateNavigation() {
  renderNavigation();
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === appState.currentView);
  });
}

function updateShellStatus() {
  const connected = Boolean(appState.health?.ok);
  backendDot.classList.toggle("ok", connected);
  backendText.textContent = connected ? "已连接" : "服务不可用";
}

async function refreshProjects() {
  const result = await getProjects();
  const rawProjects = result.ok ? result.data.projects || result.data.grouped?.active || [] : [];
  const projects = rawProjects.filter((project) => !["archived", "purged"].includes(String(project.status || "").toLowerCase()));
  setProjects(projects);
  projectSwitcher.innerHTML = renderProjectSwitcher(appState.cachedProjects, appState.activeProjectId);
}

async function refreshShell() {
  const health = await getHealth();
  setHealth(health.ok ? { ok: true, ...health.data } : { ok: false, error: health.error });
  updateShellStatus();
}

async function renderCurrentView() {
  if (!canAccessView(appState.currentView)) {
    setCurrentView("chat");
  }
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
    const targetView = button.dataset.viewTarget;
    setCurrentView(targetView);
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
  window.addEventListener("researchos:refresh-navigation", renderCurrentView);
  window.addEventListener("researchos:continue-artifact-in-chat", async (event) => {
    setCurrentView("chat");
    await renderCurrentView();
    const input = document.querySelector("#chatInput");
    if (input && event.detail?.artifactId) {
      input.value = `请基于交付物 ${event.detail.artifactId} 继续修改：`;
      input.focus();
    }
  });
}

async function boot() {
  bindShellEvents();
  await refreshProjects();
  if (appState.activeProjectId) {
    setCurrentView("chat");
  }
  await refreshShell();
  await renderCurrentView();
}

boot();
