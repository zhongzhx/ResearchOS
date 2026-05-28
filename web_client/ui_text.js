const STATUS_LABELS = {
  demo_only: "演示预览",
  not_connected: "尚未接入",
  partial: "部分可用",
  needs_authorization: "需要授权",
  parser_not_connected: "数据解析器尚未接入",
  experimental: "实验功能",
  legacy_stable: "稳定聊天",
  safe_to_promote: "可加入项目记忆",
  failed: "失败",
  fail: "失败",
  error: "错误",
  completed: "已完成",
  complete: "已完成",
  done: "已完成",
  running: "运行中",
  active: "可用",
  ready: "可用",
  pending: "等待处理",
  draft: "草稿",
  disabled: "未启用",
  internal_control: "内部控制",
  "internal/control": "内部控制",
};

const PHRASE_LABELS = [
  [/demo_only/g, "演示预览"],
  [/not_connected/g, "尚未接入"],
  [/needs_authorization/g, "需要授权"],
  [/parser_not_connected/g, "数据解析器尚未接入"],
  [/safe_to_promote/g, "可加入项目记忆"],
  [/internal\/control/g, "内部控制"],
];

export function displayStatus(value, fallback = "未知") {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  const key = raw.toLowerCase();
  return STATUS_LABELS[key] || raw;
}

export function displayUserText(value, fallback = "暂无数据") {
  let text = String(value ?? "").trim();
  if (!text) return fallback;
  for (const [pattern, replacement] of PHRASE_LABELS) {
    text = text.replace(pattern, replacement);
  }
  return text;
}
