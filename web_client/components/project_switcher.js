import { escapeHtml, text } from "./cards.js";

export function renderProjectSwitcher(projects, activeProjectId) {
  if (!projects?.length) {
    return `<div class="project-empty">No project selected</div>`;
  }
  const options = projects
    .map((project) => {
      const id = project.id || project.project_id || "";
      const name = project.title || project.name || id || "Untitled project";
      return `<option value="${escapeHtml(id)}"${id === activeProjectId ? " selected" : ""}>${escapeHtml(text(name))}</option>`;
    })
    .join("");
  return `<label class="sr-only" for="projectSelect">Project</label><select id="projectSelect" class="project-select" data-project-select>${options}</select>`;
}
