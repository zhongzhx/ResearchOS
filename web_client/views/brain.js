import {
  getClaimReview,
  getClaims,
  getDecisions,
  getEvidenceReview,
  getFailures,
  getMemoryContext,
  getMemoryReviewQueue,
  getProtocols,
  getRelationships,
  getReports,
} from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, firstArray, itemCard, metricCards, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

let activeTab = "Claims";
const tabs = ["Claims", "Decisions", "Failures", "Protocols", "Reports", "Relationships", "Review Queue"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-brain-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function rowFor(item, fallbackType = "memory") {
  return itemCard({
    title: item.title || item.claim || item.name || item.report_id || item.id || item.relation || "Untitled",
    subtitle: item.summary || item.description || item.statement || item.recovery_suggestion || item.source || "No summary yet",
    status: item.status || item.confidence || item.trust_level || fallbackType,
    meta: [item.type || item.claim_type || item.protocol_type || "", item.updated_at || item.created_at || ""].filter(Boolean),
  });
}

function renderRows(rows, emptyLabel) {
  if (!rows.length) return emptyState(emptyLabel, "This area will populate as AURA promotes validated research memory.");
  return `<div class="list">${rows.slice(0, 80).map((row) => rowFor(row)).join("")}</div>`;
}

function reviewRows(memoryReview, evidenceReview, claimReview) {
  const rows = [
    ...firstArray(memoryReview?.data, ["review_queue", "items"]).map((item) => ({ ...item, type: item.type || "memory review" })),
    ...firstArray(evidenceReview?.data, ["items", "evidence", "evidence_review_items"]).map((item) => ({ ...item, type: item.type || "evidence review" })),
    ...firstArray(claimReview?.data, ["claims", "items", "review_queue"]).map((item) => ({ ...item, type: item.type || "claim review" })),
  ];
  return renderRows(rows, "No review queue items");
}

export async function renderBrainView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">Research Brain</h1><p class="page-subtitle">Project memory, claims, decisions, failures, protocols, reports, relationships, and review queues.</p></div>
    </header>
    <div class="page-scroll"><div class="grid" id="brainContent">${emptyState("Loading Research Brain", "Fetching memory context and canonical records.")}</div></div>
  </section>`;

  const [context, memoryReview, claims, decisions, failures, protocols, reports, relationships, evidenceReview, claimReview] = await Promise.all([
    getMemoryContext(appState.activeProjectId),
    getMemoryReviewQueue(appState.activeProjectId),
    getClaims(appState.activeProjectId),
    getDecisions(appState.activeProjectId),
    getFailures(appState.activeProjectId),
    getProtocols(appState.activeProjectId),
    getReports(appState.activeProjectId),
    getRelationships(appState.activeProjectId),
    getEvidenceReview(appState.activeProjectId),
    getClaimReview(appState.activeProjectId),
  ]);

  const data = {
    Claims: firstArray(claims.data, ["claims"]),
    Decisions: firstArray(decisions.data, ["decisions"]),
    Failures: firstArray(failures.data, ["failures"]),
    Protocols: firstArray(protocols.data, ["protocols"]),
    Reports: firstArray(reports.data, ["reports"]),
    Relationships: firstArray(relationships.data, ["relationships"]),
  };
  const resultByTab = { Claims: claims, Decisions: decisions, Failures: failures, Protocols: protocols, Reports: reports, Relationships: relationships };
  const metrics = Object.entries(data).map(([label, rows]) => ({ label, value: rows.length }));
  const content = root.querySelector("#brainContent");
  const contextText = context.ok ? text(context.data.summary || context.data.context || context.data.memory_context, "No memory context returned yet.") : context.error;
  const currentRows =
    activeTab === "Review Queue"
      ? reviewRows(memoryReview, evidenceReview, claimReview)
      : resultByTab[activeTab]?.ok
        ? renderRows(data[activeTab] || [], `No ${activeTab.toLowerCase()} yet`)
        : apiErrorCard(resultByTab[activeTab], `${activeTab} endpoint unavailable`);

  content.innerHTML = `
    <div class="panel pad"><p class="muted">${text(contextText)}</p></div>
    ${metricCards(metrics)}
    <div class="panel pad">
      ${tabButtons()}
      ${currentRows}
      ${jsonDetails("Raw Research Brain payload", { context: context.data, memoryReview: memoryReview.data, claims: claims.data, decisions: decisions.data, failures: failures.data, protocols: protocols.data, reports: reports.data, relationships: relationships.data })}
    </div>`;

  root.querySelectorAll("[data-brain-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.brainTab;
      renderBrainView({ root });
    });
  });
}
