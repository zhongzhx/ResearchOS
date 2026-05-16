export const PRODUCT_FEATURES = [
  { feature_id: "dual_agent_research_task", label: "研究任务", chip: "设计实验", panel: "聊天" },
  { feature_id: "literature_harvest_workflow", label: "文献", chip: "收集文献", panel: "文献库 / 证据" },
  { feature_id: "data_analysis_workflow", label: "数据", chip: "分析数据", panel: "运行记录" },
  { feature_id: "protocol_to_sop_workflow", label: "SOP", chip: "构建 SOP", panel: "文献库 / 证据" },
  { feature_id: "experiment_design_workflow", label: "实验", chip: "设计实验", panel: "任务流程" },
  { feature_id: "failure_recovery_workflow", label: "失败诊断", chip: "诊断失败", panel: "研究大脑" },
  { feature_id: "writing_review_workflow", label: "写作", chip: "审阅写作", panel: "报告" },
  { feature_id: "weekly_report_workflow", label: "周报", chip: "生成报告", panel: "报告" },
];

export function featureById(featureId) {
  return PRODUCT_FEATURES.find((feature) => feature.feature_id === featureId) || null;
}

export function featureForChip(chip) {
  const normalized = String(chip || "").toLowerCase();
  return PRODUCT_FEATURES.find((feature) => feature.chip.toLowerCase() === normalized) || null;
}
