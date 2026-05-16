import {
  activatePendingSkill,
  getPendingSkills,
  getProductFeatures,
  getResolverHealth,
  getSkillCatalog,
  getSkillPipelines,
  rejectPendingSkill,
  routeSkillQuery,
} from "../api.js";
import { appState, setPendingSkills, setResolverHealth } from "../state.js";
import { apiErrorCard, badge, escapeHtml, firstArray, itemCard } from "../components/cards.js";
import { emptyState } from "../components/empty_state.js";
import { featureStatusRow } from "../features/feature_status.js";
import { jsonDetails, jsonViewer } from "../components/json_viewer.js";

let activeTab = "目录";
let routeResult = null;
let filter = "";
const tabs = ["功能流程", "目录", "流程", "路由测试", "待处理技能", "解析器健康"];

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
  if (disabled(result)) return emptyState("双 Agent API 未启用", "设置 RESEARCHOS_DUAL_AGENT_API_ENABLED=true 后可以查看目录和路由接口。");
  if (!result.ok) return apiErrorCard(result, "技能目录不可用");
  const rows = filtered(firstArray(result.data, ["skills"]));
  if (!rows.length) return emptyState("没有匹配技能", "请尝试其他分类、状态或技能 id。");
  return `<div class="list">${rows
    .slice(0, 120)
    .map((skill) =>
      itemCard({
        title: skill.skill_id || skill.name,
        subtitle: skill.canonical_path || skill.path || "暂无标准路径记录",
        status: skill.status || skill.category || "目录",
        meta: [
          skill.category,
          skill.allowed_auto_call === false ? { label: "需手动", tone: "warning" } : { label: "可自动调用", tone: "success" },
          skill.requires_user_authorization ? { label: "需授权", tone: "warning" } : "",
        ].filter(Boolean),
      }),
    )
    .join("")}</div>`;
}

function productFlowsView(result) {
  if (!result.ok) return apiErrorCard(result, "产品功能状态不可用");
  const rows = filtered(firstArray(result.data, ["features"]));
  if (!rows.length) return emptyState("没有匹配功能流程", "请尝试其他功能、流程或状态。");
  return `<div class="list">${rows.map((feature) => featureStatusRow(feature) + jsonDetails("功能契约", feature)).join("")}</div>`;
}

function pipelinesView(result) {
  if (disabled(result)) return emptyState("双 Agent API 未启用", "流程注册表由受控的双 Agent API 提供。");
  if (!result.ok) return apiErrorCard(result, "流程注册表不可用");
  const rows = filtered(firstArray(result.data, ["pipelines"]));
  if (!rows.length) return emptyState("没有匹配流程", "流程注册表没有返回符合当前过滤条件的记录。");
  return `<div class="list">${rows
    .map((pipeline) =>
      itemCard({
        title: pipeline.pipeline_name || pipeline.intent,
        subtitle: `意图：${pipeline.intent || "未设置"}`,
        status: pipeline.requires_user_authorization ? "需要授权" : "就绪",
        meta: [
          `技能：${(pipeline.execution_skills || []).length}`,
          `校验：${(pipeline.validation_rules || []).length}`,
          `入库：${(pipeline.promotion_targets || []).length}`,
        ],
      }) + jsonDetails("流程详情", pipeline)
    )
    .join("")}</div>`;
}

function routeTester() {
  return `<div class="grid">
    <div class="form-row">
      <label for="routeQuery">自然语言请求</label>
      <input class="text-input" id="routeQuery" lang="zh-CN" placeholder="收集巨噬细胞先天免疫相关论文" />
    </div>
    <div><button class="button primary" type="button" id="routeButton">测试路由</button></div>
    ${routeResult ? jsonViewer(routeResult) : emptyState("暂无路由测试", "输入请求后可以查看选择的流程、匹配技能和授权需求。")}
  </div>`;
}

