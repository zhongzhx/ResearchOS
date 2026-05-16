from __future__ import annotations

BRAIN_AGENT_EXTENSION = ""

EXECUTION_AGENT_EXTENSION = ""

USER_VISIBLE_ALLOWED_KEYS = {
    "project_id",
    "project_title",
    "task_id",
    "query",
    "selected_pipeline",
    "feature_id",
    "status",
    "warnings",
}

HIDDEN_CONTEXT_KEYS = {
    "system_prompt",
    "raw_prompt",
    "prompt_messages",
    "debug",
    "traceback",
    "api_key",
    "token",
    "password",
    "cookie",
    "authorization",
}
