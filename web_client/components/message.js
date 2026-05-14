import { badge, escapeHtml, text } from "./cards.js";
import { detailsBlock } from "./details.js";
import { jsonDetails } from "./json_viewer.js";

function pipelineName(data) {
  return (
    data?.selected_pipeline ||
    data?.task_spec?.input_data?.pipeline_name ||
    data?.task_spec?.pipeline_name ||
    data?.pipeline?.pipeline_name ||
    data?.raw_details?.TaskSpec?.pipeline ||
    data?.details?.task_spec?.input_data?.pipeline_name ||
    "Not selected"
  );
}

function unresolvedCount(data) {
  const errors = data?.execution_result?.errors || [];
  const issues = data?.validation_report?.issues || [];
  const rejected = data?.promotion_decision?.rejected_items || data?.rejected_items || [];
  return errors.length + issues.length + rejected.length;
}

export function plainMessage(role, body) {
  return `<article class="message ${escapeHtml(role)}"><div class="message-bubble">${escapeHtml(body)}</div></article>`;
}

export function dualAgentMessage(data) {
  const execution = data?.execution_result || data?.raw_details?.ExecutionResult || {};
  const pending = data?.pending_skill || {};
  const resolver = data?.resolver_health || {};
  const memoryPages = Array.isArray(data?.memory_pages) ? data.memory_pages.length : Array.isArray(data?.memory_updates) ? data.memory_updates.length : 0;
  const artifactCount = Array.isArray(data?.artifacts) ? data.artifacts.length : 0;
  const summary = data?.summary || data?.handoff || execution.summary || "AURA finished a dual-agent pass.";
  const skillrunId = data?.skillrun_id || execution.skillrun_id || "none";
  const executionStatus = data?.execution_status || execution.status || "unknown";
  const badges = [
    badge(`Pipeline: ${pipelineName(data)}`, "success"),
    badge(`SkillRun: ${text(skillrunId, "none")}`),
    badge(`Artifacts: ${artifactCount}`),
    badge(`Memory: ${memoryPages}`),
    badge(`Pending Skill: ${text(pending.name || pending.status, "none")}`, pending.name ? "warning" : "muted"),
    badge(`Resolver: ${resolver.ok === false ? "needs review" : "checked"}`, resolver.ok === false ? "warning" : "success"),
  ].join("");

  const top = `<div class="assistant-summary">
    <p>${escapeHtml(text(summary, "No summary returned."))}</p>
    <p class="muted">Execution status: ${escapeHtml(text(executionStatus, "unknown"))}. Unresolved items: ${unresolvedCount(data)}.</p>
    <div class="badge-row">${badges}</div>
  </div>`;
  const details = [
    jsonDetails("Task Plan / TaskSpec", data?.task_spec || data?.raw_details?.TaskSpec),
    jsonDetails("Execution Result", data?.execution_result || data?.raw_details?.ExecutionResult),
    jsonDetails("Validation Report", data?.validation_report),
    jsonDetails("Promotion Decision", data?.promotion_decision),
    jsonDetails("Brain Memory Update", data?.memory_update || data?.brain_memory_write || data?.memory_commit),
    jsonDetails("Artifacts", data?.artifacts),
    jsonDetails("Pending Skill", data?.pending_skill),
    jsonDetails("Resolver Health", data?.resolver_health),
    jsonDetails("Raw JSON", data),
  ].join("");

  return `<article class="message assistant"><div class="message-bubble">${top}${details}</div></article>`;
}