function pendingView(result) {
  if (disabled(result)) return emptyState("双 Agent API 未启用", "生成技能的待复核列表会保持受控，直到显式启用 API。");
  if (!result.ok) return apiErrorCard(result, "待处理技能不可用");
  const rows = firstArray({ pending: result.data }, ["pending"]);
  if (!rows.length) return emptyState("暂无待处理技能", "等待复核的生成技能会显示在这里。");
  return `<div class="list">${rows
    .map((skill) => `<article class="item-card">
      <h3 class="item-title">${escapeHtml(skill.name || skill.skill_id || "生成技能")}</h3>
      <p class="item-subtitle">${escapeHtml(skill.description || skill.skill_dir || "等待复核批准")}</p>
      <div class="badge-row">${badge("等待复核", "warning")}${badge("不可自动执行", "muted")}</div>
      <div class="inline-actions">
        <button class="button secondary small" type="button" data-activate-skill="${escapeHtml(skill.name)}">启用</button>
        <button class="button danger small" type="button" data-reject-skill="${escapeHtml(skill.name)}">拒绝</button>
      </div>
    </article>`)
    .join("")}</div>`;
}

function resolverView(result) {
  if (disabled(result)) return emptyState("双 Agent API 未启用", "解析器健康检查需要受控的双 Agent API。");
  if (!result.ok) return apiErrorCard(result, "解析器健康不可用");
  return `<div class="grid">
    ${itemCard({ title: "解析器条目", subtitle: result.data.resolver_entries ?? "暂无数据", status: "checked" })}
    ${itemCard({ title: "重复触发词", subtitle: JSON.stringify(result.data.duplicate_triggers || []), status: (result.data.duplicate_triggers || []).length ? "warning" : "ok" })}
    ${itemCard({ title: "不可达技能", subtitle: JSON.stringify(result.data.unreachable_skills || []), status: (result.data.unreachable_skills || []).length ? "warning" : "ok" })}
    ${itemCard({ title: "缺失标准路径", subtitle: JSON.stringify(result.data.missing_canonical_paths || []), status: (result.data.missing_canonical_paths || []).length ? "warning" : "ok" })}
    ${jsonDetails("解析器健康原始数据", result.data, true)}
  </div>`;
}

export async function renderSkillsView({ root }) {
  root.innerHTML = `<section class="page">
    <header class="page-header">
      <div><h1 class="page-title">技能 / 流程</h1><p class="page-subtitle">目录、流程注册表、路由测试、待处理生成技能和解析器健康。</p></div>
      <input class="search-input" id="skillFilter" lang="zh-CN" value="${escapeHtml(filter)}" placeholder="过滤技能或流程..." />
    </header>
    <div class="page-scroll"><div class="panel pad" id="skillsContent">${emptyState("正在加载技能", "正在读取目录、流程、待处理技能和解析器健康。")}</div></div>
  </section>`;

  const [features, catalog, pipelines, pending, resolver] = await Promise.all([getProductFeatures(), getSkillCatalog(), getSkillPipelines(), getPendingSkills(), getResolverHealth()]);
  if (pending.ok) setPendingSkills(pending.data);
  setResolverHealth(resolver.ok ? { ok: true, ...resolver.data } : { ok: false, error: resolver.error, status: resolver.status });
  const views = {
    功能流程: productFlowsView(features),
    目录: catalogView(catalog),
    流程: pipelinesView(pipelines),
    路由测试: routeTester(),
    待处理技能: pendingView(pending),
    解析器健康: resolverView(resolver),
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
      if (!confirm(`确定启用生成技能“${name}”吗？`)) return;
      await activatePendingSkill(name);
      renderSkillsView({ root });
    });
  });
  root.querySelectorAll("[data-reject-skill]").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = button.dataset.rejectSkill;
      const reason = prompt(`请输入拒绝“${name}”的原因：`);
      if (!reason) return;
      await rejectPendingSkill(name, reason);
      renderSkillsView({ root });
    });
  });
}
