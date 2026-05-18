import {
  getClaimReview,
  getClaims,
  getDecisions,
  getEvidenceReview,
  getFailures,
  getCognitiveState,
  getMemoryEpisodes,
  getMemoryEvents,
  getMemoryHealth,
  getMemoryItems,
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

let activeTab = "主张";
const tabs = ["主张", "决策", "失败记录", "实验方案", "报告", "关系", "MemoryOS", "待复核"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-brain-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function rowFor(item, fallbackType = "memory") {
  return itemCard({
    title: item.title || item.claim || item.name || item.report_id || item.id || item.relation || "未命名",
    subtitle: item.summary || item.description || item.statement || item.recovery_suggestion || item.source || "暂无摘要",
    status: item.status || item.confidence || item.trust_level || fallbackType,
    meta: [item.type || item.claim_type || item.protocol_type || "", item.updated_at || item.created_at || ""].filter(Boolean),
  });
}

function renderRows(rows, emptyLabel) {
  if (!rows.length) return emptyState(emptyLabel, "AURA 将在验证研究记忆后填充这里。");
  return `<div class="list">${rows.slice(0, 80).map((row) => rowFor(row)).join("")}</div>`;
}

function reviewRows(memoryReview, evidenceReview, claimReview) {
  const rows = [
    ...firstArray(memoryReview?.data, ["review_queue", "items"]).map((item) => ({ ...item, type: item.type || "记忆复核" })),
    ...firstArray(evidenceReview?.data, ["items", "evidence", "evidence_review_items"]).map((item) => ({ ...item, type: item.type || "证据复核" })),
    ...firstArray(claimReview?.data, ["claims", "items", "review_queue"]).map((item) => ({ ...item, type: item.type || "主张复核" })),
  ];
  return renderRows(rows, "暂无待复核项");
}

function memoryOsRows(memoryItems, episodes, events, health, cognitiveState) {
  if ([memoryItems, episodes, events, health, cognitiveState].some((result) => result?.data?.status === "disabled")) {
    return emptyState("MemoryOS 未启用", "设置 RESEARCHOS_MEMORYOS_ENABLED=true 后可以查看增强记忆层。");
  }
  const rows = [
    ...firstArray(memoryItems?.data, ["items"]).map((item) => ({ ...item, type: item.type || item.memory_type || "记忆项" })),
    ...firstArray(episodes?.data, ["episodes"]).map((item) => ({ ...item, type: item.type || "片段" })),
    ...firstArray(events?.data, ["events"]).map((item) => ({ ...item, type: item.event_type || "记忆事件" })),
  ];
  const statusRows = [
    health?.ok ? { id: "memory_health", title: "记忆健康", summary: JSON.stringify(health.data.health || {}), status: "health" } : null,
    cognitiveState?.ok ? { id: "cognitive_state", title: "认知状态", summary: JSON.stringify(cognitiveState.data.cognitive_state || {}), status: "state" } : null,
  ].filter(Boolean);
  return renderRows([...statusRows, ...rows], "暂无 MemoryOS 记录");
}

export async function renderBrainView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">研究记忆</h1><p class="page-subtitle">查看项目记忆、主张、决策、失败记录、实验方案、报告、关系和复核队列。</p></div>
    </header>
    <div class="page-scroll"><div class="grid" id="brainContent">${emptyState("正在加载研究大脑", "正在读取记忆上下文和标准记录。")}</div></div>
  </section>`;

  const [context, memoryReview, claims, decisions, failures, protocols, reports, relationships, evidenceReview, claimReview, memoryItems, episodes, memoryEvents, memoryHealth, cognitiveState] = await Promise.all([
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
    getMemoryItems(appState.activeProjectId),
    getMemoryEpisodes(appState.activeProjectId),
    getMemoryEvents(appState.activeProjectId),
    getMemoryHealth(appState.activeProjectId),
    getCognitiveState(appState.activeProjectId),
  ]);

  const data = {
    主张: firstArray(claims.data, ["claims"]),
    决策: firstArray(decisions.data, ["decisions"]),
    失败记录: firstArray(failures.data, ["failures"]),
    实验方案: firstArray(protocols.data, ["protocols"]),
    报告: firstArray(reports.data, ["reports"]),
    关系: firstArray(relationships.data, ["relationships"]),
  };
  const resultByTab = { 主张: claims, 决策: decisions, 失败记录: failures, 实验方案: protocols, 报告: reports, 关系: relationships };
  const metrics = Object.entries(data).map(([label, rows]) => ({ label, value: rows.length }));
  const content = root.querySelector("#brainContent");
  const contextText = context.ok ? text(context.data.summary || context.data.context || context.data.memory_context, "暂无记忆上下文。") : context.error;
  const currentRows =
    activeTab === "待复核"
      ? reviewRows(memoryReview, evidenceReview, claimReview)
      : activeTab === "MemoryOS"
        ? memoryOsRows(memoryItems, episodes, memoryEvents, memoryHealth, cognitiveState)
      : resultByTab[activeTab]?.ok
        ? renderRows(data[activeTab] || [], `暂无${activeTab}`)
        : apiErrorCard(resultByTab[activeTab], `${activeTab}接口不可用`);

  content.innerHTML = `
    <div class="panel pad"><p class="muted">${text(contextText)}</p></div>
    ${metricCards(metrics)}
    <div class="panel pad">
      ${tabButtons()}
      ${currentRows}
      ${jsonDetails("研究大脑原始数据", { context: context.data, memoryReview: memoryReview.data, claims: claims.data, decisions: decisions.data, failures: failures.data, protocols: protocols.data, reports: reports.data, relationships: relationships.data, memoryItems: memoryItems.data, episodes: episodes.data, memoryEvents: memoryEvents.data, memoryHealth: memoryHealth.data, cognitiveState: cognitiveState.data })}
    </div>`;

  root.querySelectorAll("[data-brain-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.brainTab;
      renderBrainView({ root });
    });
  });
}
