import { getHealth, getLlmSettings, getResolverHealth, getRuntimeStatus, getSchedulerStatus, saveLlmSettings, testLlmSettings } from "../api.js";
import { appState, setDeveloperMode } from "../state.js";
import { apiErrorCard, badge, escapeHtml, itemCard, metricCards, text } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { jsonDetails } from "../components/json_viewer.js";

function runtimeSection(health, runtime, scheduler) {
  return `<div class="grid">
    ${metricCards([
      { label: "健康状态", value: health.ok ? "在线" : "离线" },
      { label: "运行时", value: runtime.ok ? "就绪" : "缺失" },
      { label: "调度器", value: scheduler.ok && scheduler.data.enabled ? "已启用" : "空闲" },
    ])}
    <div class="grid three">
      ${itemCard({ title: "HTTP 服务", subtitle: health.ok ? "ResearchOS API 已响应 /health。" : health.error, status: health.ok ? "ok" : "error" })}
      ${itemCard({ title: "运行状态", subtitle: runtime.ok ? text(runtime.data.status || runtime.data.runtime_status || "可用") : runtime.error, status: runtime.ok ? "ok" : "error" })}
      ${itemCard({ title: "调度器", subtitle: scheduler.ok ? JSON.stringify(scheduler.data.last_run || {}) : scheduler.error, status: scheduler.ok ? "ok" : "error" })}
    </div>
  </div>`;
}

function dualAgentSection(resolver, demoAvailable) {
  const disabled = resolver.error === "dual_agent_api_disabled";
  return `<div class="grid">
    <div class="badge-row">
      ${badge(disabled ? "RESEARCHOS_DUAL_AGENT_API_ENABLED=false" : "双 Agent API 已启用", disabled ? "warning" : "success")}
      ${badge(demoAvailable ? "演示接口可用" : "演示接口受限", demoAvailable ? "success" : "muted")}
    </div>
    ${disabled ? emptyState("双 Agent API 未启用", "启动本地客户端前设置 RESEARCHOS_DUAL_AGENT_API_ENABLED=true，即可启用协调器、解析器、目录、流程和待处理技能接口。") : jsonDetails("解析器状态", resolver.data || resolver)}
  </div>`;
}

function llmSettingsSection(settings) {
  const available = settings.ok;
  const data = settings.data || {};
  const mode = data.mode || data.settings?.mode || "single_key";
  return `<div class="grid">
    ${available ? "" : emptyState("后端设置接口暂时不可用", "在后端实现 GET/POST /api/settings/llm 和 /test 之前，API key 表单会保持禁用。")}
    <form class="form-grid" id="llmForm">
      <div class="form-row">
        <label for="llmMode">模式</label>
        <select class="field" id="llmMode" ${available ? "" : "disabled"}>
          <option value="single_key" ${mode === "single_key" ? "selected" : ""}>两个 Agent 共用一个 key</option>
          <option value="separate_keys" ${mode === "separate_keys" ? "selected" : ""}>研究大脑和执行 Agent 分别使用 key</option>
          <option value="subscription" ${mode === "subscription" ? "selected" : ""}>ResearchOS 订阅</option>
        </select>
      </div>
      <div class="form-row">
        <label for="llmProvider">研究大脑服务商</label>
        <input class="field" id="llmProvider" lang="zh-CN" value="${escapeHtml(data.brain_provider || data.provider || "")}" placeholder="OpenAI 兼容接口" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmModel">研究大脑模型</label>
        <input class="field" id="llmModel" lang="zh-CN" value="${escapeHtml(data.brain_model || data.model || "")}" placeholder="模型名称" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmBaseUrl">研究大脑 Base URL</label>
        <input class="field" id="llmBaseUrl" lang="zh-CN" value="${escapeHtml(data.brain_base_url || data.base_url || "")}" placeholder="https://api.openai.com/v1" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionProvider">执行 Agent 服务商</label>
        <input class="field" id="executionProvider" lang="zh-CN" value="${escapeHtml(data.execution_provider || data.brain_provider || data.provider || "")}" placeholder="OpenAI 兼容接口" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionModel">执行 Agent 模型</label>
        <input class="field" id="executionModel" lang="zh-CN" value="${escapeHtml(data.execution_model || data.brain_model || data.model || "")}" placeholder="模型名称" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionBaseUrl">执行 Agent Base URL</label>
        <input class="field" id="executionBaseUrl" lang="zh-CN" value="${escapeHtml(data.execution_base_url || data.brain_base_url || data.base_url || "")}" placeholder="https://api.openai.com/v1" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="llmApiKey">研究大脑 API key</label>
        <input class="field" id="llmApiKey" lang="zh-CN" type="password" autocomplete="off" placeholder="${escapeHtml(data.brain_api_key_masked || data.masked_key || "API key")}" ${available ? "" : "disabled"} />
      </div>
      <div class="form-row">
        <label for="executionApiKey">执行 Agent API key</label>
        <input class="field" id="executionApiKey" lang="zh-CN" type="password" autocomplete="off" placeholder="${escapeHtml(data.execution_api_key_masked || data.brain_api_key_masked || "API key")}" ${available ? "" : "disabled"} />
      </div>
      <div class="inline-actions full-span">
        <button class="button secondary" type="button" id="testLlm" ${available ? "" : "disabled"}>测试连接</button>
        <button class="button primary" type="submit" ${available ? "" : "disabled"}>保存</button>
        <button class="button danger" type="button" id="clearKeys" ${available ? "" : "disabled"}>清除 key</button>
      </div>
    </form>
    <div class="badge-row">
      ${badge(`研究大脑 key：${data.brain_api_key_masked || data.masked_key || "未配置"}`, data.brain_api_key_masked || data.masked_key ? "success" : "warning")}
      ${badge(`执行 key：${data.execution_api_key_masked || "未配置"}`, data.execution_api_key_masked ? "success" : "warning")}
      ${badge(`订阅：${data.subscription_status || "未配置"}`)}
    </div>
  </div>`;
}

