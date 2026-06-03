import { WORKFLOW_OUTPUT_ARTIFACTS, saveWorkflowArtifacts as saveArtifactsToProject } from "./artifact_types.js";

const WORKFLOW_HISTORY_PREFIX = "researchos.workflowHistory.v1.";
const CONFIRM_WORDS = ["好", "可以", "开始", "确认", "执行", "就按这个", "没问题"];
const CANCEL_WORDS = ["取消", "不要", "不用了", "先不做", "停止"];

export const WORKFLOW_GROUPS = ["找资料", "做实验", "分析数据", "写论文"];

export const WORKFLOW_DEFINITIONS = {
  literature_search: {
    intent: "literature_search",
    user_title: "找文献",
    user_description: "围绕主题检索近年论文，整理可阅读的文献清单。",
    group: "找资料",
    required_params: ["query"],
    optional_params: ["max_results", "recent_years", "include_review"],
    default_params: { max_results: 50, recent_years: 5, include_review: true },
    confirmation_template: "我将围绕“{query}”检索近 {recent_years} 年文献，最多整理 {max_results} 条结果。",
    user_visible_steps: ["确认检索主题", "检索相关文献", "筛选高相关结果", "整理文献清单"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["文献清单", "检索策略"],
    save_to_project: true,
    developer_notes: "User-facing literature discovery. Full execution should route to a stable literature search service when connected.",
  },
  literature_harvest_and_kb: {
    intent: "literature_harvest_and_kb",
    user_title: "下载文献并构建知识库",
    user_description: "检索并处理可合法获取的全文，把资料整理进项目知识库。",
    group: "找资料",
    required_params: ["query"],
    optional_params: ["max_papers", "recent_years", "oa_only", "build_kb", "non_oa_policy"],
    default_params: { max_papers: 20, oa_only: true, build_kb: true, non_oa_policy: "manual_queue" },
    confirmation_template: "我将检索“{query}”相关文献，最多 {max_papers} 篇，范围为近 {recent_years} 年，优先处理开放获取全文，并构建知识库。",
    user_visible_steps: ["确认检索主题", "创建文献采集任务", "检索开放获取文献", "整理手动下载队列", "构建项目知识库"],
    execution_strategy: "legacy_literature_api",
    current_status: "executable",
    output_types: ["文献清单", "手动下载队列", "知识库"],
    save_to_project: true,
    developer_notes: "Uses createLiteratureSearchTask -> runLiteratureSearch -> generatePaperRequests -> buildKnowledgeBase. Non-OA material stays in manual queue.",
  },
  ingest_uploaded_papers: {
    intent: "ingest_uploaded_papers",
    user_title: "上传 PDF 并学习",
    user_description: "把上传的论文加入资料库，提取摘要、结论和可追问内容。",
    group: "找资料",
    required_params: ["source"],
    optional_params: ["goal"],
    default_params: {},
    confirmation_template: "我将学习你提供的 PDF“{source}”，并按“{goal}”整理重点。",
    user_visible_steps: ["选择 PDF", "读取论文信息", "提取重点内容", "写入项目资料库"],
    execution_strategy: "needs_file",
    current_status: "needs_file",
    output_types: ["中文摘要", "重点结论", "资料库条目"],
    save_to_project: true,
    developer_notes: "Requires uploaded file selection before a real ingestion call can run.",
  },
  paper_reader: {
    intent: "paper_reader",
    user_title: "论文精读",
    user_description: "按研究问题拆解论文贡献、方法、结果、局限和图表。",
    group: "找资料",
    required_params: ["source"],
    optional_params: ["language", "output_format", "include_figure_explanation", "focus"],
    default_params: { language: "zh", output_format: "markdown", include_figure_explanation: true },
    confirmation_template: "我将精读“{source}”，输出中文结构化解读，并解释关键图表。",
    user_visible_steps: ["确认论文", "提取研究问题", "拆解方法与结果", "解释图表", "整理局限与可复用点"],
    execution_strategy: "needs_file",
    current_status: "executable",
    output_types: ["中文精读", "图表解释", "方法要点"],
    save_to_project: true,
    developer_notes: "Needs a selected paper or uploaded PDF. Keep output at product artifact level.",
  },
  citation_finder: {
    intent: "citation_finder",
    user_title: "找支撑引用",
    user_description: "为论文论点寻找可支撑的参考文献和引用位置。",
    group: "找资料",
    required_params: ["claim"],
    optional_params: ["field", "recent_years"],
    default_params: { recent_years: 5 },
    confirmation_template: "我将为“{claim}”寻找可支撑引用，并说明每条引用适合支撑的位置。",
    user_visible_steps: ["确认论点", "检索候选文献", "匹配支撑关系", "整理引用建议"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["引用建议", "支撑理由", "候选文献"],
    save_to_project: true,
    developer_notes: "Plan-only until citation grounding service is connected.",
  },
  paper_to_ppt: {
    intent: "paper_to_ppt",
    user_title: "生成组会 PPT",
    user_description: "把论文或资料整理成组会汇报结构和讲稿备注。",
    group: "找资料",
    required_params: ["source"],
    optional_params: ["slide_count", "language", "include_speaker_notes"],
    default_params: { slide_count: 15, language: "zh", include_speaker_notes: true },
    confirmation_template: "我将把“{source}”整理成 {slide_count} 页中文组会 PPT，并附讲稿备注。",
    user_visible_steps: ["确认材料", "抽取汇报主线", "生成幻灯片大纲", "补充讲稿备注"],
    execution_strategy: "needs_file",
    current_status: "executable",
    output_types: ["PPT 大纲", "讲稿备注", "汇报重点"],
    save_to_project: true,
    developer_notes: "Needs PDF or library file selection before deck generation can run.",
  },
  experiment_design: {
    intent: "experiment_design",
    user_title: "设计实验方案",
    user_description: "根据研究目标生成分组、指标、流程、风险和质控点。",
    group: "做实验",
    required_params: ["research_goal"],
    optional_params: ["model", "sample", "intervention"],
    default_params: {},
    confirmation_template: "我将围绕“{research_goal}”生成实验设计方案。",
    user_visible_steps: ["确认研究目标", "梳理实验变量", "设计分组与指标", "列出风险和质控点"],
    execution_strategy: "coordinator_or_chat",
    current_status: "executable",
    output_types: ["实验方案", "分组设计", "质控清单"],
    save_to_project: true,
    developer_notes: "Use coordinator when available; otherwise return a plan without exposing backend routing.",
  },
  protocol_to_sop: {
    intent: "protocol_to_sop",
    user_title: "生成 SOP",
    user_description: "把 protocol、论文方法或实验描述整理成可执行 SOP。",
    group: "做实验",
    required_params: ["source"],
    optional_params: ["scenario", "target_format"],
    default_params: { target_format: "step_by_step_sop" },
    confirmation_template: "我将把“{source}”整理成可执行 SOP。",
    user_visible_steps: ["确认来源材料", "提取关键步骤", "整理 SOP", "列出质控点"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["SOP", "质控点", "材料清单"],
    save_to_project: true,
    developer_notes: "Plan-only until SOP extraction is connected to a stable user workflow endpoint.",
  },
  failure_recovery: {
    intent: "failure_recovery",
    user_title: "实验失败复盘",
    user_description: "根据异常现象推断可能原因，给出下一步排查路径。",
    group: "做实验",
    required_params: ["failure_description"],
    optional_params: ["protocol", "observed_data"],
    default_params: {},
    confirmation_template: "我将根据“{failure_description}”做失败复盘。",
    user_visible_steps: ["确认失败现象", "梳理已排查条件", "排列可能原因", "给出下一步排查方案"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["原因假设", "排查计划", "风险提示"],
    save_to_project: true,
    developer_notes: "Plan-only until a stable failure recovery route is available.",
  },
  experiment_log: {
    intent: "experiment_log",
    user_title: "记录今天实验",
    user_description: "把今天的操作、观察、问题和待办整理成实验记录。",
    group: "做实验",
    required_params: ["experiment_notes"],
    optional_params: ["date", "project_id"],
    default_params: { date: "today" },
    confirmation_template: "我将把今天的实验记录整理为可保存的项目日志。",
    user_visible_steps: ["整理原始记录", "提取关键观察", "归纳问题", "生成待办"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["实验记录", "问题清单", "待办事项"],
    save_to_project: true,
    developer_notes: "Project log persistence can be added later; current client returns a structured plan.",
  },
  next_step_plan: {
    intent: "next_step_plan",
    user_title: "生成下一步计划",
    user_description: "基于当前进展和阻塞，整理下一轮实验或写作计划。",
    group: "做实验",
    required_params: ["current_progress"],
    optional_params: ["constraints", "deadline"],
    default_params: {},
    confirmation_template: "我将根据“{current_progress}”生成下一步计划。",
    user_visible_steps: ["确认当前进展", "识别阻塞", "拆解下一步动作", "标出优先级"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["下一步计划", "优先级", "风险清单"],
    save_to_project: true,
    developer_notes: "Plan-only project planning workflow.",
  },
  table_analysis: {
    intent: "table_analysis",
    user_title: "上传表格分析",
    user_description: "根据表格和目标生成统计分析、可视化和解释计划。",
    group: "分析数据",
    required_params: ["file_id", "analysis_goal"],
    optional_params: ["group_column", "value_column"],
    default_params: {},
    confirmation_template: "我将根据“{analysis_goal}”分析表格“{file_id}”。",
    user_visible_steps: ["选择数据表", "确认分析目标", "检查变量", "生成分析计划"],
    execution_strategy: "needs_file",
    current_status: "executable",
    output_types: ["分析计划", "图表建议", "结果解释"],
    save_to_project: true,
    developer_notes: "Data execution is not fully connected; do not report fake statistical completion.",
  },
  qpcr_elisa_cck8_analysis: {
    intent: "qpcr_elisa_cck8_analysis",
    user_title: "qPCR / ELISA / CCK-8 数据分析",
    user_description: "整理常见实验数据的分组比较、统计方法和图表输出。",
    group: "分析数据",
    required_params: ["file_id", "assay_type"],
    optional_params: ["control_group", "analysis_goal"],
    default_params: {},
    confirmation_template: "我将按 {assay_type} 数据类型分析“{file_id}”。",
    user_visible_steps: ["选择数据文件", "确认实验类型", "规划统计比较", "生成图表方案"],
    execution_strategy: "coding_runtime",
    current_status: "executable",
    output_types: ["统计方案", "图表建议", "结果解释"],
    save_to_project: true,
    developer_notes: "qPCR uses CodingRuntimeService qpcr_template. ELISA and CCK-8 currently fall back to a generic project-scoped data profile until assay-specific normalization is connected.",
  },
  metabolomics_interpretation: {
    intent: "metabolomics_interpretation",
    user_title: "代谢组结果解释",
    user_description: "根据差异代谢物和通路结果生成生物学解释。",
    group: "分析数据",
    required_params: ["result_summary"],
    optional_params: ["species", "pathway_database"],
    default_params: {},
    confirmation_template: "我将根据“{result_summary}”解释代谢组结果。",
    user_visible_steps: ["确认结果摘要", "梳理差异代谢物", "归纳通路变化", "生成机制解释"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["结果解释", "机制假设", "后续验证建议"],
    save_to_project: true,
    developer_notes: "Plan-only interpretation until structured omics parsers are connected.",
  },
  figure_generation: {
    intent: "figure_generation",
    user_title: "生成论文图表",
    user_description: "把数据或结果描述整理成论文图表方案和绘图规格。",
    group: "分析数据",
    required_params: ["file_id", "group_column", "value_column", "figure_goal"],
    optional_params: ["output_format", "style"],
    default_params: { output_format: "svg", style: "publication" },
    confirmation_template: "我将按“{figure_goal}”生成论文图表方案，默认输出 {output_format}。",
    user_visible_steps: ["确认图表目标", "选择图表类型", "规划版式与标注", "生成绘图规格"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["图表方案", "绘图规格", "SVG"],
    save_to_project: true,
    developer_notes: "Plan-only until chart rendering is connected in this client.",
  },
  ml_modeling_assistant: {
    intent: "ml_modeling_assistant",
    user_title: "机器学习建模助手",
    user_description: "规划特征、建模目标、验证方式和结果解释。",
    group: "分析数据",
    required_params: ["modeling_goal"],
    optional_params: ["file_id", "target_column"],
    default_params: {},
    confirmation_template: "我将根据“{modeling_goal}”规划机器学习建模方案。",
    user_visible_steps: ["确认建模目标", "梳理特征和标签", "设计验证方案", "规划解释输出"],
    execution_strategy: "not_ready",
    current_status: "not_ready",
    output_types: ["建模计划", "特征建议", "验证方案"],
    save_to_project: true,
    developer_notes: "Not ready for normal users; keep disabled until modeling backend and safety checks exist.",
  },
  manuscript_section_writing: {
    intent: "manuscript_section_writing",
    user_title: "写论文段落",
    user_description: "根据材料写结果、讨论、引言或方法段落初稿。",
    group: "写论文",
    required_params: ["writing_goal"],
    optional_params: ["materials", "section_type"],
    default_params: {},
    confirmation_template: "我将按“{writing_goal}”生成论文段落初稿。",
    user_visible_steps: ["确认写作目标", "整理材料", "生成段落", "标注需补证据处"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["论文段落", "证据缺口", "修改建议"],
    save_to_project: true,
    developer_notes: "Keep claims conservative and ask for evidence when needed.",
  },
  english_polishing: {
    intent: "english_polishing",
    user_title: "英文润色",
    user_description: "在不改变原意的前提下润色英文，并检查过度表述。",
    group: "写论文",
    required_params: ["text"],
    optional_params: ["check_overclaim", "preserve_meaning"],
    default_params: { check_overclaim: true, preserve_meaning: true },
    confirmation_template: "我将润色你提供的英文文本，并保留原意、检查过度表述。",
    user_visible_steps: ["读取原文", "润色语言", "检查过度表述", "输出修改说明"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["润色稿", "修改说明", "风险提示"],
    save_to_project: false,
    developer_notes: "Plan-only in workspace; chat may later provide direct text polishing.",
  },
  peer_review_simulation: {
    intent: "peer_review_simulation",
    user_title: "模拟审稿",
    user_description: "模拟审稿人指出论文逻辑、证据、图表和写作问题。",
    group: "写论文",
    required_params: ["manuscript_or_summary"],
    optional_params: ["journal", "review_strictness"],
    default_params: { review_strictness: "normal" },
    confirmation_template: "我将模拟审稿人审阅“{manuscript_or_summary}”。",
    user_visible_steps: ["确认稿件材料", "检查逻辑链", "检查证据与图表", "整理审稿意见"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["审稿意见", "修改优先级", "风险清单"],
    save_to_project: true,
    developer_notes: "User-facing peer review simulation without exposing internal review skills.",
  },
  reviewer_response: {
    intent: "reviewer_response",
    user_title: "审稿回复",
    user_description: "把审稿意见拆成动作清单，生成逐条回复草稿。",
    group: "写论文",
    required_params: ["review_comments"],
    optional_params: ["revision_notes", "require_action_mapping", "require_revision_location"],
    default_params: { require_action_mapping: true, require_revision_location: true },
    confirmation_template: "我将根据审稿意见生成逐条回复，并要求映射修改动作和修改位置。",
    user_visible_steps: ["拆解审稿意见", "匹配修改动作", "标注修改位置", "生成回复草稿"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["回复信草稿", "修改动作表", "修改位置清单"],
    save_to_project: true,
    developer_notes: "Plan-only until document-aware revision tracking is connected.",
  },
  submission_checklist: {
    intent: "submission_checklist",
    user_title: "投稿材料检查",
    user_description: "检查投稿所需文件、声明、格式和补充材料是否齐全。",
    group: "写论文",
    required_params: ["journal"],
    optional_params: ["materials"],
    default_params: {},
    confirmation_template: "我将按“{journal}”投稿要求检查材料清单。",
    user_visible_steps: ["确认目标期刊", "列出材料要求", "检查缺口", "生成补齐清单"],
    execution_strategy: "needs_authorization",
    current_status: "needs_authorization",
    output_types: ["投稿清单", "缺失材料", "格式提醒"],
    save_to_project: true,
    developer_notes: "May require external journal-page access or user authorization before full checking.",
  },
  weekly_report: {
    intent: "weekly_report",
    user_title: "项目周报",
    user_description: "汇总项目进展、问题、风险和下周计划。",
    group: "写论文",
    required_params: ["current_progress"],
    optional_params: ["time_range", "focus"],
    default_params: { time_range: "recent" },
    confirmation_template: "我将汇总当前项目的最近进展并生成周报。",
    user_visible_steps: ["确认项目", "汇总最近记录", "整理风险和阻塞", "生成周报"],
    execution_strategy: "plan_only",
    current_status: "executable",
    output_types: ["项目周报", "风险清单", "下周计划"],
    save_to_project: true,
    developer_notes: "Plan-only in this controller unless weekly report persistence is wired later.",
  },
  data_analysis: {
    intent: "data_analysis",
    user_title: "上传表格分析",
    user_description: "兼容旧入口：根据表格和目标生成分析计划。",
    group: "分析数据",
    required_params: ["file_id", "analysis_goal"],
    optional_params: ["group_column", "value_column"],
    default_params: {},
    confirmation_template: "我将根据“{analysis_goal}”分析表格“{file_id}”。",
    user_visible_steps: ["选择数据表", "确认分析目标", "检查变量", "生成分析计划"],
    execution_strategy: "needs_file",
    current_status: "executable",
    output_types: ["分析计划", "图表建议", "结果解释"],
    save_to_project: true,
    developer_notes: "Backward-compatible alias for table_analysis.",
  },
  writing_review: {
    intent: "writing_review",
    user_title: "写论文段落",
    user_description: "兼容旧入口：整理、润色或审阅写作材料。",
    group: "写论文",
    required_params: ["writing_goal"],
    optional_params: ["materials", "section_type"],
    default_params: {},
    confirmation_template: "我将按“{writing_goal}”处理写作任务。",
    user_visible_steps: ["确认写作目标", "整理材料", "生成修改建议", "输出可继续编辑的文本"],
    execution_strategy: "plan_only",
    current_status: "plan_only",
    output_types: ["论文段落", "修改建议", "证据缺口"],
    save_to_project: true,
    developer_notes: "Backward-compatible alias for manuscript_section_writing.",
  },
};

const BACKEND_WORKFLOW_INTENTS = {
  citation_finder: "citation_support",
  paper_reader: "paper_deep_reading",
  paper_to_ppt: "nature_paper_to_ppt",
  experiment_design: "experiment_design",
  protocol_to_sop: "protocol_to_sop",
  failure_recovery: "failure_recovery",
  table_analysis: "scientific_data_analysis",
  qpcr_elisa_cck8_analysis: "scientific_data_analysis",
  data_analysis: "scientific_data_analysis",
  figure_generation: "nature_figure_generation",
  english_polishing: "nature_academic_polishing",
  reviewer_response: "nature_reviewer_response",
  weekly_report: "weekly_report",
  data_availability_statement: "nature_data_availability",
};

export function backendIntentForWorkflow(intent) {
  return BACKEND_WORKFLOW_INTENTS[intent] || "";
}

Object.entries(WORKFLOW_DEFINITIONS).forEach(([intent, definition]) => {
  definition.output_artifacts = WORKFLOW_OUTPUT_ARTIFACTS[intent] || ["data_analysis_report"];
  if (definition.output_artifacts.length) definition.save_to_project = true;
});

const QUESTION_BY_PARAM = {
  query: "请告诉我文献检索主题或关键词。",
  source: "请上传文件，或告诉我需要处理的论文、PDF、protocol 或资料来源。",
  claim: "请告诉我需要找引用支撑的论点。",
  research_goal: "请补充实验目标、模型或想验证的机制。",
  failure_description: "请描述实验失败现象、异常结果或已经排查过的条件。",
  experiment_notes: "请粘贴今天的实验记录或观察。",
  current_progress: "请告诉我当前进展和主要阻塞。",
  file_id: "请先上传或选择数据文件。",
  analysis_goal: "请告诉我分析目标，例如比较哪些组、输出什么图。",
  assay_type: "请告诉我数据类型，例如 qPCR、ELISA 或 CCK-8。",
  result_summary: "请粘贴结果摘要、差异代谢物或通路结果。",
  figure_goal: "请告诉我希望生成什么论文图表。",
  modeling_goal: "请告诉我建模目标、标签或预测问题。",
  writing_goal: "请告诉我写作目标或需要处理的段落。",
  text: "请粘贴需要润色的英文文本。",
  manuscript_or_summary: "请提供论文稿件、摘要或主要结果。",
  review_comments: "请粘贴审稿意见。",
  journal: "请告诉我目标期刊。",
  project_id: "请先选择一个项目。",
};

function nowIso() {
  return new Date().toISOString();
}

function normalize(value) {
  return String(value ?? "").trim();
}

function safeNumber(value, fallback) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
}

function compactId(value) {
  return normalize(value)
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function requireProjectId(projectId) {
  const normalized = normalize(projectId);
  if (!normalized) throw new Error("project_id is required");
  return normalized;
}

function workflowId(intent) {
  return `workflow-${compactId(intent) || "task"}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function historyKey(projectId) {
  return `${WORKFLOW_HISTORY_PREFIX}${compactId(requireProjectId(projectId))}`;
}

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Workflow history is a local convenience cache; failure should not block the task.
  }
}

function visibleParamValue(value, fallback = "待补充") {
  const text = normalize(value);
  return text || fallback;
}

export function workflowDefinitionsForWorkspace() {
  return Object.values(WORKFLOW_DEFINITIONS).filter((definition) => !["data_analysis", "writing_review"].includes(definition.intent));
}

export function groupedWorkflowDefinitions() {
  return WORKFLOW_GROUPS.map((group) => ({
    group,
    workflows: workflowDefinitionsForWorkspace().filter((definition) => definition.group === group),
  }));
}

export function normalizeWorkflowParams(intent, params = {}, context = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent] || {};
  const normalized = { ...(definition.default_params || {}), ...(params || {}) };
  if (normalized.topic && !normalized.query) normalized.query = normalized.topic;
  if (normalized.goal) {
    if (["experiment_design"].includes(intent) && !normalized.research_goal) normalized.research_goal = normalized.goal;
    if (["table_analysis", "data_analysis"].includes(intent) && !normalized.analysis_goal) normalized.analysis_goal = normalized.goal;
    if (["manuscript_section_writing", "writing_review"].includes(intent) && !normalized.writing_goal) normalized.writing_goal = normalized.goal;
  }
  if (normalized.file && !normalized.file_id) normalized.file_id = normalized.file;
  if (normalized.material && !normalized.writing_goal) normalized.writing_goal = normalized.material;
  if (normalized.phenomenon && !normalized.failure_description) normalized.failure_description = normalized.phenomenon;
  if (context.projectId && !normalized.project_id) normalized.project_id = context.projectId;
  if (intent === "literature_harvest_and_kb") {
    normalized.max_papers = Math.min(safeNumber(normalized.max_papers || normalized.targetCount, 20), 100);
    normalized.recent_years = safeNumber(normalized.recent_years, 5);
    normalized.oa_only = normalized.oa_only !== false && normalized.openAccessOnly !== false;
    normalized.build_kb = normalized.build_kb !== false && normalized.buildKnowledgeBase !== false;
    normalized.non_oa_policy = normalized.non_oa_policy || "manual_queue";
  }
  if (intent === "literature_search") {
    normalized.max_results = Math.min(safeNumber(normalized.max_results, 50), 100);
    normalized.recent_years = safeNumber(normalized.recent_years, 5);
    normalized.include_review = normalized.include_review !== false;
  }
  if (intent === "paper_to_ppt") {
    normalized.slide_count = Math.min(safeNumber(normalized.slide_count, 15), 80);
    normalized.language = normalized.language || "zh";
  }
  return normalized;
}

export function createWorkflowDraft(intent, initialParams = {}, context = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  if (!definition) {
    return {
      workflow_id: workflowId("unknown"),
      intent,
      title: "未知科研任务",
      params: { ...(initialParams || {}) },
      status: "failed",
      current_step: "无法识别任务",
      next_step: "请换一种方式描述你想完成的科研工作。",
      created_at: nowIso(),
      updated_at: nowIso(),
      context: { ...(context || {}) },
    };
  }
  const timestamp = nowIso();
  const params = normalizeWorkflowParams(intent, initialParams, context);
  const validation = validateWorkflowParams(intent, params);
  return {
    workflow_id: workflowId(intent),
    intent,
    title: definition.user_title,
    user_description: definition.user_description,
    params,
    status: validation.ok ? "draft" : "needs_input",
    required_params: [...definition.required_params],
    current_step: validation.ok ? "已收集必要信息" : "需要补充信息",
    next_step: validation.ok ? "生成计划并请你确认。" : validation.questions[0],
    created_at: timestamp,
    updated_at: timestamp,
    linked_conversation_id: context.conversationId || "",
    context: { ...(context || {}) },
    validation,
  };
}

export function validateWorkflowParams(intent, params = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  const missing = [];
  const questions = [];
  if (!definition) return { ok: false, missing: ["intent"], questions: ["我还不能识别这个任务，请换一种方式描述。"] };
  const normalized = normalizeWorkflowParams(intent, params, {});
  for (const key of definition.required_params) {
    if (key === "file_id" && (normalized.uploaded_file || normalized.file || normalized.source)) continue;
    if (!normalize(normalized[key])) missing.push(key);
  }
  missing.forEach((key) => questions.push(QUESTION_BY_PARAM[key] || "请补充执行这个任务所需的关键信息。"));
  return {
    ok: missing.length === 0,
    missing,
    questions: questions.length ? questions : ["请补充执行这个任务所需的关键信息。"],
  };
}

function fillTemplate(template, params) {
  return String(template || "").replace(/\{([A-Za-z0-9_]+)\}/g, (_, key) => visibleParamValue(params[key]));
}

export function buildWorkflowPlan(intent, params = {}, context = {}) {
  const definition = WORKFLOW_DEFINITIONS[intent];
  const normalized = normalizeWorkflowParams(intent, params, context);
  const validation = validateWorkflowParams(intent, normalized);
  if (!definition) {
    return {
      ok: false,
      status: "failed",
      title: "未知科研任务",
      message: "我还不能识别这个任务。",
      steps: [],
      next_step: "请换一种方式描述你想完成的科研工作。",
      validation,
    };
  }
  if (definition.current_status === "not_ready") {
    return {
      ok: false,
      status: "not_ready",
      intent,
      title: definition.user_title,
      message: "该功能正在接入中。",
      steps: [],
      current_step: "正在接入中",
      next_step: "请选择其他已开放的工作台功能。",
      params: normalized,
      validation,
    };
  }
  if (!validation.ok) {
    return {
      ok: false,
      status: "needs_input",
      title: definition.user_title,
      message: validation.questions[0],
      steps: ["补充必要信息"],
      next_step: validation.questions[0],
      params: normalized,
      validation,
    };
  }
  return {
    ok: true,
    status: "pending_confirmation",
    intent,
    title: definition.user_title,
    message: fillTemplate(definition.confirmation_template, normalized),
    steps: [...definition.user_visible_steps],
    current_step: "待确认",
    next_step: definition.current_status === "plan_only" ? "我可以先生成执行计划，确认后仍只输出计划，不会当作已执行成功。" : "确认后开始执行。",
    params: normalized,
    output_types: [...definition.output_types],
    technical: {
      execution_strategy: definition.execution_strategy,
      developer_notes: definition.developer_notes,
      current_status: definition.current_status,
    },
  };
}

function extractCount(text) {
  const match = text.match(/(?:找|下载|整理|改成|调整为|设置为|最多|前)?\s*(\d+)\s*篇/);
  return match ? Number(match[1]) : null;
}

const YEAR_WORDS = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 };

function extractRecentYears(text) {
  const match = normalize(text).match(/近\s*([一二两三四五六七八九十\d]+)\s*年/);
  if (!match) return null;
  if (/^\d+$/.test(match[1])) return Number(match[1]);
  return YEAR_WORDS[match[1]] || null;
}

function extractSlideCount(text) {
  const match = normalize(text).match(/(\d+)\s*页/);
  return match ? Number(match[1]) : null;
}

function extractQuery(text) {
  const normalized = normalize(text);
  const explicit = normalized.match(/(?:主题|方向|关键词|围绕|关于)\s*(?:是|为|：|:)?\s*([^，。；,.]+)/);
  if (explicit?.[1]) return normalize(explicit[1]);
  return normalized
    .replace(/^(请|麻烦|帮我|给我|可以)?/g, "")
    .replace(/近\s*[一二两三四五六七八九十\d]+\s*年/g, "")
    .replace(/\d+\s*(篇|页|条)/g, "")
    .replace(/(下载文献并构建知识库|下载文献构建知识库|下载文献并入库|下载文献|检索文献|采集文献|构建知识库|建立知识库|加入项目|查一下|查一些|找|搜索|检索|方向的论文|相关论文|文献清单|文献|论文|研究)/g, "")
    .replace(/[，。；、,.]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function updateWorkflowDraft(draft, userMessage) {
  const text = normalize(userMessage);
  const params = { ...(draft?.params || {}) };
  const intent = draft?.intent || "";
  const lower = text.toLowerCase();
  if (CANCEL_WORDS.some((word) => lower.includes(word))) {
    return { ...draft, status: "cancelled", updated_at: nowIso(), current_step: "已取消", next_step: "" };
  }
  const count = extractCount(text);
  const recentYears = extractRecentYears(text);
  const slideCount = extractSlideCount(text);
  if (intent === "literature_harvest_and_kb" && count) params.max_papers = count;
  if (intent === "literature_search" && count) params.max_results = count;
  if (["literature_harvest_and_kb", "literature_search", "citation_finder"].includes(intent) && recentYears) params.recent_years = recentYears;
  if (["literature_harvest_and_kb", "literature_search"].includes(intent)) {
    const query = extractQuery(text);
    if (/主题\s*(改成|改为|换成)/.test(text) || query) params.query = query || params.query;
  }
  if (intent === "paper_to_ppt" && slideCount) params.slide_count = slideCount;
  if (intent === "experiment_design") {
    if (!params.research_goal || /(目标|方案|实验|验证|模型|改成|改为)/.test(text)) params.research_goal = text;
    const model = text.match(/\b(RAW264\.7|BV2|小鼠|斑马鱼|大鼠|巨噬细胞)\b/i)?.[1];
    if (model) params.model = model.replace(/^raw/i, "RAW").replace(/^bv/i, "BV");
  }
  if (["table_analysis", "data_analysis"].includes(intent)) {
    if (!params.analysis_goal || /(分析|比较|输出|作图)/.test(text)) params.analysis_goal = text;
    if (!params.file_id && !params.uploaded_file) params.uploaded_file = text;
  }
  if (intent === "qpcr_elisa_cck8_analysis") {
    const assay = text.match(/\b(qPCR|ELISA|CCK-?8)\b/i)?.[1];
    if (assay) params.assay_type = assay.toLowerCase() === "qpcr" ? "qPCR" : assay.toUpperCase().replace("CCK8", "CCK-8");
    if (!params.analysis_goal) params.analysis_goal = text;
  }
  if (["ingest_uploaded_papers", "paper_reader", "paper_to_ppt", "protocol_to_sop"].includes(intent) && !params.source) params.source = text;
  if (intent === "citation_finder" && !params.claim) params.claim = text;
  if (intent === "failure_recovery" && !params.failure_description) params.failure_description = text;
  if (intent === "experiment_log" && !params.experiment_notes) params.experiment_notes = text;
  if (intent === "next_step_plan" && !params.current_progress) params.current_progress = text;
  if (intent === "metabolomics_interpretation" && !params.result_summary) params.result_summary = text;
  if (intent === "figure_generation" && !params.figure_goal) params.figure_goal = text;
  if (intent === "ml_modeling_assistant" && !params.modeling_goal) params.modeling_goal = text;
  if (["manuscript_section_writing", "writing_review"].includes(intent) && !params.writing_goal) params.writing_goal = text;
  if (intent === "english_polishing" && !params.text) params.text = text;
  if (intent === "peer_review_simulation" && !params.manuscript_or_summary) params.manuscript_or_summary = text;
  if (intent === "reviewer_response" && !params.review_comments) params.review_comments = text;
  if (intent === "submission_checklist" && !params.journal) params.journal = text;
  const normalized = normalizeWorkflowParams(intent, params, draft?.context || {});
  const validation = validateWorkflowParams(intent, normalized);
  const confirmed = CONFIRM_WORDS.some((word) => lower === word || lower.includes(word));
  return {
    ...draft,
    params: normalized,
    status: confirmed && validation.ok ? "confirmed" : validation.ok ? "draft" : "needs_input",
    current_step: validation.ok ? (confirmed ? "已确认" : "已更新参数") : "需要补充信息",
    next_step: validation.ok ? "确认后开始执行。" : validation.questions[0],
    updated_at: nowIso(),
    validation,
  };
}

function resultSummary(result) {
  return normalize(result?.message || result?.result_summary || result?.title || "任务状态已更新。");
}

function asTechnical(response) {
  return response?.data || response || {};
}

function backendMessage(response) {
  return normalize(response?.error || response?.data?.message || response?.data?.error || response?.message || "后端没有返回成功状态");
}

function failedWorkflowStep(intent, title, result, completedSteps = []) {
  return {
    ok: false,
    status: "failed",
    intent,
    title: "任务执行失败",
    message: `${title}没有完成：${backendMessage(result)}。已停止后续步骤。`,
    steps: [...completedSteps, `${title}失败`],
    current_step: `${title}失败`,
    next_step: "请检查项目、文件或服务状态后重试。",
    result_summary: `${title}没有完成，任务已停止。`,
    technical: asTechnical(result),
  };
}

function manualQueueCount(result) {
  const payload = result?.data || {};
  const rows = payload.paper_requests || payload.requests || payload.manual_queue || [];
  if (Array.isArray(rows)) return rows.length;
  return Number(payload.manual_queue_count || 0);
}

async function executeLiteratureWorkflow(draft, api) {
  const params = normalizeWorkflowParams(draft.intent, draft.params, draft.context || {});
  const projectId = requireProjectId(params.project_id || draft.context?.projectId);
  const payload = {
    project_id: projectId,
    query: params.query,
    keywords: [params.query].filter(Boolean),
    max_results: Math.min(safeNumber(params.max_papers, 20), 100),
    recent_years: safeNumber(params.recent_years, 5),
    oa_only: params.oa_only !== false,
    non_oa_policy: params.non_oa_policy || "manual_queue",
  };
  const completed = [];
  const createTask = await api.createLiteratureSearchTask(payload);
  if (!createTask?.ok) return failedWorkflowStep(draft.intent, "创建文献采集任务", createTask, completed);
  completed.push("创建文献采集任务");
  const search = await api.runLiteratureSearch(payload);
  if (!search?.ok) return failedWorkflowStep(draft.intent, "检索文献", search, completed);
  completed.push("检索开放获取文献");
  const paperRequests = await api.generatePaperRequests({ project_id: projectId });
  if (!paperRequests?.ok) return failedWorkflowStep(draft.intent, "整理手动下载队列", paperRequests, completed);
  completed.push("整理手动下载队列");
  let kb = null;
  if (params.build_kb !== false) {
    kb = await api.buildKnowledgeBase({ project_id: projectId });
    if (!kb?.ok) return failedWorkflowStep(draft.intent, "构建知识库", kb, completed);
    completed.push("构建项目知识库");
  } else {
    completed.push("跳过知识库构建");
  }
  const manualCount = manualQueueCount(paperRequests);
  return {
    ok: true,
    status: "completed",
    intent: draft.intent,
    title: WORKFLOW_DEFINITIONS[draft.intent].user_title,
    message:
      manualCount > 0
        ? `文献检索已完成，可合法开放获取的文献已处理；有 ${manualCount} 篇非开放获取或无法下载的文献已进入手动下载队列。`
        : "文献检索已完成，可合法开放获取的文献已处理，并已按设置构建知识库。",
    steps: completed,
    current_step: "已完成",
    next_step: manualCount > 0 ? "请在手动下载队列中补充无法自动获取的全文。" : "可以在资料库中查看结果。",
    manual_queue_count: manualCount,
    result_summary: manualCount > 0 ? `完成文献采集；${manualCount} 篇需要手动下载。` : "完成文献采集和知识库构建。",
    technical: { createTask: createTask.data, search: search.data, paperRequests: paperRequests.data, kb: kb?.data },
  };
}

async function executePlanOnlyWorkflow(draft, api, options = {}) {
  const definition = WORKFLOW_DEFINITIONS[draft.intent];
  const plan = buildWorkflowPlan(draft.intent, draft.params, draft.context || {});
  if (definition.current_status === "not_ready") {
    return {
      ok: false,
      status: "not_ready",
      intent: draft.intent,
      title: definition.user_title,
      message: "该功能正在接入中。",
      steps: [],
      current_step: "正在接入中",
      next_step: "请选择其他已开放的工作台功能。",
      result_summary: "该功能正在接入中。",
      technical: { execution_strategy: definition.execution_strategy, developer_notes: definition.developer_notes },
    };
  }
  if (definition.current_status === "needs_file") {
    return {
      ok: false,
      status: "needs_file",
      intent: draft.intent,
      title: definition.user_title,
      message: "请先上传文件或选择资料库文件。",
      steps: plan.steps || [],
      current_step: "需要上传文件",
      next_step: "上传文件或从资料库选择文件后再继续。",
      result_summary: "需要上传文件或选择资料库文件。",
      technical: { execution_strategy: definition.execution_strategy, developer_notes: definition.developer_notes },
    };
  }
  if (definition.current_status === "needs_authorization") {
    return {
      ok: false,
      status: "needs_authorization",
      intent: draft.intent,
      title: definition.user_title,
      message: "需要授权后执行。",
      steps: plan.steps || [],
      current_step: "需要授权",
      next_step: "授权后再继续执行。",
      result_summary: "需要授权后执行。",
      technical: { execution_strategy: definition.execution_strategy, developer_notes: definition.developer_notes },
    };
  }
  return {
    ok: true,
    status: "plan_only",
    intent: draft.intent,
    title: definition.user_title,
    message: `我可以先生成执行计划：${plan.message}`,
    steps: plan.steps,
    current_step: "已生成计划",
    next_step: "现在可以按计划准备材料；真实执行入口接入后可继续执行。",
    result_summary: "已生成工作流计划。",
    technical: { execution_strategy: definition.execution_strategy, plan_only: true, developer_notes: definition.developer_notes },
  };
}

function backendWorkflowParams(draft) {
  const params = { ...(draft.params || {}) };
  const intent = BACKEND_WORKFLOW_INTENTS[draft.intent];
  if (draft.intent === "citation_finder") params.claim = params.claim || params.text;
  if (draft.intent === "paper_reader") params.paper_text = params.paper_text || params.source;
  if (draft.intent === "paper_to_ppt") params.paper_text = params.paper_text || params.source;
  if (draft.intent === "experiment_design") params.objective = params.objective || params.research_goal;
  if (draft.intent === "protocol_to_sop") params.method_text = params.method_text || params.source;
  if (["table_analysis", "data_analysis"].includes(draft.intent)) params.artifact_id = params.artifact_id || params.file_id;
  if (draft.intent === "qpcr_elisa_cck8_analysis") {
    params.artifact_id = params.artifact_id || params.file_id;
    if (String(params.assay_type || "").toLowerCase() === "qpcr") params.runtime_template = "qpcr_template";
  }
  if (draft.intent === "figure_generation") {
    params.artifact_id = params.artifact_id || params.file_id;
    params.x = params.x || params.group_column;
    params.y = params.y || params.value_column;
  }
  if (draft.intent === "reviewer_response") params.reviewer_comments = params.reviewer_comments || params.review_comments;
  if (draft.intent === "data_availability_statement") params.dataset_inventory = params.dataset_inventory || params.inventory;
  return { intent, params };
}

async function executeRealBackendWorkflow(draft, api, options = {}) {
  const backend = backendWorkflowParams(draft);
  if (!backend.intent || typeof api?.executeWorkflowExecution !== "function") return null;
  const projectId = requireProjectId(draft.params?.project_id || options.projectId || draft.context?.projectId);
  const response = await api.executeWorkflowExecution({
    project_id: projectId,
    intent: backend.intent,
    params: backend.params,
    conversation_id: options.conversationId || draft.linked_conversation_id || "",
  });
  const result = response?.data || {};
  if (response?.ok && result.ok) return result;
  return {
    ok: false,
    status: result.status || "failed",
    intent: backend.intent,
    title: result.title || draft.title,
    message: result.message || response?.error || "后端未返回可验证的执行结果。",
    run_id: result.run_id || "",
    artifacts: Array.isArray(result.artifacts) ? result.artifacts : [],
    current_step: result.status || "failed",
    next_step: result.next_step || "请检查所需材料后重试。",
    technical: result.developer_diagnostics || result,
  };
}

export async function executeWorkflow(draft, api, options = {}) {
  if (!draft || draft?.status !== "confirmed") {
    return {
      ok: false,
      status: "pending_confirmation",
      intent: draft?.intent || "",
      title: draft?.title || "科研任务",
      message: "请先确认任务设置，我不会在确认前执行。",
      steps: ["等待用户确认"],
      current_step: "待确认",
      next_step: "点击确认开始，或继续修改参数。",
      result_summary: "任务等待确认。",
    };
  }
  const validation = validateWorkflowParams(draft.intent, draft.params || {});
  if (!validation.ok) {
    return {
      ok: false,
      status: "needs_input",
      intent: draft.intent,
      title: draft.title,
      message: validation.questions[0],
      steps: ["补充必要信息"],
      current_step: "需要补充信息",
      next_step: validation.questions[0],
      result_summary: "任务需要补充信息。",
    };
  }
  if (draft.intent === "literature_harvest_and_kb") return executeLiteratureWorkflow(draft, api);
  const realResult = await executeRealBackendWorkflow(draft, api, options);
  if (realResult) return realResult;
  return executePlanOnlyWorkflow(draft, api, options);
}

export function formatWorkflowResult(result, { developerMode = false } = {}) {
  const artifacts = Array.isArray(result?.artifacts) ? result.artifacts : [];
  const clean = {
    ok: Boolean(result?.ok),
    status: result?.status || "failed",
    intent: result?.intent || "",
    title: result?.title || "科研任务",
    message: result?.message || "任务状态已更新。",
    steps: Array.isArray(result?.steps) ? result.steps : [],
    current_step: result?.current_step || "",
    next_step: result?.next_step || "",
    manual_queue_count: result?.manual_queue_count || 0,
    result_summary: resultSummary(result),
    run_id: result?.run_id || "",
    project_id: result?.project_id || "",
    artifacts,
  };
  if (developerMode && result?.technical) clean.technical = result.technical;
  else if (developerMode && result?.developer_diagnostics) clean.technical = result.developer_diagnostics;
  return clean;
}

export function saveWorkflowArtifacts(projectId, workflow = {}, result = {}) {
  return saveArtifactsToProject(projectId, workflow, result);
}

export function workflowHistoryRecord(draft, result = {}) {
  const timestamp = nowIso();
  return {
    workflow_id: draft?.workflow_id || workflowId(draft?.intent || "workflow"),
    intent: draft?.intent || result?.intent || "",
    title: draft?.title || result?.title || "科研任务",
    params: { ...(draft?.params || {}) },
    status: result?.status || draft?.status || "draft",
    created_at: draft?.created_at || timestamp,
    updated_at: timestamp,
    result_summary: resultSummary(result),
    linked_conversation_id: draft?.linked_conversation_id || draft?.context?.conversationId || "",
  };
}

export function saveWorkflowHistory(projectId, record) {
  const key = historyKey(projectId || record?.params?.project_id);
  const existing = readJson(key, []);
  const nextRecord = { ...(record || {}), updated_at: record?.updated_at || nowIso() };
  const withoutDuplicate = existing.filter((item) => item.workflow_id !== nextRecord.workflow_id);
  const next = [nextRecord, ...withoutDuplicate].slice(0, 50);
  writeJson(key, next);
  if (typeof window !== "undefined") {
    window.dispatchEvent?.(new CustomEvent("researchos:workflow-history-updated", { detail: { projectId, workflow: nextRecord } }));
  }
  return nextRecord;
}

export function listWorkflowHistory(projectId) {
  return readJson(historyKey(projectId), []).sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
}

export function detectWorkflowIntent(message) {
  const text = normalize(message).toLowerCase();
  if (!text || text.includes("什么是阿尔茨海默症")) return null;
  const rules = [
    ["literature_harvest_and_kb", ["下载文献", "采集文献", "构建知识库", "下载文献并入库", "查一下", "查一些", "方向的论文"]],
    ["literature_search", ["检索文献", "找文献"]],
    ["ingest_uploaded_papers", ["学习我上传", "pdf 加入知识库", "解析这些文献"]],
    ["table_analysis", ["分析这个表格", "做统计", "做图", "分析数据"]],
    ["experiment_design", ["设计实验", "实验方案", "raw264.7"]],
    ["protocol_to_sop", ["整理 sop", "生成 sop", "protocol", "生成实验步骤"]],
    ["english_polishing", ["英文润色", "润色英文"]],
    ["peer_review_simulation", ["模拟审稿"]],
    ["reviewer_response", ["审稿回复", "回复审稿人"]],
    ["manuscript_section_writing", ["润色论文", "写结果", "整理讨论", "写论文"]],
    ["failure_recovery", ["实验失败", "数据不对", "没有结果", "排查"]],
    ["weekly_report", ["生成周报", "总结本周", "下周计划"]],
  ];
  const matches = rules.filter(([, triggers]) => triggers.some((trigger) => text.includes(trigger.toLowerCase())));
  if (matches.length !== 1) return null;
  const intent = matches[0][0];
  const params = {};
  if (["literature_harvest_and_kb", "literature_search"].includes(intent)) params.query = extractQuery(message);
  if (intent === "experiment_design") params.research_goal = message;
  if (intent === "table_analysis") params.analysis_goal = message;
  if (intent === "protocol_to_sop") params.source = message;
  if (intent === "manuscript_section_writing") params.writing_goal = message;
  if (intent === "english_polishing") params.text = message;
  if (intent === "peer_review_simulation") params.manuscript_or_summary = message;
  if (intent === "reviewer_response") params.review_comments = message;
  if (intent === "failure_recovery") params.failure_description = message;
  return { intent, title: WORKFLOW_DEFINITIONS[intent].user_title, params };
}

export function isWorkflowConfirmation(message) {
  const text = normalize(message).toLowerCase();
  return CONFIRM_WORDS.some((word) => text === word || text.includes(word));
}

export function isWorkflowCancellation(message) {
  const text = normalize(message).toLowerCase();
  return CANCEL_WORDS.some((word) => text.includes(word));
}
