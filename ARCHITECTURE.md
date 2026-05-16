# ResearchOS Directory Boundaries

This repository keeps backend runtime code separate from the registered ResearchOS skill library.

## `backend/`

`backend/` owns runtime and service infrastructure:

- HTTP server
- MVP runtime
- `research_os_mvp.py`
- `research_agent_api.py`
- `research_context_compiler.py`
- prompt router
- global agent system prompts
- RAG / memory / context compiler
- task lifecycle engine
- product feature bridge
- skill dispatcher / runtime loader
- LLM settings / gateway

Current global prompt path:

```text
backend/research_agent_runtime/prompts/
```

Runtime config and reference templates live under:

```text
backend/research_agent_runtime/config/
backend/research_agent_runtime/templates/
```

## `skills/researchos_skill_library/`

`skills/researchos_skill_library/` owns only registerable skills and their metadata:

- skill manifest
- `SKILL.md`
- skill-specific prompt
- parameter schema
- examples
- lightweight executable script
- pipeline metadata
- resolver metadata

## Forbidden Under `skills/`

The skill library must not contain backend runtime or server assets:

- HTTP server
- global agent runtime
- global system prompt
- full context compiler
- memory engine
- database runtime
- `ThreadingHTTPServer` / `BaseHTTPRequestHandler` / FastAPI app definitions
- `research_os_mvp.py`
- `research_agent_api.py`

Compatibility fallback for the old prompt path may exist in code only. The default loader must use `backend/research_agent_runtime/prompts`.
