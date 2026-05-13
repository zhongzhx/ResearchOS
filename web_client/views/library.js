import {
  getFiles,
  getKnowledgeBaseEntries,
  getLiteratureSearchTasks,
  getPaperRequests,
  getRagQueries,
  getReferenceChunks,
  getReferences,
  getUnmatchedPdfs,
} from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, compactPath, escapeHtml, firstArray, itemCard } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

let activeTab = "References";
let search = "";
const tabs = ["References", "Chunks", "KB Entries", "RAG Queries", "Literature Tasks", "Paper Requests", "Files", "Unmatched PDFs"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-library-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function matches(row) {
  if (!search) return true;
  return JSON.stringify(row).toLowerCase().includes(search.toLowerCase());
}

function renderRows(rows, emptyLabel) {
  const filtered = rows.filter(matches);
  if (!filtered.length) return emptyState(emptyLabel, "No records match the current project and search filter.");
  return `<div class="list">${filtered
    .slice(0, 100)
    .map((row) =>
      itemCard({
        title: row.title || row.question || row.name || row.file_name || row.id || "Untitled",
        subtitle: row.answer_summary || row.summary || row.doi || compactPath(row.path || row.file_path || row.source) || "No summary yet",
        status: row.status || row.year || row.source_provider || row.type || "recorded",
        meta: [row.source, row.year, compactPath(row.file_path)].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

export async function renderLibraryView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">Library / Evidence</h1><p class="page-subtitle">References, chunks, knowledge base entries, RAG queries, literature work, paper requests, files, and unmatched PDFs.</p></div>
      <input class="search-input" id="librarySearch" value="${escapeHtml(search)}" placeholder="Search title, DOI, source, status..." />
    </header>
    <div class="page-scroll"><div class="panel pad" id="libraryContent">${emptyState("Loading library", "Fetching project evidence records.")}</div></div>
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
    References: firstArray(references.data, ["references"]),
    Chunks: firstArray(chunks.data, ["reference_chunks", "chunks"]),
    "KB Entries": firstArray(kb.data, ["knowledge_base_entries", "entries"]),
    "RAG Queries": firstArray(rag.data, ["rag_queries", "queries"]),
    "Literature Tasks": firstArray(tasks.data, ["literature_search_tasks", "tasks"]),
    "Paper Requests": firstArray(requests.data, ["paper_requests", "requests"]),
    Files: firstArray(files.data, ["files"]),
    "Unmatched PDFs": firstArray(unmatched.data, ["unmatched_pdfs", "files"]),
  };
  const resultByTab = { References: references, Chunks: chunks, "KB Entries": kb, "RAG Queries": rag, "Literature Tasks": tasks, "Paper Requests": requests, Files: files, "Unmatched PDFs": unmatched };
  const result = resultByTab[activeTab];
  root.querySelector("#libraryContent").innerHTML = `
    ${tabButtons()}
    ${result.ok ? renderRows(data[activeTab] || [], `No ${activeTab.toLowerCase()} yet`) : apiErrorCard(result, `${activeTab} endpoint unavailable`)}
    ${jsonDetails("Raw library payload", Object.fromEntries(Object.entries(resultByTab).map(([key, value]) => [key, value.data])))}
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
}
