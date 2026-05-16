import { getAgentFeed, getExecutionMemory, getSkillRuns, getTasks, getWorkflowBoard } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, firstArray, itemCard, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

let activeTab = "任务";
const tabs = ["任务", "技能运行", "执行记忆", "Agent 动态", "工作流看板", "产物", "错误"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-runs-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function renderRows(rows, emptyLabel) {
  if (!rows.length) return emptyState(emptyLabel, "AURA 执行工作后会在这里显示运行和执行记录。");
  return `<div class="list">${rows
    .slice(0, 80)
    .map((row) =>
      itemCard({
        title: row.title || row.skill_name || row.skill_id || row.task_type || row.id || row.task_id || "执行记录",
        subtitle: row.summary || row.message || row.logs_summary || row.error || row.current_stage || "暂无摘要",
        status: row.status || row.task_status || "已记录",
        meta: [row.started_at, row.finished_at, row.skillrun_id, text((row.output_files || []).length ? `${row.output_files.length} 个文件` : "")].filter(Boolean),
      }) + jsonDetails("运行详情", row)
    )
    .join("")}</div>`;
}

export async function renderRunsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">运行记录 / 执行</h1><p class="page-subtitle">任务、技能运行、执行记忆、Agent 动态和工作流看板状态。</p></div>
    </header>
    <div class="page-scroll"><div class="panel pad" id="runsContent">${emptyState("正在加载运行记录", "正在读取执行状态。")}</div></div>
  </section>`;

  const [tasks, skillRuns, memory, feed, board] = await Promise.all([
    getTasks(appState.activeProjectId),
    getSkillRuns(appState.activeProjectId),
    getExecutionMemory(appState.activeProjectId),
    getAgentFeed(appState.activeProjectId),
    getWorkflowBoard(appState.activeProjectId),
  ]);
  const results = {
    任务: tasks,
    技能运行: skillRuns,
    执行记忆: memory,
    "Agent 动态": feed,
    工作流看板: board,
  };
  const rows = {
    任务: firstArray(tasks.data, ["tasks", "agent_tasks"]),
    技能运行: firstArray(skillRuns.data, ["skill_runs"]),
    执行记忆: firstArray(memory.data, ["execution_memory"]),
    "Agent 动态": firstArray(feed.data, ["items", "inbox", "agent_feed"]),
    工作流看板: firstArray(board.data, ["columns", "tasks", "items"]),
  };
  rows.产物 = [...rows.任务, ...rows.技能运行, ...rows.执行记忆].flatMap((row) => row.artifacts || row.output_files || row.output_object_refs || []);
  rows.错误 = [...rows.任务, ...rows.技能运行, ...rows.执行记忆].filter((row) => row.error || row.errors || String(row.status || "").toLowerCase().includes("fail"));
  const result = results[activeTab];
  const syntheticOk = activeTab === "产物" || activeTab === "错误";
  root.querySelector("#runsContent").innerHTML = `
    ${tabButtons()}
    ${syntheticOk || result.ok ? renderRows(rows[activeTab] || [], `暂无${activeTab}`) : apiErrorCard(result, `${activeTab}接口不可用`)}
    ${jsonDetails("执行原始数据", Object.fromEntries(Object.entries(results).map(([key, value]) => [key, value.data])))}
  `;
  root.querySelectorAll("[data-runs-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.runsTab;
      renderRunsView({ root });
    });
  });
}
