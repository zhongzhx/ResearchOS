import { badge, escapeHtml, text } from "./cards.js";
import { detailsBlock, fieldList } from "./details.js";
import { jsonDetails } from "./json_viewer.js";
import { appState } from "../state.js";

function pipelineName(data) {
  return (
    data?.selected_pipeline ||
    data?.task_spec?.input_data?.pipeline_name ||
    data?.task_spec?.pipeline_name ||
    data?.pipeline?.pipeline_name ||
    data?.raw_details?.TaskSpec?.pipeline ||
    data?.details?.task_spec?.input_data?.pipeline_name ||
    "未选择"
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

function boolText(value) {
  return value ? "是" : "否";
}

function confirmationRows(workflow) {
  const params = workflow?.params || {};
  if (workflow?.intent === "literature_harvest_and_kb") {
    return [
      ["主题", params.query || params.topic || "待补充"],
      ["下载数量", `${params.max_papers || 20} 篇`],
      ["仅开放获取文献", boolText(params.oa_only !== false)],
      ["构建知识库", boolText(params.build_kb !== false)],
      ["非开放获取文献", "加入手动下载队列"],
    ];
  }
  if (workflow?.intent === "experiment_design") {
    return [
      ["研究目标", params.research_goal || "待补充"],
      ["模型", params.model || "可稍后补充"],
      ["样品 / 干预物", params.sample || params.intervention || "可稍后补充"],
    ];
  }
  if (workflow?.intent === "data_analysis") {
    return [
      ["数据文件", params.file_id || params.uploaded_file || "待补充"],
      ["分析目标", params.analysis_goal || "待补充"],
    ];
  }
  return Object.entries(params).map(([key, value]) => [key, value]);
}

function technicalDetails(data) {
  if (!appState.developerMode || !data) return "";
  return `<details class="details"><summary>技术详情</summary><pre class="json-view">${escapeHtml(JSON.stringify(data, null, 2))}</pre></details>`;
}

export function workflowConfirmationMessage(workflow) {
  const rows = confirmationRows(workflow)
    .map(([label, value]) => `<li><strong>${escapeHtml(label)}：</strong>${escapeHtml(value)}</li>`)
    .join("");
  const title = workflow?.title || "科研任务";
  const intro =
    workflow?.intent === "literature_harvest_and_kb"
      ? "我可以帮你围绕当前对话主题检索文献，并构建当前项目知识库。请确认以下设置："
      : `我可以开始“${title}”。请确认以下设置：`;
  return `<article class="message assistant"><div class="message-bubble">
    <div class="assistant-summary workflow-confirmation-card">
      <p>${escapeHtml(intro)}</p>
      <ul>${rows}</ul>
      <div class="inline-actions">
        <button class="button primary small" type="button" data-workflow-reply="开始">开始</button>
        <button class="button secondary small" type="button" data-workflow-edit>修改设置</button>
        <button class="button ghost small" type="button" data-workflow-reply="取消">取消</button>
      </div>
    </div>
    ${technicalDetails(workflow?.technical)}
  </div></article>`;
}

export function workflowResultMessage(result) {
  const steps = Array.isArray(result?.steps) ? result.steps : [];
  const links = Array.isArray(result?.links) ? result.links : [];
  const stepItems = steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
  const linkItems = links.map((link) => `<li>${escapeHtml(link.label || link.title || link.href || link)}</li>`).join("");
  const manual = Number(result?.manual_queue_count || 0);
  const manualText = manual > 0 ? `<p>有 ${manual} 篇需要手动下载。</p>` : "";
  return `<article class="message assistant"><div class="message-bubble">
    <div class="assistant-summary workflow-result-card">
      <p><strong>${escapeHtml(result?.title || "任务状态")}</strong></p>
      <p>${escapeHtml(result?.message || "当前只能生成执行计划，真实执行入口尚未接入。")}</p>
      ${steps.length ? `<p>当前步骤：</p><ul>${stepItems}</ul>` : ""}
      ${manualText}
      ${result?.next_step ? `<p>下一步建议：${escapeHtml(result.next_step)}</p>` : ""}
      ${links.length ? `<p>相关资料或任务：</p><ul>${linkItems}</ul>` : ""}
    </div>
    ${technicalDetails(result?.technical)}
  </div></article>`;
}

function renderInlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function renderMarkdown(value) {
  const lines = String(value || "").split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let listType = "";

  const closeParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(`<p>${paragraph.join("<br>")}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (!listType) return;
    blocks.push(`</${listType}>`);
    listType = "";
  };
  const openList = (type) => {
    closeParagraph();
    if (listType === type) return;
    closeList();
    listType = type;
    blocks.push(`<${type}>`);
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      closeParagraph();
      closeList();
      return;
    }
    const heading = trimmed.match(/^#{2,3}\s+(.+)$/);
    if (heading) {
      closeParagraph();
      closeList();
      blocks.push(`<h3>${renderInlineMarkdown(heading[1])}</h3>`);
      return;
    }
    const unordered = trimmed.match(/^[-*]\s+(.+)$/);
    if (unordered) {
      openList("ul");
      blocks.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
      return;
    }
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (ordered) {
      openList("ol");
      blocks.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
      return;
    }
    closeList();
    paragraph.push(renderInlineMarkdown(trimmed));
  });
  closeParagraph();
  closeList();
  return blocks.join("");
}

const INTERNAL_TASK_NOTICE = "该内容来自内部任务执行链路，已隐藏技术细节。可在功能导航中查看任务详情。";

function firstTextValue(values) {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const normalized = String(value).trim();
    if (normalized) return normalized;
  }
  return "";
}

function internalHandoffSignals(value) {
  const body = String(value || "");
  return [
    /Research Task Handoff/i.test(body) ? "Research Task Handoff" : "",
    /\bTaskSpec\b/.test(body) ? "TaskSpec" : "",
    /\bExecutionResult\b/.test(body) ? "ExecutionResult" : "",
    /\bSkillRun\b/.test(body) ? "SkillRun" : "",
    /\bPipeline\b/.test(body) ? "Pipeline" : "",
    /\btask_[a-z0-9_-]+\b/i.test(body) ? "task_" : "",
    /Final task status/i.test(body) ? "Final task status" : "",
    /\bMemory\s*:/i.test(body) ? "Memory:" : "",
    /Pending Skill/i.test(body) ? "Pending Skill" : "",
  ].filter(Boolean);
}

function containsInternalHandoff(value) {
  return internalHandoffSignals(value).length >= 2;
}

function hasStructuredTaskPayload(data) {
  return Boolean(data?.task_spec || data?.execution_result || data?.research_task || data?.handoff || data?.handoff_summary || data?.raw_details?.TaskSpec);
}

function mainAnswer(data, fallback) {
  const body = firstTextValue([
    data?.answer,
    data?.content,
    data?.message,
    data?.response,
    data?.text,
    data?.result?.answer,
    data?.data?.answer,
    data?.summary,
  ]);
  if (containsInternalHandoff(body)) {
    return INTERNAL_TASK_NOTICE;
  }
  if (body) {
    if (/traceback|stack trace|undefined|null/i.test(body) && body.length > 240) {
      return "AURA 返回了内部错误。请在调试详情中查看后端响应。";
    }
    return body;
  }
  if (hasStructuredTaskPayload(data)) {
    return INTERNAL_TASK_NOTICE;
  }
  return text(fallback, "AURA 暂时没有返回回答。");
}

function answerSourceLabel(source) {
  return {
    llm: "模型回答",
    template: "模板",
    fallback: "降级",
    validator_rewrite: "校验改写",
    sanitizer_rewrite: "清理改写",
    coordinator_handoff: "协调器",
    product_demo: "演示预览",
    cache: "缓存",
    error_recovery: "错误恢复",
  }[source] || text(source, "未知");
}

export function answerSourceBadge(data) {
  const source = data?.answer_source;
  if (!source || (source === "llm" && data?.llm_output_used !== false)) return "";
  const tone = source === "template" || source === "fallback" ? "warning" : "muted";
  return badge(answerSourceLabel(source), tone);
}

function shouldShowChatDiagnostics(data) {
  return false;
}

function answerSourceDetails(data) {
  const rows = [
    ["answer_source", answerSourceLabel(data?.answer_source)],
    ["llm_called", String(Boolean(data?.llm_called))],
    ["llm_output_used", String(Boolean(data?.llm_output_used))],
    ["answer_overwritten_after_llm", String(Boolean(data?.answer_overwritten_after_llm))],
    ["llm_provider", data?.llm_provider || data?.llm?.provider || ""],
    ["llm_model", data?.llm_model || data?.llm?.model || ""],
    ["prompt_router_used", String(Boolean(data?.prompt_router_used))],
    ["context_compiler_used", String(Boolean(data?.context_compiler_used))],
    ["template_id", data?.template_id || ""],
    ["fallback_reason", data?.fallback_reason || ""],
  ];
  return detailsBlock("回答来源", fieldList(rows));
}

function taskStatusDetails(data) {
  if (data?.task_status) return jsonDetails("任务状态", data.task_status);
  if (data?.task_status_summary) return jsonDetails("任务状态", data.task_status_summary);
  return "";
}

export function chatAnswerMessage(data, fallback = "AURA 暂时没有返回回答。") {
  const answer = mainAnswer(data, fallback);
  const showDiagnostics = shouldShowChatDiagnostics(data);
  const sourceBadge = showDiagnostics ? answerSourceBadge(data) : "";
  const badges = sourceBadge ? `<div class="badge-row">${sourceBadge}</div>` : "";
  const details = showDiagnostics ? [answerSourceDetails(data), taskStatusDetails(data)].join("") : "";
  return `<article class="message assistant"><div class="message-bubble">
    <div class="assistant-summary">${renderMarkdown(answer)}${badges}</div>
    ${details}
  </div></article>`;
}

export function dualAgentMessage(data) {
  return plainMessage("assistant", INTERNAL_TASK_NOTICE);
  const execution = data?.execution_result || data?.raw_details?.ExecutionResult || {};
  const pending = data?.pending_skill || {};
  const resolver = data?.resolver_health || {};
  const memoryPages = Array.isArray(data?.memory_pages) ? data.memory_pages.length : Array.isArray(data?.memory_updates) ? data.memory_updates.length : 0;
  const artifactCount = Array.isArray(data?.artifacts) ? data.artifacts.length : 0;
  const summary = data?.summary || data?.handoff || execution.summary || "AURA 已完成一次内部任务执行。";
  const skillrunId = data?.skillrun_id || execution.skillrun_id || "无";
  const executionStatus = data?.execution_status || execution.status || "未知";
  const badges = [
    badge(`流程：${pipelineName(data)}`, "success"),
    badge(`技能运行：${text(skillrunId, "无")}`),
    badge(`产物：${artifactCount}`),
    badge(`记忆：${memoryPages}`),
    badge(`待处理技能：${text(pending.name || pending.status, "无")}`, pending.name ? "warning" : "muted"),
    badge(`解析器：${resolver.ok === false ? "需要检查" : "已检查"}`, resolver.ok === false ? "warning" : "success"),
  ].join("");

  const top = `<div class="assistant-summary">
    <p>${escapeHtml(text(summary, "没有返回摘要。"))}</p>
    <p class="muted">执行状态：${escapeHtml(text(executionStatus, "未知"))}。未解决项：${unresolvedCount(data)}。</p>
    <div class="badge-row">${badges}</div>
  </div>`;
  const details = [
    jsonDetails("任务计划", data?.task_spec || data?.raw_details?.TaskSpec),
    jsonDetails("执行结果", data?.execution_result || data?.raw_details?.ExecutionResult),
    jsonDetails("校验报告", data?.validation_report),
    jsonDetails("入库决策", data?.promotion_decision),
    jsonDetails("研究大脑记忆更新", data?.memory_update || data?.brain_memory_write || data?.memory_commit),
    jsonDetails("产物", data?.artifacts),
    jsonDetails("待处理技能", data?.pending_skill),
    jsonDetails("解析器状态", data?.resolver_health),
    jsonDetails("原始数据", data),
  ].join("");

  return `<article class="message assistant"><div class="message-bubble">${top}${details}</div></article>`;
}
