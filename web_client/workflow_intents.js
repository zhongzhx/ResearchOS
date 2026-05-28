import {
  WORKFLOW_DEFINITIONS,
  createWorkflowDraft,
  isWorkflowCancellation,
  isWorkflowConfirmation,
  updateWorkflowDraft,
  validateWorkflowParams,
} from "./user_workflows.js";

export const INTENT_TRIGGERS = {
  literature_search: ["帮我找文献", "查一下这个方向的论文", "检索神经炎症相关论文", "找近五年的研究", "给我一个文献清单", "帮我找近五年", "搜索相关论文"],
  literature_harvest_and_kb: ["帮我下载文献构建知识库", "下载文献并入库", "围绕这个主题建立知识库", "帮我找20篇文献并加入项目", "把开放获取文献下载下来", "下载文献并构建知识库", "查一些"],
  ingest_uploaded_papers: ["学习我上传的论文", "把这些PDF加入知识库", "解析上传的文献", "把论文导入项目", "读取这些论文文件", "把上传论文入库"],
  paper_reader: ["精读这篇论文", "帮我读这篇文章", "翻译成中文精读版", "生成论文阅读笔记", "解释这篇论文的图", "帮我拆解这篇论文"],
  citation_finder: ["帮我找引用", "给这个论点找文献支撑", "找支持这句话的参考文献", "补充参考文献", "找可以引用的论文", "为这个观点找出处"],
  paper_to_ppt: ["把这篇论文做成组会PPT", "生成汇报PPT", "做一个journal club", "帮我做论文汇报", "生成15页PPT", "论文转PPT"],
  experiment_design: ["帮我设计实验方案", "设计RAW264.7实验", "给我一个实验设计", "怎么设计验证实验", "设计小鼠实验", "帮我设计BV2实验方案"],
  protocol_to_sop: ["把protocol整理成SOP", "生成实验SOP", "把论文方法写成SOP", "整理实验步骤", "生成标准操作流程", "转成可执行SOP"],
  failure_recovery: ["实验失败帮我排查", "数据不对帮我分析原因", "为什么没有结果", "帮我复盘失败实验", "排查实验问题", "结果异常怎么恢复"],
  experiment_log: ["记录今天实验", "整理实验记录", "帮我写实验日志", "把今天操作记下来", "生成实验记录", "归纳今天观察"],
  next_step_plan: ["帮我规划下一步", "生成下一步计划", "接下来怎么做", "帮我安排后续实验", "给我下周计划", "整理下一轮工作"],
  table_analysis: ["分析这个表格", "帮我做表格统计", "分析CSV数据", "看一下这份Excel", "做数据表分析", "比较这些组的数据"],
  qpcr_elisa_cck8_analysis: ["帮我做qPCR数据分析", "分析ELISA数据", "处理CCK-8结果", "qPCR统计和作图", "帮我分析实验读数", "分析qPCR ELISA CCK8"],
  metabolomics_interpretation: ["解释代谢组结果", "分析差异代谢物", "帮我解读代谢通路", "代谢组富集结果怎么看", "整理代谢组机制解释", "解释KEGG通路变化"],
  figure_generation: ["帮我画论文图", "生成发表级图表", "把这个数据画成图", "做一张机制图", "生成SVG图", "做论文插图"],
  ml_modeling_assistant: ["帮我做机器学习建模", "设计预测模型", "规划特征工程", "做分类模型方案", "帮我建模分析", "生成模型验证计划"],
  manuscript_section_writing: ["帮我写论文段落", "写结果部分", "写讨论部分", "整理引言段落", "根据结果写方法", "生成论文初稿"],
  english_polishing: ["润色这段英文", "改成学术英语", "检查过度声称", "帮我润色论文", "改成更像高水平期刊表达", "润色英文摘要"],
  peer_review_simulation: ["模拟审稿人", "帮我审稿", "找论文逻辑漏洞", "模拟同行评审", "给我审稿意见", "严格审一下这篇稿"],
  reviewer_response: ["帮我写审稿回复", "逐条回复审稿人", "整理reviewer comments", "生成response letter", "把审稿意见拆成回复", "写返修回复"],
  submission_checklist: ["生成投稿清单", "检查投稿材料", "投稿前检查", "按期刊要求核对材料", "submission checklist", "检查cover letter和补充材料"],
  weekly_report: ["生成周报", "总结本周进展", "写项目周报", "整理本周实验", "生成下周计划", "汇总最近工作"],
};

const ORDINARY_QUESTION_PATTERNS = [
  /^什么是/,
  /^.*是什么[？?]?$/,
  /你可以为我做什么/,
  /怎么理解/,
  /规划学习/,
  /训练免疫是什么/,
  /nf-?κ?b\s*是什么/i,
  /阿尔兹海默症|阿尔茨海默症/,
];

