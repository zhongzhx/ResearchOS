import { escapeHtml } from "./cards.js";

export function detailsBlock(title, body, open = false) {
  const content = body || "<p>暂无数据</p>";
  return `<details class="details"${open ? " open" : ""}>
    <summary>${escapeHtml(title)}</summary>
    <div class="details-body">${content}</div>
  </details>`;
}

export function fieldList(rows) {
  const items = rows
    .map(([label, value]) => `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value ?? "暂无数据")}</p>`)
    .join("");
  return items || "<p>暂无数据</p>";
}
