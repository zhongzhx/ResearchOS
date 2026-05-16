import { detailsBlock } from "./details.js";
import { escapeHtml } from "./cards.js";

const SECRET_KEY_RE = /(api[_-]?key|token|secret|password|cookie|authorization)/i;
const PATH_RE = /([A-Za-z]:\\|\/(?:Users|home|var|tmp|mnt|Volumes)\/)/;

function redact(value, depth = 0) {
  if (depth > 7) return "[Max depth reached]";
  if (Array.isArray(value)) return value.slice(0, 80).map((item) => redact(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => {
        if (SECRET_KEY_RE.test(key)) return [key, "[redacted]"];
        return [key, redact(nested, depth + 1)];
      }),
    );
  }
  if (typeof value === "string") {
    if (SECRET_KEY_RE.test(value)) return "[redacted]";
    const pathFolded = PATH_RE.test(value) && value.length > 80 ? `[path] ${value.split(/[\\/]+/).slice(-3).join("/")}` : value;
    return pathFolded.length > 900 ? `${pathFolded.slice(0, 897)}...` : pathFolded;
  }
  return value;
}

export function safeJson(value) {
  return JSON.stringify(redact(value), null, 2);
}

export function jsonViewer(value) {
  return `<pre class="json-view">${escapeHtml(safeJson(value ?? {}))}</pre>`;
}

export function jsonDetails(title, value, open = false) {
  return detailsBlock(title, jsonViewer(value), open);
}
