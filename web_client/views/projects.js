import { archiveProject, clearProject, createProject, purgeProject, updateProject } from "../api.js";
import { appState, projectDisplayName, setActiveProjectId, setCurrentView, startNewConversation } from "../state.js";
import { badge, escapeHtml, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";

function projectId(project) {
  return project.id || project.project_id || "";
}

function projectName(project) {
  return projectDisplayName(project);
}

function projectSummary(project) {
  return project.research_area || project.description || project.summary || project.status || "项目上下文会用于 AURA 的聊天回答。";
}

function projectCard(project) {
  const id = projectId(project);
  const active = id && id === appState.activeProjectId;
  const name = projectName(project);
  const meta = [active ? "当前项目" : project.status || "项目", project.updated_at || project.created_at || "", project.research_area || ""].filter(Boolean);
  return `<article class="item-card">
    <h3 class="item-title">${escapeHtml(name)}</h3>
    <p class="item-subtitle">${escapeHtml(projectSummary(project))}</p>
    <div class="item-meta">${meta.map((item) => badge(item)).join("")}</div>
    ${
      id
        ? `<div class="inline-actions">
            <button class="button secondary small" type="button" data-select-project-id="${escapeHtml(id)}">打开</button>
            <button class="button danger small" type="button" data-delete-project-id="${escapeHtml(id)}" data-project-name="${escapeHtml(name)}">删除</button>
          </div>`
        : ""
    }
  </article>`;
}

function activeProject() {
  return appState.cachedProjects.find((project) => projectId(project) === appState.activeProjectId) || appState.activeProject;
}

function statusLine(result, success) {
  if (!result) return "";
  return `<div class="notice ${result.ok ? "success" : "error"}"><strong>${escapeHtml(result.ok ? success : "操作失败")}</strong><p>${escapeHtml(result.error || result.data?.error || "")}</p></div>`;
}

async function refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView }) {
  if (refreshProjects) await refreshProjects();
  if (refreshShell) await refreshShell();
  if (renderCurrentView) await renderCurrentView();
}

let projectActionStatus = null;

