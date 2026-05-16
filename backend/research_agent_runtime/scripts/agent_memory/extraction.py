from __future__ import annotations

import re
from typing import Any

from .models import clean
from .policy import decide_memory_action


CELL_LINES = ["RAW264.7", "HEK293", "HEK293T", "293T", "HeLa", "HepG2", "A549", "HUVEC", "MCF-7", "C2C12", "CHO", "Jurkat"]
INSTRUMENTS = ["LC-MS", "LCMS", "HPLC", "GC-MS", "qPCR", "PCR", "ELISA", "Western blot", "NMR", "SEM", "TEM", "XRD", "FTIR", "UV-vis"]


def _find_list(pattern: str, text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).strip() for match in re.finditer(pattern, text, flags=re.IGNORECASE)))


def _extract_samples(text: str) -> list[dict[str, Any]]:
    sample_ids = []
    for pattern in [
        r"\b(?:sample|样本|compound|cmpd|extract|fraction|batch)[\s:#_-]*[A-Za-z0-9_.-]{1,24}\b",
        r"\b[A-Z]{1,6}[-_]?\d{1,5}[A-Za-z]?\b",
    ]:
        sample_ids.extend(_find_list(pattern, text))
    result = []
    for value in list(dict.fromkeys(sample_ids))[:30]:
        result.append({"sample_code": value, "confidence": 0.62})
    return result


def _extract_groups(text: str) -> dict[str, list[str]]:
    groups = {"control_groups": [], "treatment_groups": [], "positive_controls": [], "negative_controls": []}
    sentences = re.split(r"(?<=[.;。；])\s+", text)
    for sentence in sentences:
        lower = sentence.lower()
        if "positive control" in lower or "阳性对照" in sentence:
            groups["positive_controls"].append(clean(sentence))
        elif "negative control" in lower or "阴性对照" in sentence:
            groups["negative_controls"].append(clean(sentence))
        elif "control" in lower or "对照" in sentence:
            groups["control_groups"].append(clean(sentence))
        elif "treated" in lower or "treatment" in lower or "处理" in sentence or "给药" in sentence:
            groups["treatment_groups"].append(clean(sentence))
    return {key: value[:8] for key, value in groups.items()}


def _extract_conditions(text: str) -> dict[str, list[str]]:
    return {
        "concentrations": _find_list(r"\b\d+(?:\.\d+)?\s?(?:nM|uM|µM|μM|mM|M|mg/mL|ug/mL|μg/mL|ng/mL|%)\b", text),
        "dosages": _find_list(r"\b\d+(?:\.\d+)?\s?(?:mg/kg|g/kg|mg/L|mg/ml|IU|U/mL)\b", text),
        "time_points": _find_list(r"\b\d+(?:\.\d+)?\s?(?:s|min|h|hr|hrs|hour|hours|d|day|days)\b", text),
        "temperature": _find_list(r"\b\d+(?:\.\d+)?\s?(?:°C|C)\b", text),
        "pH": _find_list(r"\bpH\s?\d+(?:\.\d+)?\b", text),
    }


def _detect_experiment_type(text: str) -> str:
    lower = text.lower()
    mapping = [
        ("cell viability assay", ["cck-8", "mtt", "cell viability", "细胞活力"]),
        ("qPCR", ["qpcr", "rt-qpcr"]),
        ("ELISA", ["elisa"]),
        ("western blot", ["western blot", "wb"]),
        ("LC-MS analysis", ["lc-ms", "lcms"]),
        ("HPLC analysis", ["hplc"]),
        ("synthesis", ["synthesis", "reaction", "合成", "反应"]),
        ("materials characterization", ["sem", "tem", "xrd", "ftir"]),
    ]
    for name, terms in mapping:
        if any(term in lower for term in terms):
            return name
    return ""


def _split_experiment_blocks(text: str) -> list[str]:
    parts = re.split(r"(?=\bExperiment\s+\d+[:：]|\bExperiment[:：]|实验\s*\d*[:：])", text, flags=re.IGNORECASE)
    blocks = [clean(part) for part in parts if clean(part)]
    return blocks if len(blocks) > 1 else [clean(text)]


