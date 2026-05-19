import { escapeHtml, text } from "./cards.js";

function currentProjectName(projects, activeProjectId) {
  const current = (projects || []).find((project) => (project.id || project.project_id || "") === activeProjectId);
  return current?.display_name || current?.title || current?.name || "未命名项目";
}

export function renderProjectSwitcher(projects, activeProjectId) {
  const hasSelectedProject = Boolean((projects || []).some((project) => (project.id || project.project_id || "") === activeProjectId));
  if (!projects?.length || !activeProjectId || !hasSelectedProject) {
    return `<div class="project-toolbar project-toolbar-empty">
      <div class="project-empty">未选择项目</div>
      <button class="button secondary small" type="button" data-view-target="projects">新建项目</button>
    </div>`;
  }
  const label = currentProjectName(projects, activeProjectId);
  const options = projects
    .map((project) => {
      const id = project.id || project.project_id || "";
      const name = project.display_name || project.title || project.name || "未命名项目";
      return `<option value="${escapeHtml(id)}"${id === activeProjectId ? " selected" : ""}>${escapeHtml(text(name))}</option>`;
    })
    .join("");
  return `<div class="project-toolbar">
    <span class="project-current-label">当前项目</span>
    <span class="project-current" title="${escapeHtml(text(label))}">${escapeHtml(text(label))}</span>
    <label class="sr-only" for="projectSelect">项目</label>
    <select id="projectSelect" class="project-select" lang="zh-CN" data-project-select>${options}</select>
    <button class="button secondary small" type="button" data-view-target="projects">新建项目</button>
  </div>`;
}
