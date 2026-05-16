import { escapeHtml } from "./cards.js";

export function emptyState(title, subtitle = "") {
  return `<div class="empty-state"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(subtitle)}</p></div></div>`;
}
