# ResearchOS

ResearchOS 是一个面向科研工作流的本地双 Agent 系统。项目把后端调度、Research Brain 记忆、执行 Agent、技能库、文献获取能力和本地桌面客户端放在同一个仓库里，目标是让大模型在收到用户需求后，能够先理解任务意图，再按技能目录选择合适的 `SKILL.md` 执行。

## 项目结构

```text
.
├── backend/                         # ResearchOS 后端、双 Agent 协调、技能路由和执行层
├── skills/researchos_skill_library/ # 规范化分类后的技能库
├── browser-use/                     # 浏览器自动化能力源码
├── opendataloader-pdf/              # PDF 文献解析/加载能力源码
├── researchos_local_client.pyw      # Windows 本地客户端
├── run_researchos_local_api.ps1     # 本地 API 启动脚本
├── run_researchos_local_api.cmd     # Windows 一键启动入口
└── tests/                           # 后端和技能路由测试
```

## 技能库分类

所有 ResearchOS 技能统一放在 `skills/researchos_skill_library/` 下，并通过 `skill_catalog.json`、`pipeline_registry.json` 和 `legacy_skill_path_map.json` 提供给后端解析。

当前分类：

| 分类 | 用途 |
| --- | --- |
| `01_core_runtime_memory` | 核心运行时、记忆、证据管理、技能路由、输出校验 |
| `02_literature_browser_ingestion` | 文献检索、网页浏览、PDF/引用/开放源码摄取 |
| `03_research_design_protocol` | 研究路线、实验设计、SOP 和 protocol 提取 |
| `04_data_analysis_writing_review` | 数据分析、结果叙述、论文润色、审稿回复和 Nature 工作流 |

后端技能发现入口主要在：

- `backend/researchos/skills/pipeline_registry.py`
- `backend/researchos/execution/skill_dispatcher.py`
- `backend/researchos/api/dual_agent_routes.py`

这些模块会读取技能目录和 catalog，将用户需求路由到 pipeline，再解析 canonical skill path，避免模型只知道旧路径或找不到技能位置。

## 本地启动

在 Windows 上可以直接运行：

```powershell
.\run_researchos_local_api.cmd
```

或使用 PowerShell：

```powershell
.\run_researchos_local_api.ps1
```

默认配置：

- API 地址：`http://127.0.0.1:8765`
- 本地 Agent 数据目录：`agent_data/`
- 可用环境变量：`RESEARCHOS_HOST`、`RESEARCHOS_PORT`、`RESEARCHOS_AGENT_ROOT`

启动脚本会优先使用 `runtime/AURA Research.exe`；如果不存在，则使用本机 Python 启动 `research_agent_api.py`。

## 常用接口

后端路由位于 `backend/researchos/api/dual_agent_routes.py`，主要接口包括：

- `POST /api/agents/coordinator/run`：执行一次双 Agent 任务
- `GET /api/skills/catalog`：查看技能 catalog
- `GET /api/skills/pipelines`：查看 pipeline registry
- `POST /api/skills/route`：根据用户问题测试技能路由
- `GET /api/skills/resolver/check`：检查技能路径解析健康状态

## 测试

运行后端测试：

```powershell
py -m unittest discover -s tests
```

## 不纳入版本库的本地数据

仓库保留代码、技能定义、测试和必要资源；以下内容按设计不提交：

- `.env`
- `.tmp/`
- `agent_data/`
- `data/`
- `generated_outputs/`
- `runtime/`
- PDF、Office 文档、数据库、日志
- 示例输出、实验结果和本地缓存

这样可以避免把测试结果、审计输出、Agent 本地数据和 PDF 文献数据推到远程仓库。
