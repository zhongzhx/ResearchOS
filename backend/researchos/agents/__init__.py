"""Dual-agent protocol scaffolding for ResearchOS."""

from .agent_protocol import BrainDecision, ContextEnvelope, ExecutionResult, TaskSpec

__all__ = [
    "BrainDecision",
    "ContextEnvelope",
    "ExecutionResult",
    "TaskSpec",
]