function preferenceSection() {
  return `<div class="grid">
    <label class="check-row"><input id="developerModeToggle" type="checkbox" ${appState.developerMode ? "checked" : ""} /> 开发者模式</label>
    <p class="muted">开启后会显示任务调试、研究记忆、技能目录、运行记录和 API 诊断页面。</p>
  </div>`;
}

export async function renderSettingsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">设置</h1><p class="page-subtitle">管理 AURA Research 的本地偏好和模型连接。</p></div>
    </header>
    <div class="page-scroll"><div class="grid" id="settingsContent">${emptyState("正在加载设置", "正在检查本地运行时和设置接口。")}</div></div>
  </section>`;

  const [health, runtime, scheduler, resolver, llm] = await Promise.all([
    getHealth(),
    getRuntimeStatus(appState.activeProjectId),
    getSchedulerStatus(appState.activeProjectId),
    getResolverHealth(),
    getLlmSettings(),
  ]);
  root.querySelector("#settingsContent").innerHTML = `
    <div class="panel pad"><h2 class="item-title">LLM 服务 / API 设置</h2>${llmSettingsSection(llm)}</div>
    <div class="panel pad"><h2 class="item-title">偏好</h2>${preferenceSection()}</div>
    ${
      appState.developerMode
        ? `<div class="panel pad"><h2 class="item-title">运行状态</h2>${runtimeSection(health, runtime, scheduler)}</div>
          <div class="panel pad"><h2 class="item-title">API / Resolver 诊断</h2>${dualAgentSection(resolver, resolver.ok)}</div>
          <div class="panel pad"><h2 class="item-title">诊断</h2>${health.ok ? jsonDetails("运行时原始数据", { health: health.data, runtime: runtime.data, scheduler: scheduler.data }) : apiErrorCard(health, "服务不可用")}</div>`
        : ""
    }
  `;

  root.querySelector("#developerModeToggle")?.addEventListener("change", (event) => {
    setDeveloperMode(event.target.checked);
    window.dispatchEvent(new CustomEvent("researchos:refresh-navigation"));
    renderSettingsView({ root });
  });

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
      alert(result.ok ? "设置已保存。" : `保存失败：${result.error}`);
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
      alert(result.ok ? "连接测试成功。" : `连接测试失败：${result.error}`);
    });
    root.querySelector("#clearKeys").addEventListener("click", async () => {
      if (!confirm("确定清除已保存的研究大脑和执行 Agent API key 吗？")) return;
      const result = await saveLlmSettings({ mode: root.querySelector("#llmMode").value, clear_brain_api_key: true, clear_execution_api_key: true });
      alert(result.ok ? "Key 已清除。" : `清除失败：${result.error}`);
      renderSettingsView({ root });
    });
  }
}
