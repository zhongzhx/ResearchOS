import { escapeHtml } from "./cards.js";

export function detailsBlock(title, body, open = false) {
  const content = body || "<p>Not available yet</p>";
  return `<details class="details"${open ? " open" : ""}>
    <summary>${escapeHtml(title)}</summary>
    <div class="details-body">${content}</div>
  </details>`;
}

export function fieldList(rows) {
  const items = rows
    .map(([label, value]) => `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value ?? "Not available yet")}</p>`)
    .join("");
  return items || "<p>Not available yet</p>";
}
