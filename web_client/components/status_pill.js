import { escapeHtml } from "./cards.js";

export function statusPill(label, tone = "muted", id = "") {
  return `<span${id ? ` id="${escapeHtml(id)}"` : ""} class="status-pill ${escapeHtml(tone)}">${escapeHtml(label)}</span>`;
}
