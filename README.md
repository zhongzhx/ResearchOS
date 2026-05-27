# ResearchOS

ResearchOS 是面向湿实验科研人员的本地双智能体研究工作空间。它结合了基于标准库的 HTTP 后端、Research Brain 记忆系统、执行技能、文献/证据工具以及 Electron 桌面客户端。

## 项目结构

```text
.
├── backend/                         # 双智能体协作、技能路由、Brain 与执行适配器
├── skills/researchos_skill_library/ # 标准 ResearchOS 技能、目录、流水线与解析数据
├── electron/                        # 本地桌面外壳与后端代理
├── web_client/                      # 原生 HTML/CSS/JS 客户端
├── scripts/check_web_client.py      # 客户端静态冒烟检查
├── run_researchos_local_api.ps1     # 本地 API 启动脚本
├── run_researchos_local_api.cmd     # Windows 启动脚本
└── tests/                           # 后端、技能、API 与客户端测试
```

## 本地桌面客户端

启动本地客户端：

```powershell
npm run client:electron
```

Electron 会打开本地 `web_client/` 界面、提供静态资源、在需要时启动 ResearchOS HTTP API，并通过 `/api/backend/*` 代理浏览器请求。

默认运行参数：

- API: `http://127.0.0.1:8765`
- 智能体数据：`agent_data/`
- 重要环境变量：`RESEARCHOS_HOST`、`RESEARCHOS_PORT`、`RESEARCHOS_AGENT_ROOT`、`RESEARCHOS_DUAL_AGENT_API_ENABLED`

Electron 启动器会默认为桌面客户端设置 `RESEARCHOS_DUAL_AGENT_API_ENABLED=true`。如果手动启动后端且未设置该标志，受限的 `/api/...` 双智能体端点会返回：

```json
{"ok": false, "error": "dual_agent_api_disabled"}
```

旧版聊天路由仍然可用：

```text
POST /research-os/agent/chat
```

## 客户端页面

桌面工作空间包含以下页面：

- 对话（Chat）
- 任务生命周期（Task Lifecycle）
- Research Brain
- 文献库 / 证据（Library / Evidence）
- 技能 / 流水线（Skills / Pipelines）
- 运行 / 执行（Runs / Execution）
- 设置（Settings）

客户端有意采用原生 HTML/CSS/JS。API 调用位于 `web_client/api.js`，共享状态位于 `web_client/state.js`，视图位于 `web_client/views/`，可复用的 UI 片段位于 `web_client/components/`。

## 关键 API

双智能体 API 需要启用 `RESEARCHOS_DUAL_AGENT_API_ENABLED=true`：

- `POST /api/agents/coordinator/run`
- `POST /api/brain/skillrun/{skillrun_id}/process`
- `GET /api/self-evolution/pending-skills`
- `POST /api/self-evolution/skills/{skill_name}/activate`
- `POST /api/self-evolution/skills/{skill_name}/reject`
- `GET /api/skills/resolver/check`
- `GET /api/skills/catalog`
- `GET /api/skills/pipelines`
- `POST /api/skills/route`
- `GET /api/demo/dual-agent`

客户端使用的 ResearchOS 核心 API 位于 `/research-os/...` 下，涵盖项目、任务、记忆、主张、协议、报告、引用、文件、SkillRun、执行记忆、调度器和工作流看板等端点。

## 检查与测试

运行针对客户端的测试：

```powershell
py -m unittest tests.test_researchos_web_client tests.test_research_agent_api_dual_agent_gate -v
```

运行客户端静态检查：

```powershell
npm run client:check
```

运行 Electron 冒烟测试：

```powershell
npm run client:electron:smoke
```

运行更完整的后端测试：

```powershell
py -m unittest discover -s tests -p "test_*.py"
$env:LLM_PROVIDER='mock'; py -m unittest discover -s backend\research_agent_runtime\scripts\tests -p "test_research_os_mvp.py"
```

## 本地数据

仓库只应保留代码、技能定义、测试和必要资源。本地运行数据不应被版本控制跟踪：

- `.env`
- `.tmp/`
- `agent_data/`
- `data/`
- `generated_outputs/`
- `runtime/`
- 本地 PDF、Office 文档、数据库、日志、缓存以及生成的研究输出

## 许可证

本仓库中的 ResearchOS 原始源代码和文档基于 [Apache License 2.0](LICENSE) 许可发布。

包括 `opendataloader-pdf/` 在内的第三方或随附组件，仍受其自身分发的许可证与署名文件约束。
