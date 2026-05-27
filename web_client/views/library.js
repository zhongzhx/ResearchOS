import {
  buildKnowledgeBase,
  createLiteratureSearchTask,
  createPaperRequest,
  expandLiteratureQuery,
  generatePaperRequests,
  getFiles,
  getKnowledgeBaseEntries,
  getLiteratureSearchTasks,
  getPaperRequests,
  getRagQueries,
  getReferenceChunks,
  getReferences,
  getUnmatchedPdfs,
  mineLiteratureKeywords,
  processPaperRequestWatchFolder,
  queryResearchOsRag,
  runLiteratureSearch,
} from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, compactPath, escapeHtml, firstArray, itemCard, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

let activeTab = "引用";
let search = "";
let literatureKeywords = "RAW264.7, innate immunity";
let maxResults = 10;
let includeOaOnly = true;
let paperRequestDoi = "";
let paperRequestTitle = "";
let paperRequestReason = "全文需要手动补充";
let ragQuery = "";
let actionStatus = null;
let lastLiteratureResult = null;
let lastRagResult = null;
let libraryRefreshSeq = 0;
const tabs = ["引用", "文本块", "知识库条目", "RAG 查询", "文献任务", "论文请求", "文件", "未匹配 PDF"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-library-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function currentProjectId() {
  return String(appState.activeProjectId || "").trim();
}

function projectSelectionRequiredState() {
  return emptyState("请先选择或创建项目", "每个项目拥有独立资料库，选择项目后才能查看或操作证据内容。");
}

function keywordList() {
  return literatureKeywords
    .split(/[,\n，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function literaturePayload() {
  return {
    project_id: currentProjectId(),
    query: literatureKeywords,
    keywords: keywordList(),
    max_results: Math.max(1, Number(maxResults || 10)),
    oa_only: Boolean(includeOaOnly),
  };
}

function statusBlock() {
  if (!actionStatus) return "";
  const status = actionStatus.status || (actionStatus.ok ? "success" : "error");
  const label = actionStatus.ok ? "成功" : status === "loading" ? "处理中" : "未完成";
  const detail = actionStatus.error || actionStatus.detail || actionStatus.message || "";
  return `<div class="notice ${escapeHtml(status)}" id="libraryActionStatus"><strong>${escapeHtml(label)}</strong><p>${escapeHtml(detail || status)}</p></div>`;
}

function matches(row) {
  if (!search) return true;
  return JSON.stringify(row).toLowerCase().includes(search.toLowerCase());
}

function resultText(result, successLabel) {
  if (!result) return "";
  if (result.ok) return successLabel;
  return result.data?.status || result.error || "not_connected";
}

async function runLibraryAction(root, label, action) {
  actionStatus = { ok: false, status: "loading", message: `${label}中...` };
  const target = root.querySelector("#libraryActionStatus");
  if (target) target.innerHTML = `<strong>处理中</strong><p>${escapeHtml(label)}中...</p>`;
  const result = await action();
  actionStatus = {
    ok: Boolean(result.ok),
    status: result.data?.status || (result.ok ? "success" : "not_connected"),
    message: resultText(result, `${label}完成`),
    detail: result.data?.detail || "",
    error: result.error || "",
  };
  window.dispatchEvent(new CustomEvent("researchos:refresh-shell"));
  await refreshLibraryContent(root);
}

function renderRows(rows, emptyLabel) {
  const filtered = rows.filter(matches);
  if (!filtered.length) return emptyState(emptyLabel, "当前项目和搜索条件下没有匹配记录。");
  return `<div class="list">${filtered
    .slice(0, 100)
    .map((row) =>
      itemCard({
        title: row.title || row.question || row.name || row.file_name || row.id || row.task_id || "未命名",
        subtitle: row.answer_summary || row.summary || row.doi || row.reason || compactPath(row.path || row.file_path || row.source) || "暂无摘要",
        status: row.status || row.year || row.source_provider || row.type || "已记录",
        meta: [row.source, row.year, row.suggested_action, compactPath(row.file_path)].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

function renderPaperRequests(rows) {
  if (!rows.length) return emptyState("暂无论文请求", "无法自动获取的全文会作为手动下载队列显示在这里。");
  return `<div class="list">${rows
    .slice(0, 80)
    .map((row) => `<article class="item-card">
      <h3 class="item-title">${escapeHtml(text(row.title || row.paper_title || row.doi, "论文请求"))}</h3>
      <p class="item-subtitle">DOI：${escapeHtml(text(row.doi, "暂无 DOI"))}</p>
      <div class="item-meta">
        <span class="badge muted">${escapeHtml(text(row.status, "pending"))}</span>
        <span class="badge muted">${escapeHtml(text(row.reason, "未记录原因"))}</span>
        <span class="badge warning">${escapeHtml(text(row.suggested_action || row.action, "手动补充全文"))}</span>
      </div>
    </article>`)
    .join("")}</div>`;
}

function literatureTaskPanel() {
  return `<div class="panel pad grid">
    <div class="section-heading"><div><h2>文献采集任务</h2><p>创建并运行当前项目的 legacy ResearchOS 文献任务。</p></div></div>
    <div class="form-grid">
      <label class="field-label">关键词 / 检索式<input class="search-input" id="literatureKeywords" lang="zh-CN" value="${escapeHtml(literatureKeywords)}" /></label>
      <label class="field-label">最大结果数<input class="search-input" id="literatureMax" type="number" min="1" max="100" value="${escapeHtml(maxResults)}" /></label>
      <label class="check-row"><input id="literatureOaOnly" type="checkbox" ${includeOaOnly ? "checked" : ""} /> OA only</label>
      <button class="button secondary" type="button" id="createLiteratureTask">创建任务</button>
      <button class="button secondary" type="button" id="expandLiteratureQuery">扩展关键词</button>
      <button class="button secondary" type="button" id="mineLiteratureKeywords">挖掘关键词</button>
      <button class="button primary" type="button" id="runLiteratureSearch">运行检索</button>
    </div>
    ${lastLiteratureResult ? jsonDetails("最新文献采集结果", lastLiteratureResult) : ""}
  </div>`;
}

function paperRequestPanel(requests) {
  return `<div class="panel pad grid">
    <div class="section-heading"><div><h2>论文请求 / 手动下载队列</h2><p>只记录合规手动下载需求，不接外部下载、校园网授权或 paywall 绕过。</p></div></div>
    <div class="form-grid">
      <label class="field-label">DOI<input class="search-input" id="paperRequestDoi" value="${escapeHtml(paperRequestDoi)}" /></label>
      <label class="field-label">标题<input class="search-input" id="paperRequestTitle" value="${escapeHtml(paperRequestTitle)}" /></label>
      <label class="field-label">原因<input class="search-input" id="paperRequestReason" value="${escapeHtml(paperRequestReason)}" /></label>
      <button class="button secondary" type="button" id="createPaperRequest">创建 paper request</button>
      <button class="button secondary" type="button" id="generatePaperRequests">从任务生成 paper requests</button>
      <button class="button secondary" type="button" id="processWatchFolder">处理 watch folder</button>
    </div>
    ${renderPaperRequests(requests)}
  </div>`;
}

function kbRagPanel(kbRows, chunkRows, ragRows) {
  return `<div class="panel pad grid">
    <div class="section-heading"><div><h2>知识库查询</h2><p>构建当前项目知识库，并查询已入库文本块。</p></div></div>
    <div class="form-grid">
      <button class="button secondary" type="button" id="buildKnowledgeBase">构建知识库</button>
      <label class="field-label">检索问题<input class="search-input" id="ragQuery" lang="zh-CN" value="${escapeHtml(ragQuery)}" /></label>
      <button class="button primary" type="button" id="queryRag">查询知识库</button>
    </div>
    ${lastRagResult ? `<div class="grid">
      ${itemCard({ title: "回答", subtitle: lastRagResult.answer || lastRagResult.data?.answer || lastRagResult.error || "暂无回答", status: lastRagResult.status || (lastRagResult.ok === false ? "not_connected" : "ok") })}
      ${jsonDetails("来源", lastRagResult.sources || lastRagResult.data?.sources || [])}
      ${jsonDetails("文本块", lastRagResult.chunks || lastRagResult.data?.chunks || [])}
    </div>` : ""}
    <div class="metric-grid">
      <div class="metric-card"><strong>${kbRows.length}</strong><span>知识库条目</span></div>
      <div class="metric-card"><strong>${chunkRows.length}</strong><span>文本块</span></div>
      <div class="metric-card"><strong>${ragRows.length}</strong><span>查询历史</span></div>
    </div>
    ${ragRows.length ? jsonDetails("查询历史", ragRows) : ""}
  </div>`;
}

async function refreshLibraryContent(root) {
  const refreshId = ++libraryRefreshSeq;
  const workbench = root.querySelector("#libraryWorkbench");
  const content = root.querySelector("#libraryContent");
  const status = root.querySelector("#libraryActionStatus");
  if (!workbench || !content) return;
  if (status) status.outerHTML = statusBlock();
  const projectId = currentProjectId();
  if (!projectId) {
    workbench.innerHTML = projectSelectionRequiredState();
    content.innerHTML = projectSelectionRequiredState();
    return;
  }
  workbench.innerHTML = emptyState("正在加载文献工作台", "正在读取项目证据记录。");
  content.innerHTML = emptyState("正在加载文献库", "正在读取项目证据记录。");
  const [references, chunks, kb, rag, tasks, requests, files, unmatched] = await Promise.all([
    getReferences(projectId, search),
    getReferenceChunks(projectId),
    getKnowledgeBaseEntries(projectId),
    getRagQueries(projectId),
    getLiteratureSearchTasks(projectId),
    getPaperRequests(projectId),
    getFiles(projectId),
    getUnmatchedPdfs(projectId),
  ]);
  if (refreshId !== libraryRefreshSeq) return;
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
  workbench.innerHTML = `
    ${literatureTaskPanel()}
    ${paperRequestPanel(data.论文请求)}
    ${kbRagPanel(data.知识库条目, data.文本块, data["RAG 查询"])}
  `;
  content.innerHTML = `
    ${tabButtons()}
    ${result.ok ? renderRows(data[activeTab] || [], `暂无${activeTab}`) : apiErrorCard(result, `${activeTab}接口不可用`)}
    ${jsonDetails("文献库原始数据", Object.fromEntries(Object.entries(resultByTab).map(([key, value]) => [key, value.data])))}
  `;
  bindLibraryContentEvents(root);
}

function bindLibraryContentEvents(root) {
  root.querySelectorAll("[data-library-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.libraryTab;
      refreshLibraryContent(root);
    });
  });

  const syncInputs = () => {
    literatureKeywords = root.querySelector("#literatureKeywords").value;
    maxResults = Number(root.querySelector("#literatureMax").value || 10);
    includeOaOnly = root.querySelector("#literatureOaOnly").checked;
    paperRequestDoi = root.querySelector("#paperRequestDoi").value.trim();
    paperRequestTitle = root.querySelector("#paperRequestTitle").value.trim();
    paperRequestReason = root.querySelector("#paperRequestReason").value.trim();
    ragQuery = root.querySelector("#ragQuery").value.trim();
  };

  root.querySelector("#createLiteratureTask").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "创建任务", async () => {
      const result = await createLiteratureSearchTask(literaturePayload());
      lastLiteratureResult = result.data || { ok: false, error: result.error };
      return result;
    });
  });
  root.querySelector("#expandLiteratureQuery").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "扩展关键词", async () => {
      const result = await expandLiteratureQuery(literaturePayload());
      lastLiteratureResult = result.data || { ok: false, error: result.error };
      return result;
    });
  });
  root.querySelector("#mineLiteratureKeywords").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "挖掘关键词", async () => {
      const result = await mineLiteratureKeywords(literaturePayload());
      lastLiteratureResult = result.data || { ok: false, error: result.error };
      return result;
    });
  });
  root.querySelector("#runLiteratureSearch").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "运行检索", async () => {
      const result = await runLiteratureSearch(literaturePayload());
      lastLiteratureResult = result.data || { ok: false, error: result.error };
      return result;
    });
  });
  root.querySelector("#createPaperRequest").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "创建 paper request", () =>
      createPaperRequest({ project_id: currentProjectId(), doi: paperRequestDoi, title: paperRequestTitle, reason: paperRequestReason, suggested_action: "manual_download" }),
    );
  });
  root.querySelector("#generatePaperRequests").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "生成 paper requests", () => generatePaperRequests({ project_id: currentProjectId() }));
  });
  root.querySelector("#processWatchFolder").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "处理 watch folder", () => processPaperRequestWatchFolder({ project_id: currentProjectId() }));
  });
  root.querySelector("#buildKnowledgeBase").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "构建知识库", () => buildKnowledgeBase({ project_id: currentProjectId() }));
  });
  root.querySelector("#queryRag").addEventListener("click", async () => {
    syncInputs();
    await runLibraryAction(root, "查询知识库", async () => {
      const result = await queryResearchOsRag({ project_id: currentProjectId(), query: ragQuery });
      lastRagResult = result.data || { ok: false, status: result.status, error: result.error };
      return result;
    });
  });
}

export async function renderLibraryView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">文献库 / 证据</h1><p class="page-subtitle">查看引用、文本块、知识库条目、RAG 查询、文献任务、论文请求、文件和未匹配 PDF。</p></div>
      <input class="search-input" id="librarySearch" lang="zh-CN" value="${escapeHtml(search)}" placeholder="搜索标题、DOI、来源或状态..." />
    </header>
    <div class="page-scroll">
      ${statusBlock()}
      <div id="libraryWorkbench">${emptyState("正在加载文献工作台", "正在读取项目证据记录。")}</div>
      <div class="panel pad" id="libraryContent">${emptyState("正在加载文献库", "正在读取项目证据记录。")}</div>
    </div>
  </section>`;

  await refreshLibraryContent(root);
  root.querySelector("#librarySearch").addEventListener("input", (event) => {
    search = event.target.value;
    refreshLibraryContent(root);
  });
}