export async function renderProjectsView({ root, refreshShell, refreshProjects, renderCurrentView }) {
  const projects = appState.cachedProjects || [];
  const active = activeProject();
  const activeId = appState.activeProjectId;
  const activeName = projectName(active);
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">项目</h1><p class="page-subtitle">创建、选择和管理 AURA Research 项目。</p></div>
    </header>
    <div class="page-scroll">
      <div class="grid">
        ${statusLine(projectActionStatus, "操作已完成")}
        <div class="panel pad grid">
          <h2 class="item-title">新建项目</h2>
          <div class="inline-actions">
            <input class="text-input" id="newProjectName" lang="zh-CN" placeholder="项目名称" />
            <button class="button primary" type="button" id="createProjectButton">新建项目</button>
          </div>
        </div>
        <div class="panel pad grid">
          <h2 class="item-title">当前项目</h2>
          ${
            active
              ? `<p class="muted">${escapeHtml(activeName)}</p>
                 <div class="inline-actions">
                   <input class="text-input" id="renameProjectName" lang="zh-CN" value="${escapeHtml(activeName)}" />
                   <button class="button secondary" type="button" id="renameProjectButton">重命名项目</button>
                   <button class="button secondary" type="button" id="archiveProjectButton">归档项目</button>
                 </div>`
              : emptyState("还没有项目", "创建一个项目，开始保存你的研究对话和资料。")
          }
        </div>
        <div class="panel pad grid">
          <h2 class="item-title">项目列表</h2>
        ${
          projects.length
            ? `<div class="list">${projects.map(projectCard).join("")}</div>`
            : emptyState("还没有项目", "创建一个项目，开始保存你的研究对话和资料。")
        }
        </div>
        ${
          active
            ? `<div class="panel pad grid">
                <h2 class="item-title">危险区</h2>
                <p class="muted">清空当前项目相关数据会移除项目内资料、记忆和任务记录，但保留项目本身。</p>
                <div class="inline-actions">
                  <button class="button danger" type="button" id="clearProjectButton">清空项目数据</button>
                  <button class="button danger" type="button" id="purgeProjectButton">彻底删除项目</button>
                </div>
              </div>`
            : ""
        }
      </div>
    </div>
  </section>`;

  root.querySelector("#createProjectButton").addEventListener("click", async () => {
    const name = root.querySelector("#newProjectName").value.trim();
    if (!name) return;
    const result = await createProject({ title: name, display_name: name });
    projectActionStatus = result;
    const created = result.data?.project || result.data;
    if (result.ok && projectId(created)) {
      if (refreshProjects) await refreshProjects();
      setActiveProjectId(projectId(created));
      startNewConversation(projectId(created));
      setCurrentView("chat");
      if (refreshShell) await refreshShell();
      if (renderCurrentView) await renderCurrentView();
      return;
    }
    await refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView });
  });

  const renameButton = root.querySelector("#renameProjectButton");
  if (renameButton) {
    renameButton.addEventListener("click", async () => {
      const name = root.querySelector("#renameProjectName").value.trim();
      if (!activeId || !name) return;
      const result = await updateProject(activeId, { title: name, display_name: name });
      projectActionStatus = result;
      await refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView });
    });
  }

  const archiveButton = root.querySelector("#archiveProjectButton");
  if (archiveButton) {
    archiveButton.addEventListener("click", async () => {
      if (!activeId || !confirm(`确定归档项目“${activeName}”吗？`)) return;
      const result = await archiveProject(activeId);
      projectActionStatus = result;
      await refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView });
    });
  }

  const clearButton = root.querySelector("#clearProjectButton");
  if (clearButton) {
    clearButton.addEventListener("click", async () => {
      if (!activeId) return;
      if (!confirm(`确定清空项目“${activeName}”的数据吗？项目本身会保留。`)) return;
      if (!confirm("请再次确认：这会清空当前项目相关数据。")) return;
      const clearPhrase = `确认清空 ${activeName}`;
      const result = await clearProject(activeId, { scope: "all", confirmation: clearPhrase });
      projectActionStatus = result;
      await refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView });
    });
  }

  const purgeButton = root.querySelector("#purgeProjectButton");
  if (purgeButton) {
    purgeButton.addEventListener("click", async () => {
      if (!activeId) return;
      if (!confirm(`确定彻底删除项目“${activeName}”吗？`)) return;
      if (!confirm("请再次确认：彻底删除后普通项目列表中不再显示。")) return;
      const result = await purgeProject(activeId, { confirmation: `CONFIRM PURGE ${activeName}`, confirmed_by_user: "web_client" });
      projectActionStatus = result;
      await refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView });
    });
  }

  root.querySelectorAll("[data-delete-project-id]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const targetId = button.dataset.deleteProjectId;
      const targetName = button.dataset.projectName || targetId;
      if (!targetId) return;
      if (!confirm(`确定彻底删除项目“${targetName}”吗？`)) return;
      if (!confirm("请再次确认：彻底删除后普通项目列表中不再显示。")) return;
      const result = await purgeProject(targetId, { confirmation: `CONFIRM PURGE ${targetName}`, confirmed_by_user: "web_client" });
      projectActionStatus = result;
      await refreshAfterProjectChange({ refreshProjects, refreshShell, renderCurrentView });
    });
  });

  root.querySelectorAll("[data-select-project-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = text(button.closest(".item-card")?.querySelector(".item-title")?.textContent || "");
      setActiveProjectId(button.dataset.selectProjectId);
      if (refreshShell) await refreshShell();
      if (renderCurrentView) await renderCurrentView();
      if (name) window.dispatchEvent(new CustomEvent("researchos:project-selected", { detail: { name: escapeHtml(name) } }));
    });
  });
}
