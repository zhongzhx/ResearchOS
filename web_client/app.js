const state = {
  projects: [],
  activeProjectId: "",
  conversationId: localStorage.getItem("auraConversationId") || "",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const response = await fetch(`/api/backend${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function clean(value, fallback = "") {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function setRoute(route) {
  $$(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.route === route));
  $$(".view").forEach((view) => view.classList.toggle("is-active", view.dataset.view === route));
  if (route === "tasks") loadTasks();
  if (route === "library") loadLibrary();
  if (route === "memory") loadMemory();
  if (route === "settings") loadStatus();
}

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  $("#chatLog").appendChild(node);
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
}

function row(title, subtitle, meta = "") {
  const node = document.createElement("article");
  node.className = "row";
  node.innerHTML = `
    <strong></strong>
    <span></span>
    ${meta ? '<span class="meta"></span>' : ""}
  `;
  node.querySelector("strong").textContent = title;
  node.querySelector("span").textContent = subtitle;
  const metaNode = node.querySelector(".meta");
  if (metaNode) metaNode.textContent = meta;
  return node;
}

function renderEmpty(target, title, subtitle) {
  target.replaceChildren(row(title, subtitle));
}

async function loadStatus() {
  const dot = $("#statusDot");
  const label = $("#statusText");
  try {
    const health = await api("/health");
    dot.classList.add("ok");
    label.textContent = "已连接";
    $("#statusGrid").replaceChildren(
      row("本地服务", "ResearchOS API 正常响应", clean(health.status, "ok")),
      row("数据目录", clean(health.agent_root || health.state_db || "已配置")),
    );
  } catch (error) {
    dot.classList.remove("ok");
    label.textContent = "未连接";
    $("#statusGrid").replaceChildren(row("连接失败", error.message));
  }
}

async function loadProjects() {
  try {
    const payload = await api("/research-os/projects");
    state.projects = payload.projects || [];
    state.activeProjectId = clean(state.projects[0]?.id || state.projects[0]?.project_id);
    $("#projectHint").textContent = state.projects[0]
      ? `当前项目：${clean(state.projects[0].title || state.projects[0].name, "未命名项目")}`
      : "还没有项目，AURA 会先按你的问题工作";
  } catch {
    $("#projectHint").textContent = "后端连接中";
  }
}

async function loadTasks() {
  const target = $("#taskList");
  try {
    const payload = await api(`/research-os/tasks${state.activeProjectId ? `?project_id=${encodeURIComponent(state.activeProjectId)}` : ""}`);
    const tasks = payload.tasks || payload.agent_tasks || [];
    if (!tasks.length) {
      renderEmpty(target, "暂无任务", "发送一个需要执行的科研请求后，任务会出现在这里。");
      return;
    }
    target.replaceChildren(
      ...tasks.slice(0, 18).map((task) =>
        row(
          clean(task.title || task.type || task.task_type, "科研任务"),
          clean(task.summary || task.message || task.current_stage || task.task_id, "等待后端更新"),
          clean(task.status, "pending"),
        ),
      ),
    );
  } catch (error) {
    renderEmpty(target, "任务读取失败", error.message);
  }
}

async function loadLibrary() {
  const target = $("#libraryList");
  try {
    const payload = await api(`/research-os/references${state.activeProjectId ? `?project_id=${encodeURIComponent(state.activeProjectId)}` : ""}`);
    const refs = payload.references || [];
    if (!refs.length) {
      renderEmpty(target, "资料库为空", "导入 PDF 或启动文献采集后，文献会出现在这里。");
      return;
    }
    target.replaceChildren(
      ...refs.slice(0, 18).map((ref) =>
        row(
          clean(ref.title || ref.name, "未命名文献"),
          clean(ref.authors || ref.source || ref.path, "未记录来源"),
          clean(ref.status || ref.provider),
        ),
      ),
    );
  } catch (error) {
    renderEmpty(target, "资料库读取失败", error.message);
  }
}

async function loadMemory() {
  const target = $("#memoryText");
  if (!state.activeProjectId) {
    target.textContent = "还没有选中的项目。";
    return;
  }
  try {
    const payload = await api(`/research-os/memory/context?project_id=${encodeURIComponent(state.activeProjectId)}&query=${encodeURIComponent("当前项目摘要")}`);
    target.textContent = clean(payload.summary || payload.context || payload.memory_context || JSON.stringify(payload, null, 2), "暂无项目记忆。");
  } catch (error) {
    target.textContent = `项目记忆读取失败：${error.message}`;
  }
}

async function sendPrompt(source) {
  const prompt = source.value.trim();
  if (!prompt) return;
  source.value = "";
  addMessage("user", prompt);
  setRoute("home");
  try {
    const payload = await api("/research-os/agent/chat", {
      method: "POST",
      body: JSON.stringify({
        message: prompt,
        project_id: state.activeProjectId,
        conversation_id: state.conversationId,
      }),
    });
    if (payload.conversation_id) {
      state.conversationId = payload.conversation_id;
      localStorage.setItem("auraConversationId", state.conversationId);
    }
    addMessage("assistant", clean(payload.answer || payload.summary || payload.message, "AURA 已返回结果。"));
    loadTasks();
  } catch (error) {
    addMessage("assistant", `请求失败：${error.message}`);
  }
}

function bindEvents() {
  $$("[data-route]").forEach((item) => item.addEventListener("click", () => setRoute(item.dataset.route)));
  $("#sendHome").addEventListener("click", () => sendPrompt($("#homePrompt")));
  $("#homePrompt").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) sendPrompt($("#homePrompt"));
  });
  $("#refreshTasks").addEventListener("click", loadTasks);
  $("#refreshLibrary").addEventListener("click", loadLibrary);
  $("#refreshMemory").addEventListener("click", loadMemory);
  $("#refreshStatus").addEventListener("click", loadStatus);
}

async function boot() {
  bindEvents();
  addMessage("assistant", "AURA 已准备好。首页只保留对话框，其他内容在左侧分区查看。");
  await loadStatus();
  await loadProjects();
}

boot();
