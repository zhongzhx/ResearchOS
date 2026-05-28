export const ARTIFACT_STORAGE_PREFIX = "researchos.artifacts.v1.";

export const ARTIFACT_TYPES = {
  literature_table: {
    label: "文献清单",
    description: "包含 title、authors、year、journal、doi、中文摘要、推荐理由、OA 状态。",
    format: "md",
    downloadable: true,
  },
  manual_download_queue: {
    label: "手动下载队列",
    description: "包含 title、doi、reason、priority、recommended_action。",
    format: "md",
    downloadable: true,
  },
  paper_reading_markdown: {
    label: "中文论文精读 Markdown",
    description: "包含核心问题、方法、结果、图表解释、局限性、可引用句子。",
    format: "md",
    downloadable: true,
  },
  journal_club_ppt: {
    label: "组会 PPT",
    description: "输出 pptx 或 PPT 计划。",
    format: "pptx",
    downloadable: true,
    planOnlyLabel: "生成 PPT 计划",
  },
  publication_figure: {
    label: "论文图",
    description: "优先 SVG，附图注和作图说明。",
    format: "svg",
    downloadable: true,
    preview: "figure",
  },
  polished_text: {
    label: "润色文本",
    description: "包含修改后版本、修改说明、过度声称提示。",
    format: "md",
    downloadable: true,
  },
  citation_pack: {
    label: "引用包",
    description: "包含支持 claim 的文献、DOI、支持等级、RIS/ENW 导出占位。",
    format: "md",
    downloadable: true,
  },
  sop_document: {
    label: "SOP 文档",
    description: "包含材料、步骤、质控、注意事项、风险点。",
    format: "md",
    downloadable: true,
  },
  experiment_design_plan: {
    label: "实验方案",
    description: "包含分组、模型、剂量、指标、统计、风险。",
    format: "md",
    downloadable: true,
  },
  data_analysis_report: {
    label: "数据分析报告",
    description: "包含方法、结果、图表、结论、限制。",
    format: "md",
    downloadable: true,
  },
  reviewer_response_letter: {
    label: "审稿回复",
    description: "包含 comment id、response、action、revision location。",
    format: "md",
    downloadable: true,
  },
  weekly_report_document: {
    label: "周报",
    description: "包含本周进展、问题、下周计划、待办。",
    format: "md",
    downloadable: true,
  },
};

export const WORKFLOW_OUTPUT_ARTIFACTS = {
  literature_search: ["literature_table"],
  literature_harvest_and_kb: ["literature_table", "manual_download_queue"],
  ingest_uploaded_papers: ["paper_reading_markdown"],
  paper_reader: ["paper_reading_markdown"],
  citation_finder: ["citation_pack"],
  paper_to_ppt: ["journal_club_ppt"],
  experiment_design: ["experiment_design_plan"],
  protocol_to_sop: ["sop_document"],
  failure_recovery: ["experiment_design_plan"],
  experiment_log: ["sop_document"],
  next_step_plan: ["experiment_design_plan"],
  table_analysis: ["data_analysis_report"],
  qpcr_elisa_cck8_analysis: ["data_analysis_report"],
  metabolomics_interpretation: ["data_analysis_report"],
  figure_generation: ["publication_figure"],
  ml_modeling_assistant: ["data_analysis_report"],
  manuscript_section_writing: ["polished_text"],
  english_polishing: ["polished_text"],
  peer_review_simulation: ["reviewer_response_letter"],
  reviewer_response: ["reviewer_response_letter"],
  submission_checklist: ["sop_document"],
  weekly_report: ["weekly_report_document"],
  data_analysis: ["data_analysis_report"],
  writing_review: ["polished_text"],
};

