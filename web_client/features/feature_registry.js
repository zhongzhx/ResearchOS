export const PRODUCT_FEATURES = [
  { feature_id: "dual_agent_research_task", label: "Research Task", chip: "Design experiment", panel: "Chat" },
  { feature_id: "literature_harvest_workflow", label: "Literature", chip: "Collect literature", panel: "Library / Evidence" },
  { feature_id: "data_analysis_workflow", label: "Data", chip: "Analyze data", panel: "Runs" },
  { feature_id: "protocol_to_sop_workflow", label: "SOP", chip: "Build SOP", panel: "Library / Evidence" },
  { feature_id: "experiment_design_workflow", label: "Experiment", chip: "Design experiment", panel: "Task Lifecycle" },
  { feature_id: "failure_recovery_workflow", label: "Failure", chip: "Diagnose failure", panel: "Research Brain" },
  { feature_id: "writing_review_workflow", label: "Writing", chip: "Review writing", panel: "Reports" },
  { feature_id: "weekly_report_workflow", label: "Weekly", chip: "Generate report", panel: "Reports" },
];

export function featureById(featureId) {
  return PRODUCT_FEATURES.find((feature) => feature.feature_id === featureId) || null;
}

export function featureForChip(chip) {
  const normalized = String(chip || "").toLowerCase();
  return PRODUCT_FEATURES.find((feature) => feature.chip.toLowerCase() === normalized) || null;
}
