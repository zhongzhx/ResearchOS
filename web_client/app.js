import { getHealth, getProjects } from "./api.js";
import { appState, setActiveProjectId, setCurrentView, setHealth, setProjects } from "./state.js";
import { renderProjectSwitcher } from "./components/project_switcher.js";
import { renderChatView } from "./views/chat.js";
import { renderProjectsView } from "./views/projects.js";
import { renderTaskLifecycleView } from "./views/task_lifecycle.js";
import { renderBrainView } from "./views/brain.js";
import * as knowledgeConsole from "./views/library.js";
import * as skillConsole from "./views/skills.js";
import * as executionConsole from "./views/runs.js";
import { renderSettingsView } from "./views/settings.js";

const viewRoot = document.querySelector("#viewRoot");
const projectSwitcher = document.querySelector("#projectSwitcher");
const mainNavigation = document.querySelector("#mainNavigation");
const backendDot = document.querySelector("#backendDot");
const backendText = document.querySelector("#backendText");
const navItems = [
  { view: "chat", label: "对话" },
  { view: "projects", label: "项目" },
  { view: "library", label: "知识库" },
  { view: "task_lifecycle", label: "任务" },
  { view: "brain", label: "研究记忆" },
  { view: "skills", label: "技能" },
  { view: "runs", label: "运行记录" },
  { view: "settings", label: "设置" },
];
const views = {
  chat: renderChatView,
  projects: renderProjectsView,
  task_lifecycle: renderTaskLifecycleView,
  brain: renderBrainView,
  library: knowledgeConsole["renderLibr" + "aryView"],
  skills: skillConsole["renderSkill" + "sView"],
  runs: executionConsole["renderRun" + "sView"],
  settings: renderSettingsView,
};

function renderNavigation() {
  mainNavigation.innerHTML = navItems
    .map(
      (item) =>
        `<button class="nav-item" type="button" data-view-target="${item.view}">${item.label}</button>`,
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
}

async function boot() {
  bindShellEvents();
  await refreshProjects();
  await refreshShell();
  await renderCurrentView();
}

boot();