def extract_memory_candidates(input_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    text = clean(input_text)
    context = context or {}
    policy = decide_memory_action({"text": text})
    if not text:
        return {"should_write": False, "detected_memory_types": [], "confidence": 1.0}

    lower = text.lower()
    failed = any(term in lower for term in ["failed", "failure", "contamination", "no signal", "negative", "失败", "污染", "阴性", "重复性差"])
    decision = any(term in lower for term in ["decided", "decision", "switch", "instead", "不再", "改为", "决定"])
    detected_types = []
    if policy.get("memory_type"):
        detected_types.append(str(policy["memory_type"]))
    if failed and "failure_memory" not in detected_types:
        detected_types.append("failure_memory")
    if decision and "decision_memory" not in detected_types:
        detected_types.append("decision_memory")

    samples = _extract_samples(text)
    cell_lines = [name for name in CELL_LINES if re.search(re.escape(name), text, re.IGNORECASE)]
    instruments = [name for name in INSTRUMENTS if re.search(re.escape(name), text, re.IGNORECASE)]
    conditions = _extract_conditions(text)
    groups = _extract_groups(text)
    blocks = _split_experiment_blocks(text)
    experiments = []
    for idx, block in enumerate(blocks, 1):
        if policy.get("action") == "create_experiment" or failed or any(term in block.lower() for term in ["assay", "experiment", "treated", "control", "sample", "实验", "处理", "对照"]):
            title_match = re.search(r"(?:Experiment\s*\d*|实验\s*\d*)[:：]\s*([^.;。；\n]+)", block, flags=re.IGNORECASE)
            title = clean(title_match.group(1)) if title_match else f"Extracted experiment {idx}"
            experiments.append(
                {
                    "title": title,
                    "experiment_type": _detect_experiment_type(block),
                    "purpose": "",
                    "groups": groups,
                    "samples": samples,
                    "conditions": conditions,
                    "cell_lines": cell_lines,
                    "organisms": [],
                    "instruments": instruments,
                    "raw_files": [],
                    "processed_files": [],
                    "statistical_method": clean(re.search(r"(ANOVA|t-test|Mann-Whitney|Kruskal-Wallis|FDR|Benjamini-Hochberg)", block, re.IGNORECASE).group(0)) if re.search(r"(ANOVA|t-test|Mann-Whitney|Kruskal-Wallis|FDR|Benjamini-Hochberg)", block, re.IGNORECASE) else "",
                    "results": [clean(block)] if any(term in block.lower() for term in ["result", "showed", "increased", "decreased", "结果", "升高", "降低"]) else [],
                    "conclusion": "",
                    "limitations": [],
                    "status": "failed" if failed else "completed",
                    "confidence": 0.72 if not failed else 0.78,
                }
            )

    datasets = []
    for filename in _find_list(r"\b[\w.-]+\.(?:csv|xlsx|xls|tsv|txt|pdf|docx)\b", text):
        datasets.append({"filename": filename, "confidence": 0.7})

    uncertainty_flag = any(term in lower for term in ["maybe", "unclear", "not sure", "possibly", "可能", "不确定", "不清楚"])
    confidence = min(0.48, float(policy.get("confidence", 0.5))) if uncertainty_flag else min(0.9, max(float(policy.get("confidence", 0.5)), 0.55 if experiments or samples or datasets else 0.4))
    candidates = {
        "should_write": bool(policy["action"] != "ignore"),
        "policy": policy,
        "detected_memory_types": list(dict.fromkeys(detected_types or ["project_memory"])),
        "project": {
            "title": clean(context.get("project_title") or context.get("project_name") or ""),
            "project_id": clean(context.get("project_id")),
            "confidence": 0.62 if context.get("project_id") else 0.35,
        },
        "experiments": experiments,
        "experiment": experiments[0] if experiments else {},
        "samples": samples,
        "datasets": datasets,
        "decisions": [{"content": text, "confidence": 0.68}] if decision else [],
        "tasks": [{"content": text, "confidence": 0.55}] if any(term in lower for term in ["next", "todo", "下一步", "待办"]) else [],
        "confidence": confidence,
        "needs_review": uncertainty_flag or confidence < 0.55 or (len(experiments) > 3) or (samples and not context.get("project_id")),
        "raw_content": text,
    }
    return candidates
