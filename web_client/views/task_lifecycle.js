import { getTask, getTasks } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, asArray, badge, escapeHtml, itemCard, loadingPanel, text } from "../components/cards.js";
import { detailsBlock, fieldList } from "../components/details.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

function pipelineName(run) {
  return run?.task_spec?.input_data?.pipeline_name || run?.task_spec?.intent || run?.task_spec?.task_type || "暂无数据";
}

function lifecycleSections(run) {
  const taskSpec = run?.task_spec || {};
  const execution = run?.execution_result || {};
  const validation = run?.validation_report || {};
  const memory = run?.memory_update || run?.memory_commit || run?.brain_memory_write || {};
  const handoff = run?.handoff || run?.handoff_summary || run?.summary;
  const artifacts = execution.artifacts || execution.output_files || run?.artifacts || [];
  const contract = run?.research_task?.contract || run?.contract || {};
  return [
    ["目标", fieldList([["用户问题", taskSpec.user_query || run?.user_query], ["意图", taskSpec.intent], ["成功标准", taskSpec.success_criteria]])],
    ["计划", fieldList([["选择流程", pipelineName(run)], ["阶段", asArray(taskSpec.stages).join(", ")], ["所需技能", asArray(taskSpec.required_skills).join(", ")]])],
    ["契约", jsonViewer(contract.allowed_tools || contract.forbidden_tools || contract.expected_outputs ? contract : {
      allowed_tools: taskSpec.allowed_tools || [],
      forbidden_tools: taskSpec.forbidden_tools || [],
      expected_outputs: taskSpec.expected_outputs || [],
      validation_rules: taskSpec.validation_rules || [],
      source_requirements: taskSpec.source_requirements || [],
    })],
    ["执行", fieldList([["状态", execution.status], ["技能运行 id", execution.skillrun_id], ["开始时间", execution.started_at], ["完成时间", execution.finished_at], ["错误", asArray(execution.errors).join("; ") || "无记录"], ["未解决项", asArray(execution.unresolved_items).join("; ")]])],
    ["产物", artifacts.length ? jsonViewer(artifacts) : "<p>暂无数据</p>"],
    ["校验", fieldList([["可返回", validation.safe_to_return], ["可入库", validation.safe_to_promote], ["问题", asArray(validation.issues).join("; ") || "无记录"]]) + jsonViewer(validation)],
    ["交接", `<p>${escapeHtml(text(handoff))}</p>`],
    ["记忆", jsonViewer({
      promoted_pages: memory.promoted_pages || run?.memory_pages || [],
      claims: memory.promoted_claims || memory.claims || [],
      datasets: memory.datasets || [],
      decisions: memory.decisions || [],
      failures: memory.failures || [],
      pending_skill: run?.pending_skill || null,
    })],
  ];
}

function renderLastRun(run) {
  if (!run) {
    return emptyState("暂无任务流程记录", "从聊天发起研究请求后，这里会显示目标、计划、契约、执行、产物、校验、交接和记忆。");
  }
  return `<div class="panel pad grid">
    <div class="badge-row">
      ${badge(`流程：${pipelineName(run)}`, "success")}
      ${badge(`状态：${text(run?.execution_result?.status, "未知")}`)}
      ${badge(`技能运行：${text(run?.execution_result?.skillrun_id, "无")}`)}
    </div>
    ${lifecycleSections(run).map(([title, body], index) => detailsBlock(title, body, index < 2)).join("")}
    ${jsonDetails("任务流程原始数据", run)}
  </div>`;
}

export async function renderTaskLifecycleView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">任务流程</h1><p class="page-subtitle">每个研究任务都会整理为目标、计划、契约、执行、产物、校验、交接和记忆。</p></div>
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
  if (!tasks.length) {
    list.innerHTML = emptyState("暂无任务", "从聊天发起研究请求后，任务记录会显示在这里。");
    return;
  }
  list.innerHTML = `<div class="list">${tasks
    .slice(0, 30)
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
  root.querySelectorAll("[data-item-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const detail = await getTask(button.dataset.itemId);
      const task = detail.data?.task || detail.data || {};
      root.querySelector("#taskDetail").innerHTML = detail.ok ? renderLastRun(task) : apiErrorCard(detail, "任务详情不可用");
    });
  });
}
