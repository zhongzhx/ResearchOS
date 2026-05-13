# ResearchOS

ResearchOS is a local dual-agent research workspace for wet-lab scientists. It combines a standard-library HTTP backend, Research Brain memory, execution skills, literature/evidence tooling, and an Electron desktop client.

## Structure

```text
.
├── backend/                         # Dual-agent coordination, skill routing, brain and execution adapters
├── skills/researchos_skill_library/ # Canonical ResearchOS skills, catalog, pipelines, and resolver data
├── electron/                        # Local desktop shell and backend proxy
├── web_client/                      # Plain HTML/CSS/JS client
├── scripts/check_web_client.py      # Static client smoke check
├── run_researchos_local_api.ps1     # Local API launcher
├── run_researchos_local_api.cmd     # Windows launcher
└── tests/                           # Backend, skill, API, and client tests
```

## Local Desktop Client

Start the local client:

```powershell
npm run client:electron
```

Electron opens the local `web_client/` UI, serves static assets, starts the ResearchOS HTTP API when needed, and proxies browser requests through `/api/backend/*`.

Default runtime values:

- API: `http://127.0.0.1:8765`
- Agent data: `agent_data/`
- Important environment variables: `RESEARCHOS_HOST`, `RESEARCHOS_PORT`, `RESEARCHOS_AGENT_ROOT`, `RESEARCHOS_DUAL_AGENT_API_ENABLED`

The Electron launcher sets `RESEARCHOS_DUAL_AGENT_API_ENABLED=true` by default for the desktop client. If the backend is launched manually and this flag is absent, gated `/api/...` dual-agent endpoints return:

```json
{"ok": false, "error": "dual_agent_api_disabled"}
```

The legacy chat route remains available:

```text
POST /research-os/agent/chat
```

## Client Pages

The desktop workspace includes:

- Chat
- Task Lifecycle
- Research Brain
- Library / Evidence
- Skills / Pipelines
- Runs / Execution
- Settings

The client is intentionally plain HTML/CSS/JS. API calls live in `web_client/api.js`, shared state in `web_client/state.js`, views in `web_client/views/`, and reusable UI fragments in `web_client/components/`.

## Key APIs

Dual-agent APIs are gated by `RESEARCHOS_DUAL_AGENT_API_ENABLED=true`:

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

Core ResearchOS APIs used by the client include project, task, memory, claim, protocol, report, reference, file, SkillRun, execution memory, scheduler, and workflow-board endpoints under `/research-os/...`.

## Checks

Run the focused client tests:

```powershell
py -m unittest tests.test_researchos_web_client tests.test_research_agent_api_dual_agent_gate -v
```

Run the static client check:

```powershell
npm run client:check
```

Run the Electron smoke test:

```powershell
npm run client:electron:smoke
```

Run broader backend tests:

```powershell
py -m unittest discover -s tests -p "test_*.py"
$env:LLM_PROVIDER='mock'; py -m unittest discover -s skills\researchos_skill_library\01_core_runtime_memory\research-agent-runtime\scripts\tests -p "test_research_os_mvp.py"
```

## Local Data

The repository should keep code, skill definitions, tests, and required assets only. Local runtime data stays untracked:

- `.env`
- `.tmp/`
- `agent_data/`
- `data/`
- `generated_outputs/`
- `runtime/`
- local PDFs, Office documents, databases, logs, caches, and generated research outputs
