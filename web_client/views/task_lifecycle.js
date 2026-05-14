import { getTask, getTasks } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, asArray, badge, escapeHtml, itemCard, loadingPanel, text } from "../components/cards.js";
import { detailsBlock, fieldList } from "../components/details.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

function pipelineName(run) {
  return run?.task_spec?.input_data?.pipeline_name || run?.task_spec?.intent || run?.task_spec?.task_type || "Not available yet";
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
    ["Goal", fieldList([["User query", taskSpec.user_query || run?.user_query], ["Intent", taskSpec.intent], ["Success criteria", taskSpec.success_criteria]])],
    ["Plan", fieldList([["Selected pipeline", pipelineName(run)], ["Stages", asArray(taskSpec.stages).join(", ")], ["Required skills", asArray(taskSpec.required_skills).join(", ")]])],
    ["Contract", jsonViewer(contract.allowed_tools || contract.forbidden_tools || contract.expected_outputs ? contract : {
      allowed_tools: taskSpec.allowed_tools || [],
      forbidden_tools: taskSpec.forbidden_tools || [],
      expected_outputs: taskSpec.expected_outputs || [],
      validation_rules: taskSpec.validation_rules || [],
      source_requirements: taskSpec.source_requirements || [],
    })],
    ["Execution", fieldList([["Status", execution.status], ["SkillRun id", execution.skillrun_id], ["Started", execution.started_at], ["Finished", execution.finished_at], ["Errors", asArray(execution.errors).join("; ") || "None recorded"], ["Unresolved items", asArray(execution.unresolved_items).join("; ")]])],
    ["Artifacts", artifacts.length ? jsonViewer(artifacts) : "<p>Not available yet</p>"],
    ["Validation", fieldList([["Safe to return", validation.safe_to_return], ["Safe to promote", validation.safe_to_promote], ["Issues", asArray(validation.issues).join("; ") || "None recorded"]]) + jsonViewer(validation)],
    ["Handoff", `<p>${escapeHtml(text(handoff))}</p>`],
    ["Memory", jsonViewer({
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
    return emptyState("No lifecycle run yet", "Run a task from Chat to see goal, plan, contract, execution, artifacts, validation, handoff, and memory.");
  }
  return `<div class="panel pad grid">
    <div class="badge-row">
      ${badge(`Pipeline: ${pipelineName(run)}`, "success")}
      ${badge(`Status: ${text(run?.execution_result?.status, "unknown")}`)}
      ${badge(`SkillRun: ${text(run?.execution_result?.skillrun_id, "none")}`)}
    </div>
    ${lifecycleSections(run).map(([title, body], index) => detailsBlock(title, body, index < 2)).join("")}
    ${jsonDetails("Raw lifecycle source", run)}
  </div>`;
}

export async function renderTaskLifecycleView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">Task Lifecycle</h1><p class="page-subtitle">Each research task is organized as goal, plan, contract, execution, artifacts, validation, handoff, and memory.</p></div>
    </header>
    <div class="split-layout">
      <div class="panel pad"><div id="taskList">${loadingPanel("Loading tasks")}</div></div>
      <div class="page-scroll" id="taskDetail">${renderLastRun(appState.lastRunResult)}</div>
    </div>
  </section>`;

  const result = await getTasks(appState.activeProjectId);
  const tasks = result.ok ? result.data.tasks || result.data.agent_tasks || [] : [];
  const list = root.querySelector("#taskList");
  if (!result.ok) {
    list.innerHTML = apiErrorCard(result, "Task list is unavailable");
    return;
  }
  if (!tasks.length) {
    list.innerHTML = emptyState("No tasks yet", "Send a research request from Chat and task records will appear here.");
    return;
  }
  list.innerHTML = `<div class="list">${tasks
    .slice(0, 30)
    .map((task) =>
      itemCard({
        title: task.title || task.user_query || task.task_type || task.id,
        subtitle: task.summary || task.current_stage || task.task_id || "Task metadata only",
        status: task.status || "recorded",
        clickable: true,
        data: task.id || task.task_id,
      }),
    )
    .join("")}</div>`;
  root.querySelectorAll("[data-item-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      const detail = await getTask(button.dataset.itemId);
      const task = detail.data?.task || detail.data || {};
      root.querySelector("#taskDetail").innerHTML = detail.ok ? renderLastRun(task) : apiErrorCard(detail, "Task detail unavailable");
    });
  });
}
