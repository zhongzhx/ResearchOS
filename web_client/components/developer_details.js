import { escapeHtml } from "./cards.js";

export function developerDetails(label, value, enabled = false) {
  if (!enabled) return "";
  return `<details class="details developer-details">
    <summary>${escapeHtml(label || "Developer details")}</summary>
    <pre>${escapeHtml(JSON.stringify(value || {}, null, 2))}</pre>
  </details>`;
}
