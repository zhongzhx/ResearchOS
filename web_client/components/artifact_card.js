import { escapeHtml } from "./cards.js";
import { developerDetails } from "./developer_details.js";

const SOURCE_LABELS = {
  upload: "上传文件",
  literature_pdf: "文献 PDF",
  manual_pdf: "手动补全文",
  generated_markdown: "生成文档",
  generated_pptx: "PPT",
  generated_figure: "图表",
  generated_table: "表格",
  generated_data: "数据文件",
  kb_index: "知识库索引",
  rag_chunk: "RAG 文本块",
  workflow_run_artifact: "Workflow 生成物",
};

function label(value) {
  return SOURCE_LABELS[value] || value || "项目文件";
}

function size(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function pathSummary(path) {
  const value = String(path || "");
  return value.length > 84 ? `...${value.slice(-81)}` : value;
}

export function artifactCategory(artifact = {}) {
  const source = artifact.source_type || artifact.artifact_type || artifact.type || "";
  if (source === "upload") return "uploads";
  if (source === "literature_pdf") return "papers";
  if (source === "manual_pdf") return "manual";
  if (source === "generated_pptx") return "ppt";
  if (source === "generated_figure" || source === "generated_table") return "figures_tables";
  if (source === "kb_index" || source === "rag_chunk") return "kb";
  return "documents";
}

export function renderArtifactCard(artifact = {}, { developerMode = false } = {}) {
  const source = artifact.source_type || artifact.artifact_type || artifact.type || "";
  const status = artifact.status || "registered";
  const ingest = artifact.ingest_status || "registered";
  const path = artifact.absolute_path || artifact.path || "";
  const title = artifact.display_name || artifact.title || artifact.original_name || "未命名文件";
  return `<article class="artifact-card" data-artifact-id="${escapeHtml(artifact.artifact_id || "")}">
    <div class="artifact-card-header">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <div class="artifact-meta">
          <span>${escapeHtml(label(source))}</span>
          <span>${escapeHtml(size(artifact.size_bytes))}</span>
          <span>${escapeHtml(artifact.created_at || "")}</span>
        </div>
      </div>
      <span class="badge ${status === "failed" || status === "deleted" ? "warning" : "success"}">${escapeHtml(status)}</span>
    </div>
    <p class="artifact-path">${escapeHtml(pathSummary(path))}</p>
    <div class="artifact-meta">
      <span>来源 workflow: ${escapeHtml(artifact.run_id || "无")}</span>
      <span>入库状态: ${escapeHtml(ingest === "indexed" ? "已入库" : ingest)}</span>
      <span>预览: ${escapeHtml(artifact.preview_type || "file")}</span>
    </div>
    ${developerDetails("Artifact raw record", artifact, developerMode)}
  </article>`;
}
