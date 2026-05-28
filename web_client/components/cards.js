import { displayStatus, displayUserText } from "../ui_text.js";

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function text(value, fallback = "暂无数据") {
  if (value === null || value === undefined) return fallback;
  const normalized = displayUserText(value, "").trim();
  return normalized || fallback;
}

export function asArray(value) {
  return Array.isArray(value) ? value : [];
}

export function firstArray(payload, keys) {
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

export function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (["success", "ok", "active", "done", "completed", "validated", "ready"].some((part) => value.includes(part))) return "success";
  if (["fail", "error", "reject", "blocked"].some((part) => value.includes(part))) return "danger";
  if (["pending", "review", "warning", "partial", "draft"].some((part) => value.includes(part))) return "warning";
  return "muted";
}

export function badge(label, tone = "muted") {
  return `<span class="badge ${escapeHtml(tone)}">${escapeHtml(displayStatus(text(label, "未知")))}</span>`;
}

export function compactPath(value) {
  const path = text(value, "");
  if (!path) return "";
  const parts = path.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 3) return path;
  return `.../${parts.slice(-3).join("/")}`;
}

export function itemCard({ title, subtitle = "", meta = [], status = "", error = false, clickable = false, data = "" }) {
  const metaItems = [
    status ? badge(status, statusTone(status)) : "",
    ...meta.filter(Boolean).map((item) => (typeof item === "string" ? badge(item) : badge(item.label, item.tone))),
  ].join("");
  const tag = clickable ? "button" : "article";
  const dataAttr = data ? ` data-item-id="${escapeHtml(data)}"` : "";
  return `<${tag} class="item-card ${error ? "error" : ""} ${clickable ? "clickable" : ""}"${dataAttr}>
    <h3 class="item-title">${escapeHtml(text(title, "未命名"))}</h3>
    <p class="item-subtitle">${escapeHtml(text(subtitle, "暂无数据"))}</p>
    ${metaItems ? `<div class="item-meta">${metaItems}</div>` : ""}
  </${tag}>`;
}

export function metricCards(metrics) {
  return `<div class="metric-grid">${metrics
    .map((metric) => `<div class="metric-card"><strong>${escapeHtml(metric.value ?? 0)}</strong><span>${escapeHtml(metric.label)}</span></div>`)
    .join("")}</div>`;
}

export function apiErrorCard(result, title = "该区域暂时不可用") {
  return itemCard({ title, subtitle: result?.error || "后端接口没有返回数据。", status: result?.status || "error", error: true });
}

export function loadingPanel(message = "加载中") {
  return `<div class="empty-state"><div><strong>${escapeHtml(message)}</strong><p>正在读取最新 ResearchOS 数据。</p></div></div>`;
}