const CONTENT_SECTIONS = {
  literature_table: ["文献条目", "中文摘要", "推荐理由", "OA 状态"],
  manual_download_queue: ["待下载文献", "原因", "优先级", "建议动作"],
  paper_reading_markdown: ["核心问题", "方法", "结果", "图表解释", "局限性", "可引用句子"],
  journal_club_ppt: ["汇报主线", "PPT 结构", "讲稿备注", "待补充素材"],
  publication_figure: ["图形预览", "图注", "作图说明", "导出说明"],
  polished_text: ["修改后版本", "修改说明", "过度声称提示"],
  citation_pack: ["待支持 claim", "候选文献", "支持等级", "RIS/ENW 导出占位"],
  sop_document: ["材料", "步骤", "质控", "注意事项", "风险点"],
  experiment_design_plan: ["分组", "模型", "剂量", "指标", "统计", "风险"],
  data_analysis_report: ["方法", "结果", "图表", "结论", "限制"],
  reviewer_response_letter: ["comment id", "response", "action", "revision location"],
  weekly_report_document: ["本周进展", "问题", "下周计划", "待办"],
};

function nowIso() {
  return new Date().toISOString();
}

function safeProjectId(projectId) {
  return String(projectId || "default").trim() || "default";
}

function safeText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function safeSlug(value, fallback = "artifact") {
  return safeText(value, fallback)
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64) || fallback;
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
    // Project artifacts can be migrated to the backend artifact API later.
  }
}

function generateArtifactId(artifact) {
  const seed = [artifact.workflow_id, artifact.artifact_type, artifact.title, Date.now(), Math.random().toString(36).slice(2)].join("-");
  return `artifact-${safeSlug(seed)}`;
}

function artifactTitle(workflow, artifactType, index = 0) {
  const definition = ARTIFACT_TYPES[artifactType] || {};
  const workflowTitle = safeText(workflow?.title || workflow?.user_title || workflow?.intent || workflow?.workflow_id, "科研交付物");
  if (index > 0) return `${workflowTitle} - ${definition.label || artifactType}`;
  return workflowTitle.includes(definition.label || artifactType) ? workflowTitle : `${workflowTitle} - ${definition.label || artifactType}`;
}

function paramsMarkdown(params = {}) {
  const entries = Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== "");
  if (!entries.length) return "- 暂无参数";
  return entries.map(([key, value]) => `- ${key}: ${String(value)}`).join("\n");
}

function fallbackContent(artifactType, workflow, result) {
  const label = ARTIFACT_TYPES[artifactType]?.label || artifactType;
  const sections = CONTENT_SECTIONS[artifactType] || ["内容", "下一步"];
  const status = result?.status === "plan_only" ? "计划草稿" : "已生成";
  const lines = [`# ${artifactTitle(workflow, artifactType)}`, "", `状态：${status}`, "", "## 任务摘要", safeText(result?.message || result?.result_summary, "暂无摘要。"), "", "## 输入参数", paramsMarkdown(workflow?.params || result?.params || {})];
  sections.forEach((section) => {
    lines.push("", `## ${section}`, `- ${label}将在真实执行结果接入后补全；当前内容来自已确认的工作流计划或执行摘要。`);
  });
  if (artifactType === "publication_figure") {
    lines.push("", "```svg", '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" role="img" aria-label="publication figure placeholder"><rect width="100%" height="100%" fill="#f8fafc"/><text x="50%" y="50%" text-anchor="middle" fill="#334155" font-size="18">Publication figure plan</text></svg>', "```");
  }
  if (artifactType === "citation_pack") {
    lines.push("", "## RIS/ENW 导出占位", "- RIS: 待生成", "- ENW: 待生成");
  }
  return lines.join("\n");
}

function contentFromResult(artifactType, workflow, result) {
  const direct = result?.artifact_content?.[artifactType] || result?.content_markdown || result?.content;
  if (direct) return String(direct);
  if (artifactType === "manual_download_queue" && Number(result?.manual_queue_count || 0) > 0) {
    return [`# ${artifactTitle(workflow, artifactType)}`, "", `需要手动下载：${Number(result.manual_queue_count)} 篇`, "", "## 建议动作", "- 在资料库的手动下载队列中补充无法自动获取的全文。"].join("\n");
  }
  return fallbackContent(artifactType, workflow, result);
}

