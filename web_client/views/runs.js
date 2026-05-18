import { getAgentFeed, getExecutionMemory, getRuntimeStatus, getSchedulerStatus, getSkillRuns, getTasks, getWorkflowBoard, promoteExecutionMemory } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, escapeHtml, firstArray, itemCard, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

let activeTab = "任务";
let statusFilter = "";
let skillIdFilter = "";
let promoteStatus = null;
const tabs = ["任务", "技能运行", "执行记忆", "运行状态", "Agent 动态", "工作流看板", "产物", "错误"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-runs-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function rowMatches(row) {
  const status = String(row.status || row.task_status || "").toLowerCase();
  const skillId = String(row.skill_id || row.skillrun_id || row.source_skillrun_id || "").toLowerCase();
  return (!statusFilter || status.includes(statusFilter.toLowerCase())) && (!skillIdFilter || skillId.includes(skillIdFilter.toLowerCase()));
}

function renderFilters() {
  return `<div class="form-grid">
    <label class="field-label">状态<input class="search-input" id="runStatusFilter" value="${escapeHtml(statusFilter)}" placeholder="运行中 / 已完成 / 失败" /></label>
    <label class="field-label">技能运行 ID<input class="search-input" id="skillIdFilter" value="${escapeHtml(skillIdFilter)}" placeholder="keyword-research-harvest" /></label>
  </div>`;
}

function renderSkillRun(row) {
  return `<article class="item-card">
    <h3 class="item-title">${escapeHtml(text(row.skill_id || row.skill_name || row.id, "技能运行"))}</h3>
    <p class="item-subtitle">${escapeHtml(text(row.summary || row.logs_summary || row.error, "暂无摘要"))}</p>
    <div class="item-meta">
      <span class="badge muted">${escapeHtml(text(row.status, "unknown"))}</span>
      <span class="badge muted">项目：${escapeHtml(text(row.project_id))}</span>
      <span class="badge muted">开始：${escapeHtml(text(row.started_at || row.created_at))}</span>
      <span class="badge muted">完成：${escapeHtml(text(row.finished_at || row.updated_at))}</span>
    </div>
    ${jsonDetails("产物", row.artifacts || row.output_files || row.output_object_refs || [])}
    ${jsonDetails("校验报告", row.validation_report || {})}
    ${jsonDetails("错误和未解决项", { errors: row.errors || row.error || [], unresolved_items: row.unresolved_items || [] })}
  </article>`;
}

function renderExecutionMemory(row) {
  const memoryId = row.id || row.memory_id || row.execution_memory_id || "";
  const safe = Boolean(row.safe_to_promote);
  const promoted = Boolean(row.promoted || row.promoted_at || row.status === "promoted");
  const promoteButton = safe && !promoted ? `<button class="button secondary small" type="button" data-promote-memory="${escapeHtml(memoryId)}">加入研究记忆</button>` : "";
  return `<article class="item-card">
    <h3 class="item-title">${escapeHtml(text(row.summary || row.title || memoryId, "执行记忆"))}</h3>
    <p class="item-subtitle">来源技能运行：${escapeHtml(text(row.skillrun_id || row.source_skillrun_id || row.source_skill_run_id))}</p>
    <div class="item-meta">
      <span class="badge muted">置信度：${escapeHtml(text(row.confidence))}</span>
      <span class="badge ${safe ? "success" : "warning"}">可加入项目记忆：${escapeHtml(safe ? "是" : "否")}</span>
      <span class="badge muted">已加入：${escapeHtml(promoted ? "是" : "否")}</span>
    </div>
    <div class="inline-actions">${promoteButton}</div>
    ${jsonDetails("执行记忆详情", row)}
  </article>`;
}

function renderRows(rows, emptyLabel) {
  const filtered = rows.filter(rowMatches);
  if (!filtered.length) return emptyState(emptyLabel, "AURA 执行工作后会在这里显示运行和执行记录。");
  return `<div class="list">${filtered
    .slice(0, 80)
    .map((row) =>
      itemCard({
        title: row.title || row.skill_name || row.skill_id || row.task_type || row.id || row.task_id || "执行记录",
        subtitle: row.summary || row.message || row.logs_summary || row.error || row.current_stage || "暂无摘要",
        status: row.status || row.task_status || "已记录",
        meta: [row.started_at, row.finished_at, row.project_id, row.skillrun_id].filter(Boolean),
      }) + jsonDetails("运行详情", row),
    )
    .join("")}</div>`;
}

function statusPanel(runtime, scheduler) {
  return `<div class="grid">
    ${runtime.ok ? jsonDetails("运行时状态", runtime.data) : apiErrorCard(runtime, "运行时状态不可用")}
    ${scheduler.ok ? jsonDetails("调度器状态", scheduler.data) : apiErrorCard(scheduler, "调度器状态不可用")}
  </div>`;
}

export async function renderRunsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">运行记录 / 执行</h1><p class="page-subtitle">查看任务、技能运行、执行记忆、Agent 动态和工作流看板状态。</p></div>
    </header>
    <div class="page-scroll"><div class="panel pad" id="runsContent">${emptyState("正在加载运行记录", "正在读取执行状态。")}</div></div>
  </section>`;

  const [tasks, skillRuns, memory, feed, board, runtime, scheduler] = await Promise.all([
    getTasks(appState.activeProjectId),
    getSkillRuns(appState.activeProjectId),
    getExecutionMemory(appState.activeProjectId),
    getAgentFeed(appState.activeProjectId),
    getWorkflowBoard(appState.activeProjectId),
    getRuntimeStatus(appState.activeProjectId),
    getSchedulerStatus(appState.activeProjectId),
  ]);
  const results = {
    任务: tasks,
    技能运行: skillRuns,
    执行记忆: memory,
    "Agent 动态": feed,
    工作流看板: board,
    运行状态: { ok: runtime.ok || scheduler.ok, data: { runtime: runtime.data, scheduler: scheduler.data } },
  };
  const rows = {
    任务: firstArray(tasks.data, ["tasks", "agent_tasks"]),
    技能运行: firstArray(skillRuns.data, ["skill_runs"]).filter(rowMatches),
    执行记忆: firstArray(memory.data, ["execution_memory", "items"]).filter(rowMatches),
    "Agent 动态": firstArray(feed.data, ["items", "inbox", "agent_feed"]),
    工作流看板: firstArray(board.data, ["columns", "tasks", "items"]),
  };
  rows.产物 = [...rows.任务, ...rows.技能运行, ...rows.执行记忆].flatMap((row) => row.artifacts || row.output_files || row.output_object_refs || []);
  rows.错误 = [...rows.任务, ...rows.技能运行, ...rows.执行记忆].filter((row) => row.error || row.errors || String(row.status || "").toLowerCase().includes("fail"));
  const result = results[activeTab];
  const syntheticOk = activeTab === "产物" || activeTab === "错误";
  const tabBody =
    activeTab === "技能运行"
      ? `<div class="list">${rows.技能运行.map(renderSkillRun).join("") || emptyState("暂无技能运行", "没有符合过滤条件的技能运行。")}</div>`
      : activeTab === "执行记忆"
        ? `<div class="list">${rows.执行记忆.map(renderExecutionMemory).join("") || emptyState("暂无执行记忆", "没有符合过滤条件的执行记忆。")}</div>`
        : activeTab === "运行状态"
          ? statusPanel(runtime, scheduler)
          : syntheticOk || result.ok
            ? renderRows(rows[activeTab] || [], `暂无${activeTab}`)
            : apiErrorCard(result, `${activeTab}接口不可用`);
  root.querySelector("#runsContent").innerHTML = `
    ${tabButtons()}
    ${renderFilters()}
    ${promoteStatus ? `<div class="notice ${escapeHtml(promoteStatus.ok ? "success" : "error")}">${escapeHtml(promoteStatus.message)}</div>` : ""}
    ${tabBody}
    ${jsonDetails("执行原始数据", Object.fromEntries(Object.entries(results).map(([key, value]) => [key, value.data])))}
  `;
  root.querySelector("#runStatusFilter").addEventListener("input", (event) => {
    statusFilter = event.target.value;
    renderRunsView({ root });
  });
  root.querySelector("#skillIdFilter").addEventListener("input", (event) => {
    skillIdFilter = event.target.value;
    renderRunsView({ root });
  });
  root.querySelectorAll("[data-runs-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.runsTab;
      renderRunsView({ root });
    });
  });
  root.querySelectorAll("[data-promote-memory]").forEach((button) => {
    button.addEventListener("click", async () => {
      const memoryId = button.dataset.promoteMemory;
      if (!confirm(`确认将执行记忆 ${memoryId} 加入研究记忆吗？`)) return;
      const result = await promoteExecutionMemory(memoryId, { project_id: appState.activeProjectId });
      promoteStatus = { ok: result.ok, message: result.ok ? "已加入研究记忆，正在刷新执行记忆和研究记忆状态。" : result.error || "加入研究记忆未完成" };
      await renderRunsView({ root });
    });
  });
}
