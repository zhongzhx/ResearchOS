import {
  WORKFLOW_DEFINITIONS,
  createWorkflowDraft,
  detectWorkflowIntent,
  isWorkflowCancellation,
  isWorkflowConfirmation,
  updateWorkflowDraft,
  validateWorkflowParams,
} from "./user_workflows.js";

export const USER_WORKFLOW_INTENTS = Object.entries(WORKFLOW_DEFINITIONS).map(([intent, definition]) => ({
  intent,
  title: definition.user_title,
  triggers:
    intent === "literature_harvest_and_kb"
      ? ["帮我下载文献", "帮我检索文献", "构建知识库", "下载文献并入库", "查一下"]
      : [],
  defaults: definition.default_params,
  required: definition.required_params,
  missingQuestion:
    intent === "literature_harvest_and_kb"
      ? "你想围绕哪个主题检索文献？"
      : validateWorkflowParams(intent, {}).questions[0],
}));

export function workflowConfig(intent) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  return definition ? { intent, title: definition.user_title, defaults: definition.default_params, required: definition.required_params } : null;
}

export function getMissingWorkflowParams(intent, params = {}) {
  return validateWorkflowParams(intent, params).missing;
}

export function missingWorkflowQuestion(intent, missing = []) {
  const validation = validateWorkflowParams(intent, {});
  if (intent === "data_analysis" && missing.length) return "请告诉我数据文件和分析目标，例如要比较哪些组、输出什么图。";
  return validation.questions[0] || "请补充执行这个任务需要的关键信息。";
}

export function applyWorkflowParameterUpdate(workflow, message) {
  const updated = updateWorkflowDraft(workflow, message);
  return { changed: JSON.stringify(updated.params || {}) !== JSON.stringify(workflow?.params || {}), workflow: updated };
}

export function supplementMissingWorkflowParams(workflow, message) {
  return updateWorkflowDraft(workflow, message);
}

export function buildWorkflowPrompt(intent, params = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  const lines = [`请为当前项目执行“${definition?.user_title || "科研任务"}”。`];
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") lines.push(`${key}: ${value}`);
  });
  lines.push("请用中文说明计划、进度、结果和下一步建议，不要向普通用户展示内部技术对象。");
  return lines.join("\n");
}

export { createWorkflowDraft, detectWorkflowIntent, isWorkflowCancellation, isWorkflowConfirmation };
