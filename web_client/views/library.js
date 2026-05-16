import {
  getFiles,
  getKnowledgeBaseEntries,
  getLiteratureSearchTasks,
  getPaperRequests,
  getRagQueries,
  getReferenceChunks,
  getReferences,
  runProductFeature,
  getUnmatchedPdfs,
} from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, compactPath, escapeHtml, firstArray, itemCard } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

let activeTab = "引用";
let search = "";
let literatureKeywords = "RAW264.7, innate immunity";
let maxResults = 10;
let includeOaOnly = true;
let useCampusNetwork = false;
let userAuthorizedBrowser = false;
let lastLiteratureRun = null;
const tabs = ["引用", "文本块", "知识库条目", "RAG 查询", "文献任务", "论文请求", "文件", "未匹配 PDF"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-library-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function matches(row) {
  if (!search) return true;
  return JSON.stringify(row).toLowerCase().includes(search.toLowerCase());
}

function renderRows(rows, emptyLabel) {
  const filtered = rows.filter(matches);
  if (!filtered.length) return emptyState(emptyLabel, "当前项目和搜索条件下没有匹配记录。");
  return `<div class="list">${filtered
    .slice(0, 100)
    .map((row) =>
      itemCard({
        title: row.title || row.question || row.name || row.file_name || row.id || "未命名",
        subtitle: row.answer_summary || row.summary || row.doi || compactPath(row.path || row.file_path || row.source) || "暂无摘要",
        status: row.status || row.year || row.source_provider || row.type || "已记录",
        meta: [row.source, row.year, compactPath(row.file_path)].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

export async function renderLibraryView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">文献库 / 证据</h1><p class="page-subtitle">引用、文本块、知识库条目、RAG 查询、文献任务、论文请求、文件和未匹配 PDF。</p></div>
      <input class="search-input" id="librarySearch" lang="zh-CN" value="${escapeHtml(search)}" placeholder="搜索标题、DOI、来源或状态..." />
    </header>
    <div class="page-scroll">
      <div class="panel pad grid">
        <div class="section-heading">
          <div><h2>新建文献任务</h2><p>创建合规任务，并把暂时无法获取的全文记录为论文请求。</p></div>
        </div>
        <div class="form-grid">
          <label class="field-label">关键词<input class="search-input" id="literatureKeywords" lang="zh-CN" value="${escapeHtml(literatureKeywords)}" /></label>
          <label class="field-label">最大结果数<input class="search-input" id="literatureMax" lang="zh-CN" type="number" min="1" max="100" value="${escapeHtml(maxResults)}" /></label>
          <label class="check-row"><input id="literatureOaOnly" type="checkbox" ${includeOaOnly ? "checked" : ""} /> 仅开放获取</label>
          <label class="check-row"><input id="literatureCampus" type="checkbox" ${useCampusNetwork ? "checked" : ""} /> 已授权校园网</label>
          <label class="check-row"><input id="literatureBrowser" type="checkbox" ${userAuthorizedBrowser ? "checked" : ""} /> 已授权浏览器</label>
          <button class="button primary" type="button" id="runLiteratureTask">运行</button>
        </div>
        <div id="literatureRunResult">${lastLiteratureRun ? jsonDetails("最新文献任务结果", lastLiteratureRun) : ""}</div>
      </div>
      <div class="panel pad" id="libraryContent">${emptyState("正在加载文献库", "正在读取项目证据记录。")}</div>
    </div>
  </section>`;

  const [references, chunks, kb, rag, tasks, requests, files, unmatched] = await Promise.all([
    getReferences(appState.activeProjectId, search),
    getReferenceChunks(appState.activeProjectId),
    getKnowledgeBaseEntries(appState.activeProjectId),
    getRagQueries(appState.activeProjectId),
    getLiteratureSearchTasks(appState.activeProjectId),
    getPaperRequests(appState.activeProjectId),
    getFiles(appState.activeProjectId),
    getUnmatchedPdfs(appState.activeProjectId),
  ]);
  const data = {
    引用: firstArray(references.data, ["references"]),
    文本块: firstArray(chunks.data, ["reference_chunks", "chunks"]),
    知识库条目: firstArray(kb.data, ["knowledge_base_entries", "entries"]),
    "RAG 查询": firstArray(rag.data, ["rag_queries", "queries"]),
    文献任务: firstArray(tasks.data, ["literature_search_tasks", "tasks"]),
    论文请求: firstArray(requests.data, ["paper_requests", "requests"]),
    文件: firstArray(files.data, ["files"]),
    "未匹配 PDF": firstArray(unmatched.data, ["unmatched_pdfs", "files"]),
  };
  const resultByTab = { 引用: references, 文本块: chunks, 知识库条目: kb, "RAG 查询": rag, 文献任务: tasks, 论文请求: requests, 文件: files, "未匹配 PDF": unmatched };
  const result = resultByTab[activeTab];
  root.querySelector("#libraryContent").innerHTML = `
    ${tabButtons()}
    ${result.ok ? renderRows(data[activeTab] || [], `暂无${activeTab}`) : apiErrorCard(result, `${activeTab}接口不可用`)}
    ${jsonDetails("文献库原始数据", Object.fromEntries(Object.entries(resultByTab).map(([key, value]) => [key, value.data])))}
  `;

  root.querySelector("#librarySearch").addEventListener("input", (event) => {
    search = event.target.value;
    renderLibraryView({ root });
  });
  root.querySelectorAll("[data-library-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.libraryTab;
      renderLibraryView({ root });
    });
  });
  root.querySelector("#runLiteratureTask").addEventListener("click", async () => {
    literatureKeywords = root.querySelector("#literatureKeywords").value;
    maxResults = Number(root.querySelector("#literatureMax").value || 10);
    includeOaOnly = root.querySelector("#literatureOaOnly").checked;
    useCampusNetwork = root.querySelector("#literatureCampus").checked;
    userAuthorizedBrowser = root.querySelector("#literatureBrowser").checked;
    const result = await runProductFeature("literature_harvest_workflow", {
      project_id: appState.activeProjectId,
      mode: userAuthorizedBrowser || useCampusNetwork ? "normal" : "dry_run",
      keywords: literatureKeywords,
      max_results: maxResults,
      include_oa_only: includeOaOnly,
      use_campus_network: useCampusNetwork,
      authorization: { browser: userAuthorizedBrowser, campus_network: useCampusNetwork },
    });
    lastLiteratureRun = result.data || { ok: false, error: result.error };
    window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
    renderLibraryView({ root });
  });
}
