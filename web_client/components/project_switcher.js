import { escapeHtml, text } from "./cards.js";

export function renderProjectSwitcher(projects, activeProjectId) {
  if (!projects?.length) {
    return `<div class="project-empty">未选择项目</div>`;
  }
  const options = projects
    .map((project) => {
      const id = project.id || project.project_id || "";
      const name = project.display_name || project.title || project.name || "未命名项目";
      return `<option value="${escapeHtml(id)}"${id === activeProjectId ? " selected" : ""}>${escapeHtml(text(name))}</option>`;
    })
    .join("");
  return `<label class="sr-only" for="projectSelect">项目</label><select id="projectSelect" class="project-select" lang="zh-CN" data-project-select>${options}</select>`;
}
