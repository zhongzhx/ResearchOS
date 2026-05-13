import { getHealth, getLlmSettings, getResolverHealth, getRuntimeStatus, getSchedulerStatus, saveLlmSettings, testLlmSettings } from "../api.js";
import { appState } from "../state.js";
import { apiErrorCard, badge, escapeHtml, itemCard, metricCards, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

function runtimeSection(health, runtime, scheduler) {
  return `<div class="grid">
    ${metricCards([
      { label: "Health", value: health.ok ? "online" : "offline" },
      { label: "Runtime", value: runtime.ok ? "ready" : "missing" },
      { label: "Scheduler", value: scheduler.ok && scheduler.data.enabled ? "enabled" : "idle" },
    ])}
    <div class="grid three">
      ${itemCard({ title: "HTTP service", subtitle: health.ok ? "ResearchOS API responded to /health." : health.error, status: health.ok ? "ok" : "error" })}
      ${itemCard({ title: "Runtime status", subtitle: runtime.ok ? text(runtime.data.status || runtime.data.runtime_status || "Available") : runtime.error, status: runtime.ok ? "ok" : "error" })}
      ${itemCard({ title: "Scheduler", subtitle: scheduler.ok ? JSON.stringify(scheduler.data.last_run || {}) : scheduler.error, status: scheduler.ok ? "ok" : "error" })}
    </div>
  </div>`;
}

function dualAgentSection(resolver, demoAvailable) {
  const disabled = resolver.error === "dual_agent_api_disabled";
  return `<div class="grid">
    <div class="badge-row">
      ${badge(disabled ? "RESEARCHOS_DUAL_AGENT_API_ENABLED=false" : "Dual Agent API enabled", disabled ? "warning" : "success")}
      ${badge(demoAvailable ? "Demo endpoint available" : "Demo endpoint gated", demoAvailable ? "success" : "muted")}
    </div>
    ${disabled ? emptyState("Dual Agent API disabled", "Set RESEARCHOS_DUAL_AGENT_API_ENABLED=true before launching the local client to enable coordinator, resolver, catalog, pipeline, and pending skill APIs.") : jsonDetails("Resolver status", resolver.data || resolver, true)}
  </div>`;
}

function llmSettingsSection(settings) {
  const available = settings.ok;
  const data = settings.data || {};
  return `<div class="grid">
    ${available ? "" : emptyState("Backend settings API not available yet", "The API key form is disabled until GET/POST /api/settings/llm and /test are implemented on the backend.")}
    <form class="form-grid" id="llmForm">
      <div class="form-row">
        <label for="llmMode">Mode</label>
        <select class="field" id="llmMode" ${available ? "" : "disabled"}>
          <option>Single key for both agents</option>
          <option>Separate keys for Brain Agent and Execution Agent</option>
          <option>ResearchOS subscription</option>
        </select>
      </div>
      <div class="form-row">
        <label for="llmProvider">Provider</label>
        <input class="field" id="llmProvider" value="${escapeHtml(data.provider || "")}" placeholder="OpenAI compatible" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmModel">Model</label>
        <input class="field" id="llmModel" value="${escapeHtml(data.model || "")}" placeholder="model name" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmBaseUrl">Base URL</label>
        <input class="field" id="llmBaseUrl" value="${escapeHtml(data.base_url || "")}" placeholder="https://api.openai.com/v1" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row full-span">
        <label for="llmApiKey">API Key</label>
        <input class="field" id="llmApiKey" type="password" autocomplete="off" placeholder="${escapeHtml(data.masked_key || "API key")}" ${available ? "" : "disabled"} />
      </div>
      <div class="inline-actions full-span">
        <button class="button secondary" type="button" id="testLlm" ${available ? "" : "disabled"}>Test connection</button>
        <button class="button primary" type="submit" ${available ? "" : "disabled"}>Save</button>
      </div>
    </form>
  </div>`;
}

export async function renderSettingsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">Settings</h1><p class="page-subtitle">Runtime status, Dual Agent availability, resolver health, scheduler state, and LLM provider settings.</p></div>
    </header>
    <div class="page-scroll"><div class="grid" id="settingsContent">${emptyState("Loading settings", "Checking local runtime and settings endpoints.")}</div></div>
  </section>`;

  const [health, runtime, scheduler, resolver, llm] = await Promise.all([
    getHealth(),
    getRuntimeStatus(appState.activeProjectId),
    getSchedulerStatus(appState.activeProjectId),
    getResolverHealth(),
    getLlmSettings(),
  ]);
  root.querySelector("#settingsContent").innerHTML = `
    <div class="panel pad"><h2 class="item-title">Runtime Status</h2>${runtimeSection(health, runtime, scheduler)}</div>
    <div class="panel pad"><h2 class="item-title">Dual Agent</h2>${dualAgentSection(resolver, resolver.ok)}</div>
    <div class="panel pad"><h2 class="item-title">LLM Provider / API Settings</h2>${llmSettingsSection(llm)}</div>
    <div class="panel pad"><h2 class="item-title">Diagnostics</h2>${health.ok ? jsonDetails("Raw runtime payload", { health: health.data, runtime: runtime.data, scheduler: scheduler.data }) : apiErrorCard(health, "Backend unavailable")}</div>
  `;

  const form = root.querySelector("#llmForm");
  if (form && llm.ok) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = {
        mode: root.querySelector("#llmMode").value,
        provider: root.querySelector("#llmProvider").value,
        model: root.querySelector("#llmModel").value,
        base_url: root.querySelector("#llmBaseUrl").value,
        api_key: root.querySelector("#llmApiKey").value,
      };
      const result = await saveLlmSettings(payload);
      root.querySelector("#llmApiKey").value = "";
      alert(result.ok ? "Settings saved." : `Save failed: ${result.error}`);
    });
    root.querySelector("#testLlm").addEventListener("click", async () => {
      const result = await testLlmSettings({
        provider: root.querySelector("#llmProvider").value,
        model: root.querySelector("#llmModel").value,
        base_url: root.querySelector("#llmBaseUrl").value,
        api_key: root.querySelector("#llmApiKey").value,
      });
      alert(result.ok ? "Connection test succeeded." : `Connection test failed: ${result.error}`);
    });
  }
}
