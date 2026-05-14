import { badge, escapeHtml, statusTone, text } from "../components/cards.js";

export function featureStatusBadge(feature) {
  const status = feature?.status || "not_connected";
  return badge(`${text(feature?.display_name || feature?.label, "Feature")}: ${status}`, statusTone(status));
}

export function featureStatusRow(feature) {
  const dependencies = Array.isArray(feature?.not_connected_dependencies) ? feature.not_connected_dependencies : [];
  return `<article class="item-card">
    <h3 class="item-title">${escapeHtml(text(feature?.display_name || feature?.feature_id, "Feature"))}</h3>
    <p class="item-subtitle">${escapeHtml(text(feature?.user_goal, "No goal supplied."))}</p>
    <div class="item-meta">
      ${badge(text(feature?.preferred_pipeline, "No pipeline"), "success")}
      ${badge(text(feature?.status, "not_connected"), statusTone(feature?.status))}
      ${dependencies.length ? badge(`Needs: ${dependencies.join(", ")}`, "warning") : ""}
    </div>
  </article>`;
}
