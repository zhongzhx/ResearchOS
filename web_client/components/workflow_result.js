import { ARTIFACT_TYPES, normalizeArtifact, saveArtifactToProject } from "../artifact_types.js";
import { escapeHtml } from "./cards.js";

function artifactTypeLabel(type) {
  return ARTIFACT_TYPES[type]?.label || type || "科研交付物";
}

function formatDate(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("zh-CN");
  } catch {
    return String(value);
  }
}

function projectLabel(projectId) {
  return projectId || "当前项目";
}

function artifactStatusLabel(artifact) {
  if (artifact.status === "plan_only" || artifact.metadata?.plan_only) return "计划草稿";
  if (artifact.artifact_type === "journal_club_ppt" && !artifact.metadata?.file_url) return "生成 PPT 计划";
  return "已生成";
}

function fileExtension(artifact) {
  const format = artifact.metadata?.format || ARTIFACT_TYPES[artifact.artifact_type]?.format || "md";
  if (artifact.status === "plan_only" && format === "pptx") return "md";
  if (["md", "txt", "svg", "pptx"].includes(format)) return format;
  return "txt";
}

function normalizedArtifacts(result, projectId) {
  return (Array.isArray(result?.artifacts) ? result.artifacts : []).map((artifact) => normalizeArtifact(projectId || artifact.project_id, artifact));
}

function artifactPreview(artifact) {
  if (artifact.artifact_type === "publication_figure") {
    return `<div class="artifact-preview figure-preview"><span>SVG 图预览占位</span></div>`;
  }
  const excerpt = String(artifact.content || "").replace(/[#*_`>~-]/g, "").trim().slice(0, 260);
  return excerpt ? `<p class="artifact-excerpt">${escapeHtml(excerpt)}${excerpt.length >= 260 ? "..." : ""}</p>` : "";
}

function artifactActions(artifact) {
  const extension = fileExtension(artifact);
  const downloadLabel =
    artifact.artifact_type === "publication_figure"
      ? "导出 SVG"
      : artifact.artifact_type === "journal_club_ppt" && artifact.status !== "plan_only"
        ? "下载 PPT"
        : `下载 .${extension}`;
  return `<div class="artifact-actions">
    <button class="button secondary small" type="button" data-artifact-copy="${escapeHtml(artifact.artifact_id)}">复制内容</button>
    ${
      artifact.downloadable
        ? `<button class="button secondary small" type="button" data-artifact-download="${escapeHtml(artifact.artifact_id)}" data-artifact-extension="${escapeHtml(extension)}">${escapeHtml(downloadLabel)}</button>`
        : ""
    }
    <button class="button primary small" type="button" data-artifact-save="${escapeHtml(artifact.artifact_id)}">保存到项目资料库</button>
    <button class="button ghost small" type="button" data-artifact-continue="${escapeHtml(artifact.artifact_id)}">在 Chat 中继续修改</button>
  </div>`;
}

function artifactCard(artifact) {
  return `<article class="artifact-card" data-artifact-id="${escapeHtml(artifact.artifact_id)}">
    <div class="artifact-card-header">
      <div>
        <strong>${escapeHtml(artifact.title)}</strong>
        <div class="artifact-meta">
          <span>${escapeHtml(artifactTypeLabel(artifact.artifact_type))}</span>
          <span>${escapeHtml(formatDate(artifact.created_at))}</span>
          <span>${escapeHtml(projectLabel(artifact.project_id))}</span>
        </div>
      </div>
      <span class="badge ${artifact.status === "plan_only" ? "warning" : "success"}">${escapeHtml(artifactStatusLabel(artifact))}</span>
    </div>
    ${artifactPreview(artifact)}
    ${artifactActions(artifact)}
  </article>`;
}

export function renderWorkflowResult(result = {}, options = {}) {
  const projectId = options.projectId || result.project_id || "default";
  const artifacts = normalizedArtifacts(result, projectId);
  const title = result.title || "科研交付物";
  const message = result.message || result.result_summary || "任务结果已整理为可保存的交付物。";
  return `<section class="workflow-result-delivery">
    <div class="workflow-result-summary">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(message)}</p>
    </div>
    <div class="artifact-list">
      ${artifacts.length ? artifacts.map(artifactCard).join("") : "<p class=\"muted-text\">暂无可保存交付物。</p>"}
    </div>
  </section>`;
}

function findArtifact(root, artifactId) {
  const card = root.querySelector(`[data-artifact-id="${CSS.escape(artifactId)}"]`);
  if (!card) return null;
  return {
    artifact_id: artifactId,
    title: card.querySelector("strong")?.textContent || "科研交付物",
    content: card.querySelector(".artifact-excerpt")?.textContent || card.querySelector(".artifact-preview")?.textContent || "",
  };
}

function downloadableBlob(artifact, extension) {
  const type = extension === "svg" ? "image/svg+xml" : "text/plain;charset=utf-8";
  return new Blob([artifact.content || ""], { type });
}

function downloadArtifact(artifact, extension) {
  const blob = downloadableBlob(artifact, extension);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${artifact.artifact_id}.${extension}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

export function bindWorkflowResultActions(root, { projectId = "default", artifacts = [] } = {}) {
  const artifactById = new Map(artifacts.map((artifact) => [artifact.artifact_id, normalizeArtifact(projectId || artifact.project_id, artifact)]));
  root.querySelectorAll("[data-artifact-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const artifactId = button.dataset.artifactCopy;
      const artifact = artifactById.get(artifactId) || findArtifact(root, artifactId);
      if (!artifact) return;
      await navigator.clipboard?.writeText?.(artifact.content || "");
    });
  });
  root.querySelectorAll("[data-artifact-download]").forEach((button) => {
    button.addEventListener("click", () => {
      const artifactId = button.dataset.artifactDownload;
      const artifact = artifactById.get(artifactId) || findArtifact(root, artifactId);
      if (!artifact) return;
      downloadArtifact(artifact, button.dataset.artifactExtension || "txt");
    });
  });
  root.querySelectorAll("[data-artifact-save]").forEach((button) => {
    button.addEventListener("click", () => {
      const artifactId = button.dataset.artifactSave;
      const artifact = artifactById.get(artifactId);
      if (!artifact) return;
      saveArtifactToProject(projectId || artifact.project_id, artifact);
      button.textContent = "已保存";
    });
  });
  root.querySelectorAll("[data-artifact-continue]").forEach((button) => {
    button.addEventListener("click", () => {
      const artifactId = button.dataset.artifactContinue;
      window.dispatchEvent?.(new CustomEvent("researchos:continue-artifact-in-chat", { detail: { artifactId, projectId } }));
    });
  });
}