const INTENT_PRIORITY = [
  "literature_harvest_and_kb",
  "paper_to_ppt",
  "qpcr_elisa_cck8_analysis",
  "literature_search",
  "paper_reader",
  "english_polishing",
  "experiment_design",
  "figure_generation",
  "citation_finder",
  "ingest_uploaded_papers",
  "protocol_to_sop",
  "failure_recovery",
  "experiment_log",
  "next_step_plan",
  "table_analysis",
  "metabolomics_interpretation",
  "ml_modeling_assistant",
  "manuscript_section_writing",
  "peer_review_simulation",
  "reviewer_response",
  "submission_checklist",
  "weekly_report",
];

const YEAR_WORDS = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 };

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function chineseNumber(value) {
  if (!value) return null;
  if (/^\d+$/.test(value)) return Number(value);
  return YEAR_WORDS[value] || null;
}

function extractRecentYears(text) {
  const match = text.match(/近\s*([一二两三四五六七八九十\d]+)\s*年/);
  return match ? chineseNumber(match[1]) : null;
}

function extractPaperCount(text) {
  const match = text.match(/(?:找|下载|整理|生成|改成|调整为|设置为|最多|前)?\s*(\d+)\s*篇/);
  return match ? Number(match[1]) : null;
}

function extractSlideCount(text) {
  const match = text.match(/(\d+)\s*页/);
  return match ? Number(match[1]) : null;
}

function extractModel(text) {
  const match = text.match(/\b(RAW264\.7|BV2|小鼠|斑马鱼|大鼠|巨噬细胞|细胞模型)\b/i);
  return match ? match[1].replace(/^raw/i, "RAW").replace(/^bv/i, "BV") : "";
}

function extractAssayType(text) {
  const match = text.match(/\b(qPCR|ELISA|CCK-?8)\b/i);
  if (!match) return "";
  const value = match[1].toLowerCase().replace("-", "");
  if (value === "qpcr") return "qPCR";
  if (value === "elisa") return "ELISA";
  return "CCK-8";
}

