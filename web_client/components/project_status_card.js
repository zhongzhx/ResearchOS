import { escapeHtml } from "./cards.js";

export function renderProjectStatusCard(status = {}) {
  const counts = status.counts || {};
  return `<article class="project-status-card">
    <strong>${escapeHtml(status.display_name || "当前项目")}</strong>
    <span>${escapeHtml(status.project_id || "")}</span>
    <p>${escapeHtml(status.root_path || status.paths?.root_path || "")}</p>
    <div class="artifact-meta">
      <span>文件 ${Number(counts.files || 0)}</span>
      <span>生成物 ${Number(counts.artifacts || 0)}</span>
      <span>运行记录 ${Number(counts.workflow_runs || 0)}</span>
    </div>
  </article>`;
}
