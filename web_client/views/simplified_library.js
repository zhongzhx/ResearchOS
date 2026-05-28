import { getFiles, getKnowledgeBaseEntries, getPaperRequests, getReferences } from "../api.js";
import { ARTIFACT_TYPES, listProjectArtifacts } from "../artifact_types.js";
import { appState } from "../state.js";
import { apiErrorCard, compactPath, escapeHtml, firstArray, itemCard, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";

let search = "";
let contentRefreshSeq = 0;

function currentProjectId() {
  return String(appState.activeProjectId || "").trim();
}

function projectSelectionRequiredState() {
  return emptyState("请先选择或创建项目", "每个项目拥有独立资料库，选择项目后才能查看其内容。");
}

function matches(row) {
  if (!search) return true;
  return JSON.stringify(row).toLowerCase().includes(search.toLowerCase());
}

function rowMatches(row, query = search) {
  if (!query) return true;
  return JSON.stringify(row).toLowerCase().includes(String(query).toLowerCase());
}

function renderReferenceList(rows) {
  const filtered = rows.filter(matches).slice(0, 8);
  if (!filtered.length) return emptyState("暂无匹配资料", "可以从工作台发起文献采集，或在项目中加入论文和资料。");
  return `<div class="list compact-list">${filtered
    .map((row) =>
      itemCard({
        title: row.title || row.name || row.doi || "未命名资料",
        subtitle: row.summary || row.answer_summary || row.doi || "暂无摘要",
        status: row.year || row.source_provider || row.source || "已收录",
        meta: [row.journal, row.authors].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

function renderArtifactList(rows, query = search) {
  const filtered = rows.filter((row) => rowMatches(row, query)).slice(0, 12);
  if (!filtered.length) return emptyState("暂无生成文档", "工作台和对话生成的交付物会保存到这里。");
  return `<div class="list compact-list">${filtered
    .map((row) => {
      const type = ARTIFACT_TYPES[row.artifact_type] || {};
      return `<details class="item-card artifact-library-item" data-library-artifact-id="${escapeHtml(row.artifact_id)}">
        <summary>
          <strong>${escapeHtml(row.title || type.label || "科研交付物")}</strong>
          <span>${escapeHtml(type.label || row.artifact_type || "交付物")}</span>
        </summary>
        <p>${escapeHtml(String(row.content || "").slice(0, 500))}</p>
        <small>${escapeHtml(row.created_at || "")}</small>
      </details>`;
    })
    .join("")}</div>`;
}

function renderFileList(rows) {
  const filtered = rows.filter(matches).slice(0, 8);
  if (!filtered.length) return emptyState("暂无匹配文件", "上传的 PDF、表格和项目资料会显示在这里。");
  return `<div class="list compact-list">${filtered
    .map((row) =>
      itemCard({
        title: row.file_name || row.name || row.title || "未命名文件",
        subtitle: compactPath(row.path || row.file_path || row.source) || "暂无路径",
        status: row.status || row.type || "已加入",
      }),
    )
    .join("")}</div>`;
}

function renderManualQueue(rows) {
  const filtered = rows.filter(matches).slice(0, 8);
  if (!filtered.length) return emptyState("暂无手动下载队列", "非开放获取或需要人工处理的文献会显示在这里。");
  return `<div class="list compact-list">${filtered
    .map((row) =>
      itemCard({
        title: row.title || row.doi || "待下载文献",
        subtitle: row.reason || row.recommended_action || row.status || "需要人工确认获取方式",
        status: row.priority || row.doi || "待处理",
        meta: [row.doi, row.recommended_action].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

function renderKnowledgeList(rows) {
  const filtered = rows.filter(matches).slice(0, 8);
  if (!filtered.length) return emptyState("暂无知识条目", "构建项目知识库后，关键结论和整理结果会显示在这里。");
  return `<div class="list compact-list">${filtered
    .map((row) =>
      itemCard({
        title: row.title || row.question || row.name || "知识条目",
        subtitle: text(row.summary || row.answer || row.content, "暂无摘要"),
        status: row.status || row.kind || "已整理",
      }),
    )
    .join("")}</div>`;
}

function knowledgeStatus(knowledgeRows) {
  if (!knowledgeRows.length) return emptyState("知识库状态", "当前项目还没有整理过的知识条目。");
  return `<div class="notice success"><strong>知识库状态</strong><p>已整理 ${knowledgeRows.length} 条项目知识，可用于后续检索和写作。</p></div>`;
}

export function renderSimplifiedLibraryContent({ projectId = currentProjectId(), references = [], files = [], knowledge = [], paperRequests = [], query = search } = {}) {
  if (!String(projectId || "").trim()) return projectSelectionRequiredState();
  const artifacts = listProjectArtifacts(projectId);
  const literatureArtifacts = artifacts.filter((item) => item.artifact_type === "literature_table");
  const manualArtifacts = artifacts.filter((item) => item.artifact_type === "manual_download_queue");
  const documentArtifacts = artifacts.filter((item) => !["literature_table", "manual_download_queue"].includes(item.artifact_type));
  const combinedLiterature = [...literatureArtifacts, ...references];
  const combinedManualQueue = [...manualArtifacts, ...paperRequests];
  const filteredFiles = files.filter((row) => rowMatches(row, query));
  const filteredKnowledge = knowledge.filter((row) => rowMatches(row, query));
  return `
    <div class="library-stats">
      <span class="status-pill">已上传文件 · ${filteredFiles.length}</span>
      <span class="status-pill">已生成文档 · ${documentArtifacts.length}</span>
      <span class="status-pill">文献清单 · ${combinedLiterature.length}</span>
      <span class="status-pill">手动下载队列 · ${combinedManualQueue.length}</span>
    </div>
    <div class="library-sections">
      <section class="library-section">
        <div class="section-heading"><div><h2>已生成文档</h2></div></div>
        ${renderArtifactList(documentArtifacts, query)}
      </section>
      <section class="library-section">
        <div class="section-heading"><div><h2>已上传文件</h2></div></div>
        ${renderFileList(filteredFiles)}
      </section>
      <section class="library-section">
        <div class="section-heading"><div><h2>文献清单</h2></div></div>
        ${renderReferenceList(combinedLiterature)}
      </section>
      <section class="library-section">
        <div class="section-heading"><div><h2>手动下载队列</h2></div></div>
        ${renderManualQueue(combinedManualQueue)}
      </section>
      <section class="library-section">
        <div class="section-heading"><div><h2>知识库状态</h2></div></div>
        ${knowledgeStatus(filteredKnowledge)}
        ${renderKnowledgeList(filteredKnowledge)}
      </section>
    </div>
  `;
}

async function refreshSimpleLibraryContent(root) {
  const refreshId = ++contentRefreshSeq;
  const content = root.querySelector("#simpleLibraryContent");
  if (!content) return;
  const projectId = currentProjectId();
  if (!projectId) {
    content.innerHTML = projectSelectionRequiredState();
    return;
  }
  content.innerHTML = emptyState("正在加载资料库", "正在读取当前项目资料。");
  const [references, files, knowledge, paperRequests] = await Promise.all([
    getReferences(projectId, search),
    getFiles(projectId),
    getKnowledgeBaseEntries(projectId),
    getPaperRequests(projectId),
  ]);
  if (refreshId !== contentRefreshSeq) return;
  const referenceRows = firstArray(references.data, ["references"]);
  const fileRows = firstArray(files.data, ["files"]);
  const knowledgeRows = firstArray(knowledge.data, ["knowledge_base_entries", "entries"]);
  const requestRows = firstArray(paperRequests.data, ["paper_requests", "requests"]);
  const contentHtml = renderSimplifiedLibraryContent({
    projectId,
    references: references.ok ? referenceRows : [],
    files: files.ok ? fileRows : [],
    knowledge: knowledge.ok ? knowledgeRows : [],
    paperRequests: paperRequests.ok ? requestRows : [],
  });
  const errors = [references.ok ? "" : apiErrorCard(references, "论文列表暂不可用"), files.ok ? "" : apiErrorCard(files, "文件列表暂不可用"), knowledge.ok ? "" : apiErrorCard(knowledge, "知识条目暂不可用"), paperRequests.ok ? "" : apiErrorCard(paperRequests, "手动下载队列暂不可用")].join("");
  content.innerHTML = `${errors}${contentHtml}`;
}

export async function renderSimplifiedLibraryView({ root }) {
  root.innerHTML = `<section class="page library-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">资料库</h1>
      </div>
      <input class="search-input" id="simpleLibrarySearch" lang="zh-CN" value="${escapeHtml(search)}" placeholder="搜索标题、DOI、文件名或摘要" />
    </header>
    <div class="page-scroll">
      <div class="library-content" id="simpleLibraryContent">${emptyState("正在加载资料库", "正在读取当前项目资料。")}</div>
    </div>
  </section>`;

  await refreshSimpleLibraryContent(root);

  root.querySelector("#simpleLibrarySearch").addEventListener("input", (event) => {
    search = event.target.value;
    refreshSimpleLibraryContent(root);
  });
  window.addEventListener("researchos:artifacts-updated", () => refreshSimpleLibraryContent(root), { once: true });
}
