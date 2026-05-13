import {
  activatePendingSkill,
  getPendingSkills,
  getResolverHealth,
  getSkillCatalog,
  getSkillPipelines,
  rejectPendingSkill,
  routeSkillQuery,
} from "../api.js";
import { appState, setPendingSkills, setResolverHealth } from "../state.js";
import { apiErrorCard, badge, escapeHtml, firstArray, itemCard } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

let activeTab = "Catalog";
let routeResult = null;
let filter = "";
const tabs = ["Catalog", "Pipelines", "Route Tester", "Pending Skills", "Resolver Health"];

function tabButtons() {
  return `<div class="tabs">${tabs.map((tab) => `<button class="tab ${tab === activeTab ? "is-active" : ""}" type="button" data-skills-tab="${tab}">${tab}</button>`).join("")}</div>`;
}

function disabled(result) {
  return result?.error === "dual_agent_api_disabled" || result?.status === 503;
}

function filtered(rows) {
  if (!filter) return rows;
  return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(filter.toLowerCase()));
}

function catalogView(result) {
  if (disabled(result)) return emptyState("Dual Agent API disabled", "Enable RESEARCHOS_DUAL_AGENT_API_ENABLED=true to inspect catalog and routing endpoints.");
  if (!result.ok) return apiErrorCard(result, "Skill catalog unavailable");
  const rows = filtered(firstArray(result.data, ["skills"]));
  if (!rows.length) return emptyState("No skills match", "Try a different category, status, or skill id.");
  return `<div class="list">${rows
    .slice(0, 120)
    .map((skill) =>
      itemCard({
        title: skill.skill_id || skill.name,
        subtitle: skill.canonical_path || skill.path || "No canonical path recorded",
        status: skill.status || skill.category || "catalog",
        meta: [
          skill.category,
          skill.allowed_auto_call === false ? { label: "manual", tone: "warning" } : { label: "auto-call ok", tone: "success" },
          skill.requires_user_authorization ? { label: "authorization", tone: "warning" } : "",
        ].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

function pipelinesView(result) {
  if (disabled(result)) return emptyState("Dual Agent API disabled", "Pipeline registry is served by the gated dual-agent API.");
  if (!result.ok) return apiErrorCard(result, "Pipeline registry unavailable");
  const rows = filtered(firstArray(result.data, ["pipelines"]));
  if (!rows.length) return emptyState("No pipelines match", "Pipeline registry returned no rows for this filter.");
  return `<div class="list">${rows
    .map((pipeline) =>
      itemCard({
        title: pipeline.pipeline_name || pipeline.intent,
        subtitle: `Intent: ${pipeline.intent || "not set"}`,
        status: pipeline.requires_user_authorization ? "authorization required" : "ready",
        meta: [
          `skills: ${(pipeline.execution_skills || []).length}`,
          `validation: ${(pipeline.validation_rules || []).length}`,
          `promotion: ${(pipeline.promotion_targets || []).length}`,
        ],
      }) + jsonDetails("Pipeline details", pipeline)
    )
    .join("")}</div>`;
}

function routeTester() {
  return `<div class="grid">
    <div class="form-row">
      <label for="routeQuery">Natural language query</label>
      <input class="text-input" id="routeQuery" placeholder="Collect papers about innate immunity in macrophages" />
    </div>
    <div><button class="button primary" type="button" id="routeButton">Route query</button></div>
    ${routeResult ? jsonViewer(routeResult) : emptyState("No route tested yet", "Enter a query to see selected pipeline, matched skills, and authorization needs.")}
  </div>`;
}

function pendingView(result) {
  if (disabled(result)) return emptyState("Dual Agent API disabled", "Pending generated skills remain gated until the API is explicitly enabled.");
  if (!result.ok) return apiErrorCard(result, "Pending skills unavailable");
  const rows = firstArray({ pending: result.data }, ["pending"]);
  if (!rows.length) return emptyState("No pending skills", "Generated skills awaiting review will appear here.");
  return `<div class="list">${rows
    .map((skill) => `<article class="item-card">
      <h3 class="item-title">${escapeHtml(skill.name || skill.skill_id || "Generated skill")}</h3>
      <p class="item-subtitle">${escapeHtml(skill.description || skill.skill_dir || "Pending reviewer approval")}</p>
      <div class="badge-row">${badge("pending_review", "warning")}${badge("not auto-executable", "muted")}</div>
      <div class="inline-actions">
        <button class="button secondary small" type="button" data-activate-skill="${escapeHtml(skill.name)}">Activate</button>
        <button class="button danger small" type="button" data-reject-skill="${escapeHtml(skill.name)}">Reject</button>
      </div>
    </article>`)
    .join("")}</div>`;
}

function resolverView(result) {
  if (disabled(result)) return emptyState("Dual Agent API disabled", "Resolver health requires the gated dual-agent API.");
  if (!result.ok) return apiErrorCard(result, "Resolver health unavailable");
  return `<div class="grid">
    ${itemCard({ title: "Resolver entries", subtitle: result.data.resolver_entries ?? "Not available yet", status: "checked" })}
    ${itemCard({ title: "Duplicate triggers", subtitle: JSON.stringify(result.data.duplicate_triggers || []), status: (result.data.duplicate_triggers || []).length ? "warning" : "ok" })}
    ${itemCard({ title: "Unreachable skills", subtitle: JSON.stringify(result.data.unreachable_skills || []), status: (result.data.unreachable_skills || []).length ? "warning" : "ok" })}
    ${itemCard({ title: "Missing canonical paths", subtitle: JSON.stringify(result.data.missing_canonical_paths || []), status: (result.data.missing_canonical_paths || []).length ? "warning" : "ok" })}
    ${jsonDetails("Raw resolver health", result.data, true)}
  </div>`;
}

export async function renderSkillsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">Skills / Pipelines</h1><p class="page-subtitle">Catalog, pipeline registry, route testing, pending generated skills, and resolver health.</p></div>
      <input class="search-input" id="skillFilter" value="${escapeHtml(filter)}" placeholder="Filter skills or pipelines..." />
    </header>
    <div class="page-scroll"><div class="panel pad" id="skillsContent">${emptyState("Loading skills", "Fetching catalog, pipelines, pending skills, and resolver health.")}</div></div>
  </section>`;

  const [catalog, pipelines, pending, resolver] = await Promise.all([getSkillCatalog(), getSkillPipelines(), getPendingSkills(), getResolverHealth()]);
  if (pending.ok) setPendingSkills(pending.data);
  setResolverHealth(resolver.ok ? { ok: true, ...resolver.data } : { ok: false, error: resolver.error, status: resolver.status });
  const views = {
    Catalog: catalogView(catalog),
    Pipelines: pipelinesView(pipelines),
    "Route Tester": routeTester(),
    "Pending Skills": pendingView(pending),
    "Resolver Health": resolverView(resolver),
  };
  root.querySelector("#skillsContent").innerHTML = `${tabButtons()}${views[activeTab]}`;

  root.querySelector("#skillFilter").addEventListener("input", (event) => {
    filter = event.target.value;
    renderSkillsView({ root });
  });
  root.querySelectorAll("[data-skills-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.skillsTab;
      renderSkillsView({ root });
    });
  });
  const routeButton = root.querySelector("#routeButton");
  if (routeButton) {
    routeButton.addEventListener("click", async () => {
      const query = root.querySelector("#routeQuery").value.trim();
      if (!query) return;
      routeResult = await routeSkillQuery(query, appState.activeProjectId);
      renderSkillsView({ root });
    });
  }
  root.querySelectorAll("[data-activate-skill]").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = button.dataset.activateSkill;
      if (!confirm(`Activate generated skill "${name}"?`)) return;
      await activatePendingSkill(name);
      renderSkillsView({ root });
    });
  });
  root.querySelectorAll("[data-reject-skill]").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = button.dataset.rejectSkill;
      const reason = prompt(`Reject "${name}" with reason:`);
      if (!reason) return;
      await rejectPendingSkill(name, reason);
      renderSkillsView({ root });
    });
  });
}