export function artifactStorageKey(projectId) {
  return `${ARTIFACT_STORAGE_PREFIX}${safeProjectId(projectId)}`;
}

export function normalizeArtifact(projectId, artifact = {}) {
  const artifactType = artifact.artifact_type || artifact.type || "data_analysis_report";
  const typeDefinition = ARTIFACT_TYPES[artifactType] || {};
  const normalizedProjectId = safeProjectId(projectId || artifact.project_id);
  const createdAt = artifact.created_at || nowIso();
  const normalized = {
    artifact_id: artifact.artifact_id || artifact.id || generateArtifactId({ ...artifact, artifact_type: artifactType }),
    project_id: normalizedProjectId,
    workflow_id: artifact.workflow_id || artifact.source_workflow_id || "",
    artifact_type: artifactType,
    title: safeText(artifact.title || typeDefinition.label, "科研交付物"),
    content: safeText(artifact.content || artifact.content_markdown || artifact.body, ""),
    created_at: createdAt,
    source_intent: artifact.source_intent || artifact.intent || artifact.workflow_id || "",
    status: artifact.status || "completed",
    downloadable: artifact.downloadable !== false && typeDefinition.downloadable !== false,
    metadata: { ...(artifact.metadata || {}), format: artifact.format || typeDefinition.format || "md" },
  };
  return normalized;
}

export function listProjectArtifacts(projectId) {
  return readJson(artifactStorageKey(projectId), []).sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

export function getProjectArtifact(projectId, artifactId) {
  return listProjectArtifacts(projectId).find((artifact) => artifact.artifact_id === artifactId) || null;
}

export function saveArtifactToProject(projectId, artifact) {
  const normalized = normalizeArtifact(projectId, artifact);
  const existing = listProjectArtifacts(normalized.project_id);
  const withoutDuplicate = existing.filter((item) => item.artifact_id !== normalized.artifact_id);
  const next = [normalized, ...withoutDuplicate].slice(0, 100);
  writeJson(artifactStorageKey(normalized.project_id), next);
  if (typeof window !== "undefined") {
    window.dispatchEvent?.(new CustomEvent("researchos:artifacts-updated", { detail: { projectId: normalized.project_id, artifact: normalized } }));
  }
  return normalized;
}

export function createArtifactsForWorkflowResult(workflow = {}, result = {}, options = {}) {
  const artifactTypes = options.outputArtifacts || workflow.output_artifacts || WORKFLOW_OUTPUT_ARTIFACTS[workflow.intent || result.intent] || [];
  const projectId = safeProjectId(options.projectId || workflow.project_id || workflow.context?.projectId || workflow.params?.project_id || result.project_id);
  const workflowId = workflow.workflow_id || result.workflow_id || workflow.intent || result.intent || "workflow";
  return artifactTypes.map((artifactType, index) =>
    normalizeArtifact(projectId, {
      workflow_id: workflowId,
      artifact_type: artifactType,
      title: artifactTitle(workflow || result, artifactType, index),
      content: contentFromResult(artifactType, workflow, result),
      created_at: result.created_at || nowIso(),
      source_intent: workflow.intent || result.intent || workflowId,
      status: result.status || "completed",
      downloadable: ARTIFACT_TYPES[artifactType]?.downloadable !== false,
      metadata: {
        plan_only: result.status === "plan_only",
        result_status: result.status || "",
        source: workflow.context?.source || options.source || "",
      },
    }),
  );
}

export function saveWorkflowArtifacts(projectId, workflow = {}, result = {}) {
  const artifacts = Array.isArray(result?.artifacts) && result.artifacts.length ? result.artifacts : createArtifactsForWorkflowResult(workflow, result, { projectId });
  return artifacts.map((artifact) => saveArtifactToProject(projectId || artifact.project_id, artifact));
}
