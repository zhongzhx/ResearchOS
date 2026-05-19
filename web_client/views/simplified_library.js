import { getFiles, getKnowledgeBaseEntries, getReferences } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, compactPath, escapeHtml, firstArray, itemCard, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";

let search = "";
let contentRefreshSeq = 0;

function currentProjectId() {
  return appState.activeProjectId || "default";
}

function matches(row) {
  if (!search) return true;
  return JSON.stringify(row).toLowerCase().includes(search.toLowerCase());
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

async function refreshSimpleLibraryContent(root) {
  const refreshId = ++contentRefreshSeq;
  const content = root.querySelector("#simpleLibraryContent");
  if (!content) return;
  content.innerHTML = emptyState("正在加载资料库", "正在读取当前项目资料。");
  const [references, files, knowledge] = await Promise.all([
    getReferences(currentProjectId(), search),
    getFiles(currentProjectId()),
    getKnowledgeBaseEntries(currentProjectId()),
  ]);
  if (refreshId !== contentRefreshSeq) return;
  const referenceRows = firstArray(references.data, ["references"]);
  const fileRows = firstArray(files.data, ["files"]);
  const knowledgeRows = firstArray(knowledge.data, ["knowledge_base_entries", "entries"]);
  content.innerHTML = `
    <div class="library-stats">
      <span class="status-pill">论文与引用 · ${referenceRows.length}</span>
      <span class="status-pill">项目文件 · ${fileRows.length}</span>
      <span class="status-pill">知识条目 · ${knowledgeRows.length}</span>
    </div>
    <div class="library-sections">
      <section class="library-section">
        <div class="section-heading"><div><h2>论文与引用</h2></div></div>
        ${references.ok ? renderReferenceList(referenceRows) : apiErrorCard(references, "论文列表暂不可用")}
      </section>
      <section class="library-section">
        <div class="section-heading"><div><h2>项目文件</h2></div></div>
        ${files.ok ? renderFileList(fileRows) : apiErrorCard(files, "文件列表暂不可用")}
      </section>
      <section class="library-section">
        <div class="section-heading"><div><h2>整理知识</h2></div></div>
        ${knowledge.ok ? renderKnowledgeList(knowledgeRows) : apiErrorCard(knowledge, "知识条目暂不可用")}
      </section>
    </div>
  `;
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
}
