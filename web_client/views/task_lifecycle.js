import { getTask, getTasks } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, asArray, badge, escapeHtml, itemCard, loadingPanel, text } from "../components/cards.js";
import { detailsBlock, fieldList } from "../components/details.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

let taskStatusFilter = "";
let taskTypeFilter = "";
let taskSearch = "";

function pipelineName(run) {
  return run?.task_spec?.input_data?.pipeline_name || run?.task_spec?.intent || run?.task_spec?.task_type || run?.task_type || "暂无数据";
}

function legacyMetadata(run) {
  return run?.metadata || run?.mvp_metadata || run?.raw_metadata || run?.legacy_metadata || {};
}

function lifecycleSections(run) {
  const taskSpec = run?.task_spec || run?.research_task?.task_spec || {};
  const execution = run?.execution_result || run?.research_task?.execution || {};
  const validation = run?.validation_report || run?.research_task?.validation || {};
  const memory = run?.memory_update || run?.memory_commit || run?.brain_memory_write || run?.research_task?.memory_commit || {};
  const handoff = run?.handoff || run?.handoff_summary || run?.research_task?.handoff || run?.summary;
  const artifacts = execution.artifacts || execution.output_files || run?.artifacts || run?.output_files || [];
  const contract = run?.research_task?.contract || run?.contract || {};
  const plan = run?.research_task?.plan || run?.plan || {};
  const metadata = legacyMetadata(run);
  return [
    ["Goal", fieldList([["用户问题", taskSpec.user_query || run?.user_query || run?.title], ["意图", taskSpec.intent || run?.intent], ["成功标准", taskSpec.success_criteria || run?.success_criteria]])],
    ["Plan", fieldList([["选择流程", pipelineName(run)], ["阶段", asArray(taskSpec.stages || plan.stages).join(", ")], ["所需技能", asArray(taskSpec.required_skills || plan.required_skills).join(", ")]]) + jsonViewer(plan)],
    ["Contract", jsonViewer(contract.allowed_tools || contract.forbidden_tools || contract.expected_outputs ? contract : {
      allowed_tools: taskSpec.allowed_tools || [],
      forbidden_tools: taskSpec.forbidden_tools || [],
      expected_outputs: taskSpec.expected_outputs || [],
      validation_rules: taskSpec.validation_rules || [],
      source_requirements: taskSpec.source_requirements || [],
    })],
    ["Execution", fieldList([["状态", execution.status || run?.status], ["技能运行 id", execution.skillrun_id || run?.skillrun_id], ["开始时间", execution.started_at || run?.started_at], ["完成时间", execution.finished_at || run?.finished_at], ["错误", asArray(execution.errors || run?.errors).join("; ") || text(run?.error, "无记录")], ["未解决项", asArray(execution.unresolved_items || run?.unresolved_items).join("; ")]])],
    ["Artifacts", artifacts.length ? jsonViewer(artifacts) : "<p>暂无数据</p>"],
    ["Validation", fieldList([["可返回", validation.safe_to_return], ["可入库", validation.safe_to_promote], ["问题", asArray(validation.issues).join("; ") || "无记录"]]) + jsonViewer(validation)],
    ["Handoff", `<p>${escapeHtml(text(handoff))}</p>`],
    ["Memory Commit", jsonViewer({
      promoted_pages: memory.promoted_pages || run?.memory_pages || [],
      claims: memory.promoted_claims || memory.claims || [],
      datasets: memory.datasets || [],
      decisions: memory.decisions || [],
      failures: memory.failures || [],
      pending_skill: run?.pending_skill || null,
    })],
    ["legacy MVP metadata", jsonViewer(metadata)],
  ];
}

function renderLastRun(run) {
  if (!run) {
    return emptyState("暂无任务流程记录", "从聊天发起研究请求后，这里会显示 Goal、Plan、Contract、Execution、Artifacts、Validation、Handoff 和 Memory Commit。");
  }
  return `<div class="panel pad grid">
    <div class="badge-row">
      ${badge(`流程：${pipelineName(run)}`, "success")}
      ${badge(`状态：${text(run?.execution_result?.status || run?.status, "未知")}`)}
      ${badge(`技能运行：${text(run?.execution_result?.skillrun_id || run?.skillrun_id, "无")}`)}
    </div>
    ${lifecycleSections(run).map(([title, body], index) => detailsBlock(title, body, index < 2)).join("")}
    ${jsonDetails("任务流程原始数据", run)}
  </div>`;
}

function taskMatches(task) {
  const status = String(task.status || task.task_status || "").toLowerCase();
  const type = String(task.task_type || task.type || task.intent || "").toLowerCase();
  const body = JSON.stringify(task).toLowerCase();
  return (
    (!taskStatusFilter || status.includes(taskStatusFilter.toLowerCase())) &&
    (!taskTypeFilter || type.includes(taskTypeFilter.toLowerCase())) &&
    (!taskSearch || body.includes(taskSearch.toLowerCase()))
  );
}

function taskFilters() {
  return `<div class="form-grid">
    <label class="field-label">status<input class="search-input" id="taskStatusFilter" value="${escapeHtml(taskStatusFilter)}" /></label>
    <label class="field-label">task_type<input class="search-input" id="taskTypeFilter" value="${escapeHtml(taskTypeFilter)}" /></label>
    <label class="field-label">query<input class="search-input" id="taskSearch" value="${escapeHtml(taskSearch)}" /></label>
  </div>`;
}

export async function renderTaskLifecycleView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">任务流程</h1><p class="page-subtitle">每个研究任务都会整理为 Goal、Plan、Contract、Execution、Artifacts、Validation、Handoff 和 Memory Commit。</p></div>
    </header>
    <div class="split-layout">
      <div class="panel pad"><div id="taskList">${loadingPanel("正在加载任务")}</div></div>
      <div class="page-scroll" id="taskDetail">${renderLastRun(appState.lastRunResult)}</div>
    </div>
  </section>`;

  const result = await getTasks(appState.activeProjectId);
  const tasks = result.ok ? result.data.tasks || result.data.agent_tasks || [] : [];
  const list = root.querySelector("#taskList");
  if (!result.ok) {
    list.innerHTML = apiErrorCard(result, "任务列表不可用");
    return;
  }
  const filteredTasks = tasks.filter(taskMatches);
  if (!tasks.length) {
    list.innerHTML = `${taskFilters()}${emptyState("暂无任务", "从聊天发起研究请求后，任务记录会显示在这里。")}`;
    return;
  }
  list.innerHTML = `${taskFilters()}<div class="list">${filteredTasks
    .slice(0, 60)
    .map((task) =>
      itemCard({
        title: task.title || task.user_query || task.task_type || task.id,
        subtitle: task.summary || task.current_stage || task.task_id || "仅有任务元数据",
        status: task.status || "已记录",
        clickable: true,
        data: task.id || task.task_id,
      }),
    )
    .join("")}</div>`;
  ["taskStatusFilter", "taskTypeFilter", "taskSearch"].forEach((id) => {
    root.querySelector(`#${id}`).addEventListener("input", (event) => {
      if (id === "taskStatusFilter") taskStatusFilter = event.target.value;
      if (id === "taskTypeFilter") taskTypeFilter = event.target.value;
      if (id === "taskSearch") taskSearch = event.target.value;
      renderTaskLifecycleView({ root });
    });
  });
  root.querySelectorAll("[data-item-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const detail = await getTask(button.dataset.itemId);
      const task = detail.data?.task || detail.data || {};
      root.querySelector("#taskDetail").innerHTML = detail.ok ? renderLastRun(task) : apiErrorCard(detail, "任务详情不可用");
    });
  });
}
