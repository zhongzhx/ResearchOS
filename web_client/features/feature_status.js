import { badge, escapeHtml, statusTone, text } from "../components/cards.js";

export function featureStatusBadge(feature) {
  const status = feature?.status || "not_connected";
  return badge(`${text(feature?.display_name || feature?.label, "功能")}: ${status}`, statusTone(status));
}

export function featureStatusRow(feature) {
  const dependencies = Array.isArray(feature?.not_connected_dependencies) ? feature.not_connected_dependencies : [];
  return `<article class="item-card">
    <h3 class="item-title">${escapeHtml(text(feature?.display_name || feature?.feature_id, "功能"))}</h3>
    <p class="item-subtitle">${escapeHtml(text(feature?.user_goal, "暂无目标。"))}</p>
    <div class="item-meta">
      ${badge(text(feature?.preferred_pipeline, "暂无流程"), "success")}
      ${badge(text(feature?.status, "not_connected"), statusTone(feature?.status))}
      ${dependencies.length ? badge(`需要：${dependencies.join(", ")}`, "warning") : ""}
    </div>
  </article>`;
}
