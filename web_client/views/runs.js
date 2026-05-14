import { getAgentFeed, getExecutionMemory, getSkillRuns, getTasks, getWorkflowBoard } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, firstArray, itemCard, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

let activeTab = "Tasks";
const tabs = ["Tasks", "SkillRuns", "Execution Memory", "Agent Feed", "Workflow Board", "Artifacts", "Errors"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-runs-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function renderRows(rows, emptyLabel) {
  if (!rows.length) return emptyState(emptyLabel, "Runs and execution records will appear when AURA performs work.");
  return `<div class="list">${rows
    .slice(0, 80)
    .map((row) =>
      itemCard({
        title: row.title || row.skill_name || row.skill_id || row.task_type || row.id || row.task_id || "Execution record",
        subtitle: row.summary || row.message || row.logs_summary || row.error || row.current_stage || "No summary yet",
        status: row.status || row.task_status || "recorded",
        meta: [row.started_at, row.finished_at, row.skillrun_id, text((row.output_files || []).length ? `${row.output_files.length} files` : "")].filter(Boolean),
      }) + jsonDetails("Run details", row)
    )
    .join("")}</div>`;
}

export async function renderRunsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">Runs / Execution</h1><p class="page-subtitle">Tasks, SkillRuns, execution memory, agent feed, and workflow board status.</p></div>
    </header>
    <div class="page-scroll"><div class="panel pad" id="runsContent">${emptyState("Loading runs", "Fetching execution state.")}</div></div>
  </section>`;

  const [tasks, skillRuns, memory, feed, board] = await Promise.all([
    getTasks(appState.activeProjectId),
    getSkillRuns(appState.activeProjectId),
    getExecutionMemory(appState.activeProjectId),
    getAgentFeed(appState.activeProjectId),
    getWorkflowBoard(appState.activeProjectId),
  ]);
  const results = {
    Tasks: tasks,
    SkillRuns: skillRuns,
    "Execution Memory": memory,
    "Agent Feed": feed,
    "Workflow Board": board,
  };
  const rows = {
    Tasks: firstArray(tasks.data, ["tasks", "agent_tasks"]),
    SkillRuns: firstArray(skillRuns.data, ["skill_runs"]),
    "Execution Memory": firstArray(memory.data, ["execution_memory"]),
    "Agent Feed": firstArray(feed.data, ["items", "inbox", "agent_feed"]),
    "Workflow Board": firstArray(board.data, ["columns", "tasks", "items"]),
  };
  rows.Artifacts = [...rows.Tasks, ...rows.SkillRuns, ...rows["Execution Memory"]].flatMap((row) => row.artifacts || row.output_files || row.output_object_refs || []);
  rows.Errors = [...rows.Tasks, ...rows.SkillRuns, ...rows["Execution Memory"]].filter((row) => row.error || row.errors || String(row.status || "").toLowerCase().includes("fail"));
  const result = results[activeTab];
  const syntheticOk = activeTab === "Artifacts" || activeTab === "Errors";
  root.querySelector("#runsContent").innerHTML = `
    ${tabButtons()}
    ${syntheticOk || result.ok ? renderRows(rows[activeTab] || [], `No ${activeTab.toLowerCase()} yet`) : apiErrorCard(result, `${activeTab} endpoint unavailable`)}
    ${jsonDetails("Raw execution payload", Object.fromEntries(Object.entries(results).map(([key, value]) => [key, value.data])))}
  `;
  root.querySelectorAll("[data-runs-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.runsTab;
      renderRunsView({ root });
    });
  });
}
