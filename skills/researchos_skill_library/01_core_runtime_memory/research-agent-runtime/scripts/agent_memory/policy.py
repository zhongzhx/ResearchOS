from __future__ import annotations

from typing import Any

from .models import clean


EXPERIMENT_TERMS = [
    "experiment",
    "assay",
    "qPCR",
    "western blot",
    "LC-MS",
    "HPLC",
    "cell line",
    "treatment",
    "control",
    "sample",
    "实验",
    "样本",
    "对照",
    "处理组",
]
FAILURE_TERMS = ["failed", "failure", "negative result", "contamination", "no signal", "失败", "污染", "阴性结果", "重复性差"]
DECISION_TERMS = ["decided", "decision", "switch", "instead", "supersede", "决定", "改为", "不再", "替代"]
PROTOCOL_TERMS = ["protocol", "SOP", "method", "procedure", "步骤", "方案", "流程"]
DATASET_TERMS = ["csv", "xlsx", "dataset", "data file", "raw data", "processed data", "数据", "表格"]
PREFERENCE_TERMS = ["remember", "prefer", "style", "language", "记住", "偏好", "格式", "语言"]


def decide_memory_action(input_payload: dict[str, Any]) -> dict[str, Any]:
    text = clean(input_payload.get("text") or input_payload.get("message") or input_payload.get("content"))
    lower = text.lower()
    if not text:
        return {"action": "ignore", "reason": "empty input", "confidence": 1.0}

    if any(term.lower() in lower for term in FAILURE_TERMS):
        return {"action": "append_memory", "memory_type": "failure_memory", "reason": "failure or negative result detected", "confidence": 0.82}
    if any(term.lower() in lower for term in DECISION_TERMS):
        return {"action": "supersede_old_memory", "memory_type": "decision_memory", "reason": "project decision or direction change detected", "confidence": 0.78}
    if any(term.lower() in lower for term in EXPERIMENT_TERMS):
        return {"action": "create_experiment", "memory_type": "experiment_memory", "reason": "experiment information detected", "confidence": 0.8}
    if any(term.lower() in lower for term in PROTOCOL_TERMS):
        return {"action": "create_protocol", "memory_type": "protocol_memory", "reason": "protocol information detected", "confidence": 0.72}
    if any(term.lower() in lower for term in DATASET_TERMS):
        return {"action": "create_dataset", "memory_type": "dataset_memory", "reason": "data file or dataset information detected", "confidence": 0.72}
    if any(term.lower() in lower for term in PREFERENCE_TERMS):
        return {"action": "append_memory", "memory_type": "preference_memory", "reason": "durable preference detected", "confidence": 0.7}

    if len(text) < 40:
        return {"action": "ignore", "reason": "short casual input with no durable research signal", "confidence": 0.65}
    return {"action": "append_memory", "memory_type": "project_memory", "reason": "potential durable project note", "confidence": 0.45}