function stripCommonTaskWords(text) {
  return cleanText(text)
    .replace(/^(请|麻烦|帮我|给我|可以)?/g, "")
    .replace(/近\s*[一二两三四五六七八九十\d]+\s*年/g, "")
    .replace(/\d+\s*(篇|页|条)/g, "")
    .replace(/(相关|这个方向的|方向的)/g, "")
    .replace(/(下载文献并构建知识库|下载文献构建知识库|下载文献并入库|下载文献|构建知识库|建立知识库|加入项目|检索|搜索|查一下|找|给我一个|文献清单|论文清单|文献|论文|研究)/g, "")
    .replace(/[，。；、,]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractTopic(text) {
  const direction = text.match(/(?:查一些|查一下|找|检索|搜索)?\s*([^，。；,.]+?)方向的(?:论文|文献|研究)/);
  if (direction?.[1]) return cleanText(direction[1]).replace(/^(请|麻烦|帮我|给我|可以)?/, "");
  const explicit = text.match(/(?:主题|方向|关键词|围绕|关于)\s*(?:是|为|：|:)?\s*([^，。；,.]+)/);
  if (explicit?.[1]) return cleanText(explicit[1]);
  return stripCommonTaskWords(text);
}

function extractFocus(text) {
  const match = text.match(/重点(?:讲|关注|解释|突出)\s*([^，。；,.]+)/);
  return match ? cleanText(match[1]) : "";
}

function scoreIntent(text, intent) {
  const normalized = text.toLowerCase();
  const triggerHit = (INTENT_TRIGGERS[intent] || []).some((trigger) => normalized.includes(trigger.toLowerCase()));
  if (triggerHit) return 3;

  if (intent === "literature_harvest_and_kb" && /文献/.test(text) && /(下载|入库|知识库|开放获取|加入项目)/.test(text)) return 2;
  if (intent === "literature_search" && /(找|查|检索|搜索).*(文献|论文|研究)/.test(text) && !/(下载|入库|知识库)/.test(text)) return 2;
  if (intent === "paper_to_ppt" && /(论文|文章|paper).*(PPT|ppt|汇报|journal club|组会)/i.test(text)) return 2;
  if (intent === "english_polishing" && /(润色|学术英语|过度声称|overclaim)/i.test(text) && /(英文|英语|论文)/.test(text)) return 2;
  if (intent === "qpcr_elisa_cck8_analysis" && /(qPCR|ELISA|CCK-?8)/i.test(text) && /(分析|统计|作图|数据)/.test(text)) return 2;
  if (intent === "experiment_design" && /(设计|方案|验证).*(实验|RAW264\.7|BV2|小鼠|斑马鱼)/i.test(text)) return 2;
  if (intent === "figure_generation" && /(画|生成|做).*(图|图表|机制图|SVG|svg)/.test(text)) return 2;
  return 0;
}

function extractParams(intent, message) {
  const text = cleanText(message);
  const params = {};
  const count = extractPaperCount(text);
  const recentYears = extractRecentYears(text);
  const slideCount = extractSlideCount(text);
  const model = extractModel(text);
  const assayType = extractAssayType(text);

  if (["literature_harvest_and_kb", "literature_search"].includes(intent)) {
    params.query = extractTopic(text);
    if (count) params[intent === "literature_harvest_and_kb" ? "max_papers" : "max_results"] = count;
    if (recentYears) params.recent_years = recentYears;
  }
  if (intent === "literature_harvest_and_kb") {
    params.oa_only = /开放获取|OA|open access|只要/.test(text) ? true : true;
    params.build_kb = /知识库|入库|加入项目/.test(text) ? true : true;
  }
  if (["paper_reader", "paper_to_ppt", "ingest_uploaded_papers", "protocol_to_sop"].includes(intent)) {
    params.source = /这篇|这份|上传|PDF|pdf|论文|文章|protocol/i.test(text) ? text.match(/这篇论文|这篇文章|上传的论文|这些PDF|protocol/i)?.[0] || text : "";
  }
  if (intent === "paper_to_ppt") {
    if (slideCount) params.slide_count = slideCount;
    params.language = /英文|英语/.test(text) ? "en" : "zh";
    const focus = extractFocus(text);
    if (focus) params.focus = focus;
  }
  if (intent === "experiment_design") {
    params.research_goal = text;
    if (model) params.model = model;
    const intervention = text.match(/(?:用|处理|干预|药物|样品)([^，。；,.]+)/)?.[1];
    if (intervention) params.intervention = cleanText(intervention);
  }
  if (intent === "qpcr_elisa_cck8_analysis") {
    if (assayType) params.assay_type = assayType;
    params.analysis_goal = text;
    const control = text.match(/(?:对照组|control group|control)\s*(?:是|为|:|：)?\s*([^，。；,.]+)/i)?.[1];
    if (control) params.control_group = cleanText(control);
  }
  if (intent === "table_analysis") params.analysis_goal = text;
  if (intent === "citation_finder") params.claim = text;
  if (intent === "failure_recovery") params.failure_description = text;
  if (intent === "experiment_log") params.experiment_notes = text;
  if (intent === "next_step_plan") params.current_progress = text;
  if (intent === "metabolomics_interpretation") params.result_summary = text;
  if (intent === "figure_generation") params.figure_goal = text;
  if (intent === "ml_modeling_assistant") params.modeling_goal = text;
  if (["manuscript_section_writing", "writing_review"].includes(intent)) params.writing_goal = text;
  if (intent === "english_polishing") {
    params.text = text;
    params.check_overclaim = /过度声称|overclaim/i.test(text) ? true : true;
  }
  if (intent === "peer_review_simulation") params.manuscript_or_summary = text;
  if (intent === "reviewer_response") params.review_comments = text;
  if (intent === "submission_checklist") params.journal = text;
  if (intent === "weekly_report") params.focus = text;
  return params;
}

function isOrdinaryQuestion(message) {
  const text = cleanText(message);
  return ORDINARY_QUESTION_PATTERNS.some((pattern) => pattern.test(text));
}

export const USER_WORKFLOW_INTENTS = Object.entries(WORKFLOW_DEFINITIONS).map(([intent, definition]) => ({
  intent,
  title: definition.user_title,
  triggers: INTENT_TRIGGERS[intent] || [],
  defaults: definition.default_params,
  required: definition.required_params,
  missingQuestion: validateWorkflowParams(intent, {}).questions[0],
}));

export function detectWorkflowIntent(message) {
  const text = cleanText(message);
  if (!text || isOrdinaryQuestion(text)) return null;

  const scored = INTENT_PRIORITY.map((intent) => [intent, scoreIntent(text, intent)])
    .filter(([, score]) => score > 0)
    .sort((a, b) => b[1] - a[1] || INTENT_PRIORITY.indexOf(a[0]) - INTENT_PRIORITY.indexOf(b[0]));
  if (!scored.length) return null;
  if (scored.length > 1 && scored[0][1] === scored[1][1]) return null;

  const intent = scored[0][0];
  const params = extractParams(intent, text);
  return { intent, title: WORKFLOW_DEFINITIONS[intent].user_title, params, confidence: scored[0][1] >= 3 ? "high" : "medium" };
}

export function workflowConfig(intent) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  return definition ? { intent, title: definition.user_title, defaults: definition.default_params, required: definition.required_params } : null;
}

export function getMissingWorkflowParams(intent, params = {}) {
  return validateWorkflowParams(intent, params).missing;
}

export function missingWorkflowQuestion(intent, missing = []) {
  const validation = validateWorkflowParams(intent, {});
  if (["table_analysis", "qpcr_elisa_cck8_analysis"].includes(intent) && missing.includes("file_id")) {
    return "请先上传或选择数据文件。";
  }
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

export { createWorkflowDraft, isWorkflowCancellation, isWorkflowConfirmation };
