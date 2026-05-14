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
  const mode = data.mode || data.settings?.mode || "single_key";
  return `<div class="grid">
    ${available ? "" : emptyState("Backend settings API not available yet", "The API key form is disabled until GET/POST /api/settings/llm and /test are implemented on the backend.")}
    <form class="form-grid" id="llmForm">
      <div class="form-row">
        <label for="llmMode">Mode</label>
        <select class="field" id="llmMode" ${available ? "" : "disabled"}>
          <option value="single_key" ${mode === "single_key" ? "selected" : ""}>Single key for both agents</option>
          <option value="separate_keys" ${mode === "separate_keys" ? "selected" : ""}>Separate keys for Brain Agent and Execution Agent</option>
          <option value="subscription" ${mode === "subscription" ? "selected" : ""}>ResearchOS subscription</option>
        </select>
      </div>
      <div class="form-row">
        <label for="llmProvider">Brain Agent provider</label>
        <input class="field" id="llmProvider" value="${escapeHtml(data.brain_provider || data.provider || "")}" placeholder="OpenAI compatible" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmModel">Brain Agent model</label>
        <input class="field" id="llmModel" value="${escapeHtml(data.brain_model || data.model || "")}" placeholder="model name" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmBaseUrl">Brain Agent Base URL</label>
        <input class="field" id="llmBaseUrl" value="${escapeHtml(data.brain_base_url || data.base_url || "")}" placeholder="https://api.openai.com/v1" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionProvider">Execution Agent provider</label>
        <input class="field" id="executionProvider" value="${escapeHtml(data.execution_provider || data.brain_provider || data.provider || "")}" placeholder="OpenAI compatible" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionModel">Execution Agent model</label>
        <input class="field" id="executionModel" value="${escapeHtml(data.execution_model || data.brain_model || data.model || "")}" placeholder="model name" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionBaseUrl">Execution Agent Base URL</label>
        <input class="field" id="executionBaseUrl" value="${escapeHtml(data.execution_base_url || data.brain_base_url || data.base_url || "")}" placeholder="https://api.openai.com/v1" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmApiKey">Brain Agent API key</label>
        <input class="field" id="llmApiKey" type="password" autocomplete="off" placeholder="${escapeHtml(data.brain_api_key_masked || data.masked_key || "API key")}" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionApiKey">Execution Agent API key</label>
        <input class="field" id="executionApiKey" type="password" autocomplete="off" placeholder="${escapeHtml(data.execution_api_key_masked || data.brain_api_key_masked || "API key")}" ${available ? "" : "disabled"} />
      </div>
      <div class="inline-actions full-span">
        <button class="button secondary" type="button" id="testLlm" ${available ? "" : "disabled"}>Test connection</button>
        <button class="button primary" type="submit" ${available ? "" : "disabled"}>Save</button>
        <button class="button danger" type="button" id="clearKeys" ${available ? "" : "disabled"}>Clear keys</button>
      </div>
    </form>
    <div class="badge-row">
      ${badge(`Brain key: ${data.brain_api_key_masked || data.masked_key || "not configured"}`, data.brain_api_key_masked || data.masked_key ? "success" : "warning")}
      ${badge(`Execution key: ${data.execution_api_key_masked || "not configured"}`, data.execution_api_key_masked ? "success" : "warning")}
      ${badge(`Subscription: ${data.subscription_status || "not_configured"}`)}
    </div>
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
        brain_provider: root.querySelector("#llmProvider").value,
        brain_model: root.querySelector("#llmModel").value,
        brain_base_url: root.querySelector("#llmBaseUrl").value,
        brain_api_key: root.querySelector("#llmApiKey").value,
        execution_provider: root.querySelector("#executionProvider").value,
        execution_model: root.querySelector("#executionModel").value,
        execution_base_url: root.querySelector("#executionBaseUrl").value,
        execution_api_key: root.querySelector("#executionApiKey").value,
      };
      const result = await saveLlmSettings(payload);
      root.querySelector("#llmApiKey").value = "";
      root.querySelector("#executionApiKey").value = "";
      alert(result.ok ? "Settings saved." : `Save failed: ${result.error}`);
    });
    root.querySelector("#testLlm").addEventListener("click", async () => {
      const apiKey = root.querySelector("#llmApiKey").value;
      const result = await testLlmSettings({
        brain_provider: root.querySelector("#llmProvider").value,
        brain_model: root.querySelector("#llmModel").value,
        brain_base_url: root.querySelector("#llmBaseUrl").value,
        brain_api_key: apiKey,
        use_configured_key: !apiKey,
      });
      alert(result.ok ? "Connection test succeeded." : `Connection test failed: ${result.error}`);
    });
    root.querySelector("#clearKeys").addEventListener("click", async () => {
      if (!confirm("Clear saved Brain and Execution API keys?")) return;
      const result = await saveLlmSettings({ mode: root.querySelector("#llmMode").value, clear_brain_api_key: true, clear_execution_api_key: true });
      alert(result.ok ? "Keys cleared." : `Clear failed: ${result.error}`);
      renderSettingsView({ root });
    });
  }
}
