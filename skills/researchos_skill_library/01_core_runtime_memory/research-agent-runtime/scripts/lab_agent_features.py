from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


VECTOR_SIZE = 128


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(clean(part) for part in parts).encode("utf-8")).hexdigest()[:24]


def mvp_db(agent_root: Path) -> Path:
    agent_root.mkdir(parents=True, exist_ok=True)
    return agent_root / "lab_agent_mvp.sqlite"


def connect(agent_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(mvp_db(agent_root), timeout=30)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS research_interests (
            id TEXT PRIMARY KEY,
            project_name TEXT,
            keyword TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weekly_digests (
            id TEXT PRIMARY KEY,
            project_name TEXT,
            title TEXT,
            interests_json TEXT,
            content_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS failure_records (
            id TEXT PRIMARY KEY,
            title TEXT,
            project TEXT,
            research_field TEXT,
            experiment_type TEXT,
            date TEXT,
            operator TEXT,
            objective TEXT,
            protocol_summary TEXT,
            observed_failure TEXT,
            suspected_causes TEXT,
            confirmed_cause TEXT,
            solution_attempted TEXT,
            final_outcome TEXT,
            tags TEXT,
            related_files TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            file_id TEXT PRIMARY KEY,
            project_name TEXT,
            file_name TEXT,
            source_type TEXT,
            source_path TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            file_id TEXT,
            file_name TEXT,
            source_type TEXT,
            chunk_text TEXT,
            metadata_json TEXT,
            embedding_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_interests_project ON research_interests(project_name);
        CREATE INDEX IF NOT EXISTS idx_digest_project ON weekly_digests(project_name);
        CREATE INDEX IF NOT EXISTS idx_failures_project ON failure_records(project);
        CREATE INDEX IF NOT EXISTS idx_chunks_file ON document_chunks(file_id);
        """
    )
    conn.commit()


def list_research_interests(agent_root: Path, project_name: str = "") -> list[dict[str, Any]]:
    conn = connect(agent_root)
    rows = conn.execute(
        "SELECT * FROM research_interests WHERE (?='' OR project_name=?) ORDER BY keyword",
        (project_name, project_name),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_research_interest(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    keyword = clean(payload.get("keyword"))
    if not keyword:
        raise ValueError("keyword is required")
    project_name = clean(payload.get("project_name"))
    interest_id = stable_id(project_name, keyword.lower())
    timestamp = now()
    row = {
        "id": interest_id,
        "project_name": project_name,
        "keyword": keyword,
        "description": clean(payload.get("description")),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    conn = connect(agent_root)
    conn.execute(
        """
        INSERT INTO research_interests(id, project_name, keyword, description, created_at, updated_at)
        VALUES (:id, :project_name, :keyword, :description, :created_at, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            keyword=excluded.keyword,
            description=excluded.description,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.commit()
    conn.close()
    return row


def update_research_interest(agent_root: Path, interest_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    conn = connect(agent_root)
    existing = conn.execute("SELECT * FROM research_interests WHERE id=?", (interest_id,)).fetchone()
    if not existing:
        conn.close()
        raise KeyError("research interest not found")
    keyword = clean(payload.get("keyword") or existing["keyword"])
    description = clean(payload.get("description") if "description" in payload else existing["description"])
    conn.execute(
        "UPDATE research_interests SET keyword=?, description=?, updated_at=? WHERE id=?",
        (keyword, description, now(), interest_id),
    )
    row = conn.execute("SELECT * FROM research_interests WHERE id=?", (interest_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


def delete_research_interest(agent_root: Path, interest_id: str) -> dict[str, Any]:
    conn = connect(agent_root)
    cur = conn.execute("DELETE FROM research_interests WHERE id=?", (interest_id,))
    conn.commit()
    conn.close()
    return {"deleted": cur.rowcount > 0, "id": interest_id}


def digest_topic_templates(interests: list[str], recent_notes: list[str], max_items: int) -> list[dict[str, Any]]:
    joined = " ".join(interests + recent_notes).lower()
    templates: list[dict[str, Any]] = []
    if any(k in joined for k in ["machine learning", "ai", "bayesian", "computational"]):
        templates.append(
            {
                "topic": "AI-assisted experimental condition optimization",
                "why_it_matters": "Many experimental fields can reduce trial-and-error by treating conditions as searchable variables.",
                "transferable_method": "Bayesian optimization, active learning, design-of-experiments tables, and small pilot loops.",
                "hypothesis": "A low-dimensional condition space can identify a better condition with fewer experiments than manual one-factor changes.",
                "low_cost_validation": "Retrospectively test the optimizer on existing result tables or run a 6-12 condition pilot.",
                "search_keywords": ["AI reaction optimization", "Bayesian optimization chemistry", "machine learning experimental design"],
            }
        )
    if any(k in joined for k in ["synthetic", "catalysis", "polymer", "electrochemistry", "chemistry"]):
        templates.append(
            {
                "topic": "Reproducible reaction and synthesis condition mapping",
                "why_it_matters": "Small uncontrolled changes in solvent, pH, atmosphere, temperature, or catalyst source often explain poor reproducibility.",
                "transferable_method": "Structured condition matrix with negative results and batch metadata.",
                "hypothesis": "Recording hidden condition variables will explain a meaningful fraction of failed synthesis attempts.",
                "low_cost_validation": "Add pH, water content, batch, atmosphere, and timing fields to the next 10 experiments.",
                "search_keywords": ["reaction condition optimization", "negative results chemistry", "design of experiments synthesis"],
            }
        )
    if any(k in joined for k in ["cell", "molecular", "biology", "pharmacology", "toxicology", "microbiology", "biomedical"]):
        templates.append(
            {
                "topic": "Assay robustness and biological control design",
                "why_it_matters": "Weak controls, cell state, passage number, solvent effects, and batch variation can dominate biological assay results.",
                "transferable_method": "Control checklist, passage tracking, positive/negative controls, and replicate-aware reporting.",
                "hypothesis": "Adding control completeness checks will reduce ambiguous cell assay outcomes.",
                "low_cost_validation": "Audit the last 5 assays for seeding density, passage number, solvent concentration, and control groups.",
                "search_keywords": ["cell viability assay controls", "biological assay reproducibility", "positive negative control cell biology"],
            }
        )
    if any(k in joined for k in ["materials", "nanomaterials", "characterization", "spectroscopy", "microscopy"]):
        templates.append(
            {
                "topic": "Linking synthesis variables to characterization readouts",
                "why_it_matters": "Materials projects often fail when synthesis records and characterization outputs are not connected at the sample level.",
                "transferable_method": "Sample-level metadata table linking synthesis, storage, characterization, and performance.",
                "hypothesis": "A unified sample metadata table will reveal which synthesis factors correlate with characterization changes.",
                "low_cost_validation": "Create one table joining synthesis date, batch, XRD/SEM/TEM/FTIR notes, and performance metrics for 20 samples.",
                "search_keywords": ["materials informatics characterization", "nanomaterials synthesis metadata", "materials reproducibility"],
            }
        )
    if any(k in joined for k in ["omics", "metabolomics", "proteomics", "transcriptomics"]):
        templates.append(
            {
                "topic": "Omics feature prioritization with experimental validation",
                "why_it_matters": "Differential features need careful filtering before expensive wet-lab validation.",
                "transferable_method": "Fold-change, adjusted p-value, VIP score, pathway relevance, and validation feasibility scoring.",
                "hypothesis": "Combining statistical and feasibility filters will produce a smaller, more testable candidate list.",
                "low_cost_validation": "Rank current features by p value, fold change, missingness, and assay availability.",
                "search_keywords": ["metabolomics biomarker validation", "proteomics differential analysis", "omics feature prioritization"],
            }
        )
    for interest in interests:
        if len(templates) >= max_items:
            break
        templates.append(
            {
                "topic": f"New methods and negative-result patterns in {interest}",
                "why_it_matters": f"{interest} is part of the configured research profile and should be watched for methods that transfer across projects.",
                "transferable_method": "Extract methods, controls, failure modes, and validation metrics from recent papers and lab notes.",
                "hypothesis": f"A small weekly scan of {interest} will identify one method or control worth testing locally.",
                "low_cost_validation": "Search 5 recent papers, extract methods, and compare them against current lab practice.",
                "search_keywords": [interest, f"{interest} methods", f"{interest} reproducibility"],
            }
        )
    return templates[:max_items]


def generate_weekly_digest(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_name = clean(payload.get("project_name"))
    interests = [clean(item) for item in payload.get("research_interests") or [] if clean(item)]
    if not interests:
        interests = [row["keyword"] for row in list_research_interests(agent_root, project_name)]
    if not interests:
        raise ValueError("research_interests are required or must be configured first")
    recent_notes = [clean(item) for item in payload.get("recent_notes") or [] if clean(item)]
    max_items = int(payload.get("max_items") or 5)
    language = payload.get("language") or "en"
    result = {
        "title": "Weekly Research Digest" if language == "en" else "每周科研简报",
        "research_interests": interests,
        "items": digest_topic_templates(interests, recent_notes, max_items),
        "created_at": now(),
        "language": language,
    }
    digest_id = stable_id(project_name, json.dumps(interests, ensure_ascii=False), result["created_at"])
    conn = connect(agent_root)
    conn.execute(
        "INSERT INTO weekly_digests(id, project_name, title, interests_json, content_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (digest_id, project_name, result["title"], json.dumps(interests, ensure_ascii=False), json.dumps(result, ensure_ascii=False), result["created_at"]),
    )
    conn.commit()
    conn.close()
    result["id"] = digest_id
    return result


def list_weekly_digests(agent_root: Path, project_name: str = "", limit: int = 50) -> list[dict[str, Any]]:
    conn = connect(agent_root)
    rows = conn.execute(
        "SELECT * FROM weekly_digests WHERE (?='' OR project_name=?) ORDER BY created_at DESC LIMIT ?",
        (project_name, project_name, limit),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["content"] = json.loads(item.pop("content_json") or "{}")
            item["interests"] = json.loads(item.pop("interests_json") or "[]")
        except json.JSONDecodeError:
            item["content"] = {}
            item["interests"] = []
        result.append(item)
    return result


def find_matches(patterns: list[str], text: str, flags: int = re.IGNORECASE) -> list[str]:
    values: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags):
            value = clean(match.group(0))
            if value and value not in values:
                values.append(value)
    return values


def nearby_items(keywords: list[str], text: str, window: int = 80) -> list[str]:
    items: list[str] = []
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text, re.IGNORECASE):
            snippet = clean(text[max(0, match.start() - window) : min(len(text), match.end() + window)])
            if snippet and snippet not in items:
                items.append(snippet)
    return items[:20]


def extract_protocol(payload: dict[str, Any]) -> dict[str, Any]:
    text = clean(payload.get("paper_text"))
    if not text:
        raise ValueError("paper_text is required")
    experiment_hint = clean(payload.get("experiment_type"))
    lowered = text.lower()
    experiment_type = experiment_hint or infer_experiment_type(lowered)
    research_field = infer_research_field(lowered, experiment_type)
    organisms = find_matches([r"\b(?:HeLa|MCF-7|A549|HEK293|RAW264\.7|HCT116|HepG2|E\. coli|Saccharomyces cerevisiae)\b", r"[\u4e00-\u9fa5A-Za-z0-9-]+细胞"], text)
    reagents = []
    reagent_contexts = nearby_items(["reagent", "treated", "medium", "抗体", "试剂", "溶液", "buffer"], text)
    for ctx in reagent_contexts:
        reagents.append({"name": ctx[:120], "concentration": first_or_empty(find_matches([r"\b\d+(?:\.\d+)?\s?(?:nM|uM|μM|mM|M|%|mg/mL|ug/mL|μg/mL)\b"], ctx)), "role": "unknown"})
    concentrations = find_matches([r"\b\d+(?:\.\d+)?\s?(?:nM|uM|μM|mM|M|%|mg/mL|ug/mL|μg/mL|g/L|mol/L)\b"], text)
    temperature = find_matches([r"\b\d+(?:\.\d+)?\s?(?:°C|℃|deg C|K)\b", r"室温"], text)
    times = find_matches([r"\b\d+(?:\.\d+)?\s?(?:s|min|h|hr|hours|days|d)\b", r"\d+(?:\.\d+)?\s?(?:秒|分钟|小时|天)"], text)
    p_h = find_matches([r"\bpH\s?\d+(?:\.\d+)?\b", r"pH值?\s?\d+(?:\.\d+)?"], text)
    pressure = find_matches([r"\b\d+(?:\.\d+)?\s?(?:atm|bar|Pa|kPa|MPa|psi)\b"], text)
    atmosphere = find_matches([r"\b(?:N2|nitrogen|argon|Ar|oxygen|O2|CO2|air|anaerobic)\b", r"氮气|氩气|空气|厌氧"], text)
    sample_size = find_matches([r"\bn\s?=\s?\d+\b", r"\b\d+\s?(?:samples|replicates|mice|rats|patients)\b", r"\d+\s?(?:个样本|次重复|只小鼠|名患者)"], text)
    instruments = find_matches([r"\b(?:HPLC|LC-MS|GC-MS|NMR|XRD|SEM|TEM|FTIR|Raman|XPS|plate reader|flow cytometer|microscope)\b", r"酶标仪|流式细胞仪|显微镜|质谱|液相色谱"], text)
    software = find_matches([r"\b(?:GraphPad Prism|ImageJ|R|Python|SPSS|Origin|MATLAB|FlowJo|MaxQuant)\b"], text)
    controls = nearby_items(["control", "vehicle", "blank", "positive", "negative", "对照", "阳性", "阴性", "空白"], text)
    treatment = nearby_items(["treatment", "treated", "dose", "处理", "给药", "浓度"], text)
    readouts = find_matches([r"\b(?:absorbance|fluorescence|luminescence|OD\d+|Ct value|viability|apoptosis|yield|conversion|selectivity)\b", r"吸光度|荧光|发光|细胞活力|凋亡率|产率|转化率"], text)
    characterization = find_matches([r"\b(?:XRD|SEM|TEM|FTIR|Raman|XPS|BET|DSC|TGA|UV-vis)\b"], text)
    statistics = nearby_items(["t-test", "ANOVA", "p value", "GraphPad", "统计", "方差分析", "显著"], text)
    materials = nearby_items(["material", "nanoparticle", "polymer", "compound", "substrate", "材料", "纳米", "聚合物", "化合物"], text)
    missing = missing_protocol_fields(experiment_type, organisms, reagents, concentrations, temperature, times, controls, readouts, statistics)
    warnings = []
    if concentrations and not reagents:
        warnings.append("Concentrations are reported but reagent identities or roles are unclear.")
    if any("room temperature" in item.lower() or item == "室温" for item in temperature):
        warnings.append("Room temperature is ambiguous unless the lab temperature range is recorded.")
    if controls and not treatment:
        warnings.append("Controls are mentioned but treatment-group definitions may be incomplete.")
    safety_notes = []
    if any(word in lowered for word in ["human", "patient", "animal", "mouse", "rat", "临床", "患者", "动物"]):
        safety_notes.append("Human/animal/clinical work requires ethics approval and design-level review.")
    if any(word in lowered for word in ["toxic", "hazard", "flammable", "有毒", "危险", "易燃"]):
        safety_notes.append("Hazardous reagent handling and waste disposal must be confirmed from institutional SOPs.")
    return {
        "experiment_type": experiment_type,
        "research_field": research_field,
        "organisms_or_cell_lines": organisms,
        "materials": materials,
        "reagents": reagents,
        "instruments": instruments,
        "software": software,
        "concentrations": concentrations,
        "temperature": temperature,
        "time": times,
        "pH": p_h,
        "pressure": pressure,
        "atmosphere": atmosphere,
        "sample_size": sample_size,
        "control_groups": controls,
        "treatment_groups": treatment,
        "assay_readouts": readouts,
        "characterization_methods": characterization,
        "statistical_methods": statistics,
        "safety_notes": safety_notes,
        "missing_information": missing,
        "reproducibility_warnings": warnings,
        "supported_by_provided_data": ["Structured fields are extracted only from the provided text."],
        "plausible_but_needs_validation": [],
        "unsupported": [],
    }


def first_or_empty(values: list[str]) -> str:
    return values[0] if values else ""


def infer_experiment_type(lowered: str) -> str:
    if any(k in lowered for k in ["cck-8", "mtt", "cell viability", "细胞活力"]):
        return "cell viability assay"
    if "qpcr" in lowered or "rt-qpcr" in lowered:
        return "qPCR"
    if "western blot" in lowered:
        return "Western blot"
    if "elisa" in lowered:
        return "ELISA"
    if any(k in lowered for k in ["xrd", "sem", "tem", "ftir", "raman"]):
        return "materials characterization"
    if any(k in lowered for k in ["hplc", "lc-ms", "gc-ms", "chromatography"]):
        return "analytical chemistry assay"
    return "unknown"


def infer_research_field(lowered: str, experiment_type: str) -> str:
    if any(k in lowered for k in ["cell", "protein", "gene", "mice", "mouse", "细胞", "蛋白", "基因"]):
        return "cell biology"
    if any(k in lowered for k in ["xrd", "sem", "tem", "nanoparticle", "polymer", "材料"]):
        return "materials science"
    if any(k in lowered for k in ["reaction", "synthesis", "catalyst", "溶剂", "催化"]):
        return "chemistry"
    if experiment_type != "unknown":
        return experiment_type
    return "unknown"


def missing_protocol_fields(experiment_type: str, organisms: list[str], reagents: list[dict[str, str]], concentrations: list[str], temperature: list[str], times: list[str], controls: list[str], readouts: list[str], statistics: list[str]) -> list[str]:
    missing = []
    if experiment_type == "unknown":
        missing.append("experiment type is not clearly reported")
    if not temperature:
        missing.append("temperature is not reported")
    if not times:
        missing.append("incubation/reaction time is not reported")
    if not concentrations:
        missing.append("concentrations or dose levels are not reported")
    if not controls:
        missing.append("control groups are not clearly reported")
    if not readouts:
        missing.append("assay readouts or measured outcomes are not reported")
    if not statistics:
        missing.append("statistical methods are not reported")
    if "cell" in experiment_type.lower() and not organisms:
        missing.append("cell line or organism is not reported")
    if not reagents:
        missing.append("reagent supplier/catalog/role details are not clearly reported")
    return missing


def generate_sop(payload: dict[str, Any]) -> dict[str, Any]:
    goal = clean(payload.get("experiment_goal"))
    if not goal:
        raise ValueError("experiment_goal is required")
    protocol = payload.get("protocol_json") or {}
    if isinstance(protocol, str):
        protocol = json.loads(protocol or "{}")
    language = payload.get("language") or "en"
    lower_goal = goal.lower()
    is_human_animal = bool(re.search(r"\b(human|patient|animal|mouse|mice|rat|rats|clinical)\b", lower_goal)) or any(k in lower_goal for k in ["人体", "患者", "动物"])
    confirm = list(protocol.get("missing_information") or [])
    if is_human_animal:
        confirm.append("ethics approval, inclusion/exclusion criteria, consent/data governance, and qualified supervision must be confirmed before execution")
    cell_checks = []
    if any(k in lower_goal for k in ["cell", "细胞"]) or "cell" in clean(protocol.get("research_field")).lower():
        cell_checks = ["contamination status", "cell state and confluence", "passage number", "solvent concentration", "positive control", "negative control"]
        confirm.extend([f"confirm {item}" for item in cell_checks])
    title = f"SOP: {goal}"
    sop = {
        "title": title,
        "objective": goal,
        "principle": "Convert the research goal and extracted protocol parameters into a conservative, reproducibility-oriented workflow.",
        "scope": "Design-level SOP for local lab review. Qualified human approval is required before execution.",
        "materials_and_reagents": protocol.get("materials", []) + protocol.get("reagents", []),
        "equipment": protocol.get("instruments", []) or payload.get("available_equipment") or [],
        "experimental_design": {
            "control_groups": protocol.get("control_groups", []),
            "treatment_groups": protocol.get("treatment_groups", []),
            "sample_size": protocol.get("sample_size", []),
            "lab_constraints": payload.get("lab_constraints") or [],
        },
        "step_by_step_procedure": design_level_steps(goal, protocol, is_human_animal),
        "key_parameters": {
            "concentrations": protocol.get("concentrations", []),
            "temperature": protocol.get("temperature", []),
            "time": protocol.get("time", []),
            "pH": protocol.get("pH", []),
            "pressure": protocol.get("pressure", []),
            "atmosphere": protocol.get("atmosphere", []),
        },
        "quality_control_points": ["verify identity and freshness of reagents", "record batch numbers", "record deviations", "check controls before interpreting results"] + cell_checks,
        "common_failure_modes": ["missing or weak controls", "unrecorded batch effects", "ambiguous reagent identity", "insufficient replicate information", "instrument calibration drift"],
        "troubleshooting": ["If controls fail, do not interpret treatment effects.", "If key parameters are missing, pause and confirm before execution.", "If results are inconsistent, repeat the smallest validated subset before expanding."],
        "data_recording_template": ["date", "operator", "sample_id", "group", "batch", "key_parameters", "raw_readout", "processed_readout", "deviation_notes"],
        "safety_and_waste_disposal_notes": protocol.get("safety_notes", []) + ["Follow institutional SOPs and waste disposal rules.", "Do not execute human/animal/clinical or hazardous procedures without approval."],
        "information_to_confirm_before_execution": unique(confirm),
        "supported_by_provided_data": ["SOP fields are based on the provided goal, protocol JSON, constraints, and equipment list."],
        "plausible_but_needs_validation": ["Step order and QC points should be reviewed against the lab's approved SOPs."],
        "unsupported": [],
        "language": language,
    }
    if payload.get("target_format") == "markdown":
        sop["markdown"] = sop_to_markdown(sop)
    return sop


def design_level_steps(goal: str, protocol: dict[str, Any], design_only: bool) -> list[str]:
    if design_only:
        return [
            "Define study objective, variables, endpoints, and documentation requirements.",
            "Confirm ethics, safety, data governance, and responsible personnel.",
            "Prepare a design matrix and analysis plan for review; do not execute until approved.",
        ]
    steps = [
        "Confirm objective, controls, treatment groups, and required readouts.",
        "Prepare materials, reagents, equipment, and data-recording sheet.",
        "Record batch, sample, operator, and environmental metadata before starting.",
        "Run the experiment according to approved lab SOPs and record deviations.",
        "Check quality-control points before analyzing treatment effects.",
        "Export raw data and processed data with clear sample identifiers.",
    ]
    if protocol.get("characterization_methods"):
        steps.append("Run characterization methods and link outputs to sample identifiers.")
    return steps


def unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        value = clean(value)
        if value and value not in result:
            result.append(value)
    return result


def sop_to_markdown(sop: dict[str, Any]) -> str:
    lines = [f"# {sop['title']}", "", f"## Objective\n{sop['objective']}", "", f"## Principle\n{sop['principle']}", "", "## Step-by-Step Procedure"]
    lines.extend(f"{idx}. {step}" for idx, step in enumerate(sop["step_by_step_procedure"], 1))
    lines.extend(["", "## Information to Confirm Before Execution"])
    lines.extend(f"- {item}" for item in sop["information_to_confirm_before_execution"])
    return "\n".join(lines)


FAILURE_FIELDS = [
    "title",
    "project",
    "research_field",
    "experiment_type",
    "date",
    "operator",
    "objective",
    "protocol_summary",
    "observed_failure",
    "suspected_causes",
    "confirmed_cause",
    "solution_attempted",
    "final_outcome",
    "tags",
    "related_files",
]


def create_failure_record(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    title = clean(payload.get("title"))
    if not title:
        raise ValueError("title is required")
    timestamp = now()
    row = {field: normalize_list_text(payload.get(field)) for field in FAILURE_FIELDS}
    row["id"] = payload.get("id") or stable_id(title, row.get("project", ""), timestamp)
    row["created_at"] = timestamp
    row["updated_at"] = timestamp
    conn = connect(agent_root)
    conn.execute(
        f"""
        INSERT INTO failure_records({', '.join(['id'] + FAILURE_FIELDS + ['created_at', 'updated_at'])})
        VALUES ({', '.join('?' for _ in ['id'] + FAILURE_FIELDS + ['created_at', 'updated_at'])})
        """,
        [row["id"]] + [row[field] for field in FAILURE_FIELDS] + [row["created_at"], row["updated_at"]],
    )
    conn.commit()
    conn.close()
    return row


def normalize_list_text(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return clean(value)


def update_failure_record(agent_root: Path, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    conn = connect(agent_root)
    existing = conn.execute("SELECT * FROM failure_records WHERE id=?", (record_id,)).fetchone()
    if not existing:
        conn.close()
        raise KeyError("failure record not found")
    values = dict(existing)
    for field in FAILURE_FIELDS:
        if field in payload:
            values[field] = normalize_list_text(payload.get(field))
    values["updated_at"] = now()
    assignments = ", ".join(f"{field}=?" for field in FAILURE_FIELDS + ["updated_at"])
    conn.execute(f"UPDATE failure_records SET {assignments} WHERE id=?", [values[field] for field in FAILURE_FIELDS + ["updated_at"]] + [record_id])
    row = conn.execute("SELECT * FROM failure_records WHERE id=?", (record_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row)


def delete_failure_record(agent_root: Path, record_id: str) -> dict[str, Any]:
    conn = connect(agent_root)
    cur = conn.execute("DELETE FROM failure_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return {"deleted": cur.rowcount > 0, "id": record_id}


def search_failure_records(agent_root: Path, query: str = "", project: str = "", research_field: str = "", experiment_type: str = "", tags: str = "", limit: int = 50) -> list[dict[str, Any]]:
    conn = connect(agent_root)
    rows = conn.execute("SELECT * FROM failure_records ORDER BY updated_at DESC").fetchall()
    conn.close()
    filters = [query, project, research_field, experiment_type, tags]
    result = []
    for row in rows:
        item = dict(row)
        haystack = " ".join(str(v or "") for v in item.values()).lower()
        if all(clean(f).lower() in haystack for f in filters if clean(f)):
            result.append(item)
    return result[:limit]


def tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9\u4e00-\u9fa5]{2,}", text)}


def match_failure_records(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    plan = clean(payload.get("experimental_plan") or payload.get("plan") or payload.get("protocol_summary"))
    if not plan:
        raise ValueError("experimental_plan is required")
    plan_tokens = tokens(plan)
    records = search_failure_records(agent_root, project=clean(payload.get("project")), limit=500)
    matches = []
    for record in records:
        text = " ".join(str(record.get(field, "")) for field in FAILURE_FIELDS)
        overlap = plan_tokens & tokens(text)
        if not overlap:
            continue
        score = len(overlap) / max(1, len(plan_tokens))
        if score < 0.03:
            continue
        reason_terms = ", ".join(sorted(list(overlap))[:8])
        matches.append(
            {
                "id": record["id"],
                "title": record["title"],
                "similarity_score": round(score, 3),
                "similarity_reason": f"Overlapping plan and historical failure terms: {reason_terms}",
                "suggestion": failure_suggestion(record),
            }
        )
    matches.sort(key=lambda item: item["similarity_score"], reverse=True)
    top = matches[: int(payload.get("limit") or 5)]
    risk = "high" if top and top[0]["similarity_score"] >= 0.25 else "medium" if top else "low"
    return {"risk_level": risk, "matched_failures": top}


def failure_suggestion(record: dict[str, Any]) -> str:
    if record.get("confirmed_cause"):
        return f"Check confirmed historical cause first: {record['confirmed_cause']}"
    if record.get("solution_attempted"):
        return f"Review previous solution attempt before repeating: {record['solution_attempted']}"
    return "Add controls, record key parameters, and run a small pilot before scaling this plan."


def peer_review_simulation(payload: dict[str, Any]) -> dict[str, Any]:
    text = clean(payload.get("manuscript_text"))
    if not text:
        raise ValueError("manuscript_text is required")
    mode = payload.get("review_mode") or "general"
    lower = text.lower()
    major, minor = [], []
    missing_controls, overclaims, stat_issues, method_gaps, repro = [], [], [], [], []
    if re.search(r"\b(no|without|lacking)\s+control", lower) or "未设置对照" in lower:
        missing_controls.append("The provided text explicitly indicates that control details are absent or insufficient.")
    elif not any(k in lower for k in ["control", "对照", "vehicle", "baseline"]):
        missing_controls.append("The provided text does not clearly describe control groups.")
    if not any(k in lower for k in ["n=", "replicate", "sd", "sem", "p<", "p =", "anova", "t-test", "统计"]):
        stat_issues.append("The provided text does not report replicate count or statistical testing details.")
    strong_claim_terms = ["prove", "confirm", "fully", "completely", "therefore", "blocks", "abolishes", "完全", "证明", "因此"]
    weak_evidence_terms = ["one ", "single", "pilot", "trend", "preliminary", "一次", "单次", "预实验", "趋势", "初步"]
    mechanism_terms = ["rescue", "knockdown", "overexpression", "inhibitor", "dose-response", "time-course", "拯救", "敲低", "过表达"]
    if (
        any(k in lower for k in strong_claim_terms)
        and (
            any(k in lower for k in weak_evidence_terms)
            or not any(k in lower for k in mechanism_terms)
            or not any(k in lower for k in ["replicate", "n=", "p<", "p =", "anova", "t-test", "统计"])
        )
    ):
        overclaims.append("The conclusion wording appears stronger than the mechanistic evidence described in the text.")
    if not any(k in lower for k in ["method", "methods", "prepared", "measured", "performed", "方法", "检测"]):
        method_gaps.append("Methods are not sufficiently visible in the provided section.")
    if not any(k in lower for k in ["catalog", "supplier", "batch", "passage", "instrument", "software", "货号", "厂家"]):
        repro.append("Reagent, instrument, software, batch, or sample-state details are insufficient for reproducibility.")
    if mode in {"mechanism", "hostile_reviewer"} and not any(k in lower for k in ["rescue", "knockdown", "overexpression", "inhibitor", "pathway", "机制"]):
        major.append("Mechanistic evidence is weak or not shown in the provided text.")
    if mode in {"novelty", "hostile_reviewer"} and not any(k in lower for k in ["novel", "first", "gap", "unlike", "创新", "首次"]):
        minor.append("The novelty position is not clearly articulated in the provided text.")
    if mode in {"methods", "hostile_reviewer"} and method_gaps:
        major.extend(method_gaps)
    if stat_issues and mode in {"statistics", "hostile_reviewer"}:
        major.extend(stat_issues)
    if missing_controls:
        major.extend(missing_controls)
    if overclaims:
        major.extend(overclaims)
    overall = "The section is potentially useful but needs stronger controls, methods transparency, and claim calibration." if major else "No major flaw was detected from the provided text, but review is limited to the pasted content."
    if mode == "hostile_reviewer" and major:
        overall = "A critical reviewer would likely challenge the evidentiary strength and reproducibility of this section."
    return {
        "overall_assessment": overall,
        "major_concerns": unique_text(major),
        "minor_concerns": unique_text(minor),
        "missing_controls": unique_text(missing_controls),
        "overclaimed_conclusions": unique_text(overclaims),
        "statistical_issues": unique_text(stat_issues),
        "methodological_gaps": unique_text(method_gaps),
        "reproducibility_issues": unique_text(repro),
        "suggested_experiments": suggest_experiments(mode, lower),
        "suggested_rewriting": ["Replace causal or definitive wording with wording tied to the measured evidence.", "Add one sentence naming controls, replicate count, and primary endpoint."],
        "supported_by_provided_data": ["All concerns are based on missing or present signals in the supplied text."],
        "plausible_but_needs_validation": ["Suggested experiments require field-specific review before execution."],
        "unsupported": [],
    }


def unique_text(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def suggest_experiments(mode: str, lower: str) -> list[str]:
    suggestions = []
    if "cell" in lower or "细胞" in lower:
        suggestions.append("Add positive and negative controls, cell-state/passaging records, and replicate-level reporting.")
    if mode == "mechanism" or "pathway" in lower:
        suggestions.append("Add mechanism-oriented validation such as perturbation, rescue, or pathway-specific controls where appropriate.")
    if mode == "statistics":
        suggestions.append("Report raw replicate count, variance measure, test choice, and multiple-testing correction where applicable.")
    if not suggestions:
        suggestions.append("Add the smallest control or validation experiment that directly tests the central claim.")
    return suggestions


def parse_scientific_data(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("csv_text"):
        rows = read_csv_text(payload["csv_text"])
        file_name = payload.get("file_name") or "pasted.csv"
    elif payload.get("file_path"):
        path = Path(payload["file_path"])
        if not path.exists():
            raise FileNotFoundError(f"file not found: {path}")
        if path.suffix.lower() == ".csv":
            rows = read_csv_text(path.read_text(encoding="utf-8-sig", errors="replace"))
        elif path.suffix.lower() == ".xlsx":
            rows = read_xlsx(path)
        else:
            raise ValueError("Only CSV and XLSX files are supported")
        file_name = path.name
    else:
        raise ValueError("csv_text or file_path is required")
    return summarize_table(rows, file_name)


def read_csv_text(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [{clean(k): clean(v) for k, v in row.items()} for row in reader]


def read_xlsx(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in root.findall("a:si", ns):
                texts = [t.text or "" for t in si.findall(".//a:t", ns)]
                shared.append("".join(texts))
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in z.namelist():
            candidates = [name for name in z.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            if not candidates:
                return []
            sheet_name = candidates[0]
        root = ET.fromstring(z.read(sheet_name))
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        grid: dict[int, dict[int, str]] = defaultdict(dict)
        for row in root.findall(".//a:row", ns):
            r_idx = int(row.attrib.get("r", "0"))
            for c in row.findall("a:c", ns):
                ref = c.attrib.get("r", "")
                col_idx = column_index(re.sub(r"\d+", "", ref))
                v = c.find("a:v", ns)
                value = v.text if v is not None else ""
                if c.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared):
                    value = shared[int(value)]
                grid[r_idx][col_idx] = clean(value)
        if not grid:
            return []
        first_row = min(grid)
        headers = [grid[first_row].get(i, f"column_{i}") for i in range(1, max(grid[first_row] or {1: ""}) + 1)]
        rows = []
        for r_idx in sorted(k for k in grid if k != first_row):
            rows.append({headers[i - 1] if i - 1 < len(headers) else f"column_{i}": grid[r_idx].get(i, "") for i in range(1, len(headers) + 1)})
        return rows


def column_index(col: str) -> int:
    result = 0
    for ch in col.upper():
        if "A" <= ch <= "Z":
            result = result * 26 + (ord(ch) - ord("A") + 1)
    return result or 1


def to_float(value: Any) -> float | None:
    try:
        if clean(value) == "":
            return None
        result = float(clean(value))
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except ValueError:
        return None


def summarize_table(rows: list[dict[str, str]], file_name: str) -> dict[str, Any]:
    if not rows:
        return {"file_name": file_name, "error": "table is empty or could not be parsed"}
    columns = list(rows[0].keys())
    numeric_columns, sample_columns, group_columns, metadata_columns = [], [], [], []
    missing_count = 0
    total = max(1, len(rows) * len(columns))
    for col in columns:
        values = [row.get(col, "") for row in rows]
        missing_count += sum(1 for v in values if clean(v) == "")
        floats = [to_float(v) for v in values]
        numeric = [v for v in floats if v is not None]
        lname = col.lower()
        if len(numeric) >= max(1, len(values) // 2):
            numeric_columns.append(col)
        elif any(k in lname for k in ["sample", "sample_id", "id", "样本"]):
            sample_columns.append(col)
        elif any(k in lname for k in ["group", "condition", "treatment", "class", "组别"]):
            group_columns.append(col)
        else:
            metadata_columns.append(col)
    group_col = group_columns[0] if group_columns else ""
    group_counts = Counter(row.get(group_col, "unknown") or "unknown" for row in rows) if group_col else Counter()
    duplicate_samples = []
    if sample_columns:
        counts = Counter(row.get(sample_columns[0], "") for row in rows)
        duplicate_samples = [sample for sample, count in counts.items() if sample and count > 1]
    stats = {}
    for col in numeric_columns:
        values = [to_float(row.get(col, "")) for row in rows]
        nums = [v for v in values if v is not None]
        if nums:
            stats[col] = {"count": len(nums), "mean": sum(nums) / len(nums), "min": min(nums), "max": max(nums)}
    return {
        "file_name": file_name,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "sample_columns": sample_columns or ["unknown"],
        "group_columns": group_columns or ["unknown"],
        "numeric_columns": numeric_columns,
        "possible_metadata_columns": metadata_columns,
        "detected_groups": list(group_counts.keys()) if group_counts else ["unknown"],
        "sample_count_per_group": dict(group_counts),
        "missing_value_ratio": missing_count / total,
        "duplicated_samples": duplicate_samples,
        "descriptive_statistics": stats,
        "omics_fields": detect_omics_fields(columns),
        "rows_preview": rows[:10],
    }


def detect_omics_fields(columns: list[str]) -> dict[str, str]:
    mapping = {
        "feature_name": ["feature", "id", "name"],
        "compound_name": ["compound", "metabolite"],
        "gene_name": ["gene", "symbol"],
        "protein_name": ["protein", "uniprot"],
        "m/z": ["m/z", "mz"],
        "retention_time": ["rt", "retention"],
        "fold_change": ["fold", "log2fc", "fc"],
        "p_value": ["pvalue", "p_value", "p value"],
        "adjusted_p_value": ["padj", "qvalue", "adjusted"],
        "VIP_score": ["vip"],
        "group_intensity_columns": ["intensity", "area", "abundance"],
    }
    result = {}
    lower_cols = {col.lower(): col for col in columns}
    for field, terms in mapping.items():
        matches = [original for lower, original in lower_cols.items() if any(term in lower for term in terms)]
        result[field] = matches if field == "group_intensity_columns" and matches else (matches[0] if matches else "unknown")
    return result


def result_narrative(payload: dict[str, Any]) -> dict[str, Any]:
    data_summary = clean(payload.get("data_summary"))
    parsed = payload.get("parsed_table") or {}
    experiment_type = clean(payload.get("experiment_type")) or "experiment"
    style = payload.get("target_style") or "journal"
    stats_method = clean(payload.get("statistical_method"))
    has_stats = bool(stats_method or re.search(r"\bp\s?[<=>]\s?0\.\d+", data_summary, re.IGNORECASE))
    top_numeric = []
    if isinstance(parsed, dict):
        stats = parsed.get("descriptive_statistics") or {}
        top_numeric = list(stats.keys())[:4]
    paragraph = f"The {experiment_type} data were summarized for {style} reporting."
    if data_summary:
        paragraph += f" The provided summary states: {data_summary}"
    if top_numeric:
        paragraph += f" Quantitative columns available for reporting include {', '.join(top_numeric)}."
    if not has_stats:
        paragraph += " Because raw replicate values or statistical results were not provided, statistical significance should not be claimed."
    legend = f"Figure X. Summary of {experiment_type} results."
    if parsed.get("detected_groups"):
        legend += f" Groups detected: {', '.join(map(str, parsed.get('detected_groups', [])))}."
    return {
        "result_paragraph": paragraph,
        "figure_legend": legend,
        "statistical_advice": stats_method or "Provide replicate-level values, sample size, variance measure, test choice, and multiple-testing correction if applicable.",
        "conclusion_strength": "moderate" if has_stats else "descriptive_only",
        "unsupported_claims_to_avoid": ["Do not claim statistical significance without p values or confidence intervals.", "Do not claim mechanism without mechanism-specific validation."],
        "required_additional_information": [] if has_stats else ["raw replicate values", "sample size per group", "statistical test", "variance measure"],
        "supported_by_provided_data": ["Narrative is based on the provided data summary and parsed table overview."],
        "plausible_but_needs_validation": [],
        "unsupported": [],
    }


def ingest_rag_document(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_name = clean(payload.get("project_name"))
    source_type = clean(payload.get("source_type")) or "experimental note"
    file_path = clean(payload.get("file_path"))
    max_chars = int(payload.get("chunk_size") or 1200)
    overlap = int(payload.get("chunk_overlap") or 150)
    pages: list[dict[str, Any]]
    if payload.get("text"):
        text = clean(payload.get("text"))
        file_name = clean(payload.get("file_name")) or "pasted_document.txt"
        source_path = ""
        pages = [{"page_number": payload.get("page_number"), "text": text}]
    elif file_path:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {path}")
        file_name = path.name
        source_path = str(path.resolve())
        if path.suffix.lower() == ".pdf":
            pages = extract_pdf_pages_for_rag(path)
            text = "\n\n".join(page["text"] for page in pages)
        else:
            text = extract_text_for_rag(path)
            pages = [{"page_number": payload.get("page_number"), "text": text}]
    else:
        raise ValueError("text or file_path is required")
    if not text:
        raise ValueError("no text could be extracted")
    file_id = stable_id(project_name, file_name, source_type, text[:200])
    chunk_records = chunk_records_from_pages(pages, max_chars=max_chars, overlap=overlap)
    if not chunk_records:
        raise ValueError("no chunks could be created")
    conn = connect(agent_root)
    conn.execute(
        "INSERT OR REPLACE INTO documents(file_id, project_name, file_name, source_type, source_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (file_id, project_name, file_name, source_type, source_path, now()),
    )
    conn.execute("DELETE FROM document_chunks WHERE file_id=?", (file_id,))
    for record in chunk_records:
        chunk = record["text"]
        metadata = record["metadata"]
        chunk_id = stable_id(file_id, str(metadata["chunk_index"]), chunk[:50])
        conn.execute(
            "INSERT INTO document_chunks(id, file_id, file_name, source_type, chunk_text, metadata_json, embedding_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, file_id, file_name, source_type, chunk, json.dumps(metadata, ensure_ascii=False), json.dumps(embed(chunk)), now()),
        )
    conn.commit()
    conn.close()
    return {
        "file_id": file_id,
        "file_name": file_name,
        "source_type": source_type,
        "source_path": source_path,
        "page_count": len(pages),
        "chunk_count": len(chunk_records),
        "character_count": len(text),
    }


def extract_text_for_rag(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".xlsx":
        parsed = summarize_table(read_xlsx(path), path.name)
        return json.dumps(parsed, ensure_ascii=False)
    if suffix == ".pdf":
        return "\n\n".join(page["text"] for page in extract_pdf_pages_for_rag(path))
    raise ValueError("Supported local RAG files: txt, md, csv, json, xlsx, pdf")


def extract_pdf_pages_for_rag(path: Path) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF RAG ingestion requires the pypdf package to be installed.") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ValueError(f"could not open PDF: {exc}") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError(f"PDF is encrypted and could not be decrypted without a password: {exc}") from exc

    pages: list[dict[str, Any]] = []
    page_errors: list[str] = []
    for page_number, page in enumerate(reader.pages, 1):
        try:
            text = clean(page.extract_text() or "")
        except Exception as exc:
            page_errors.append(f"page {page_number}: {exc}")
            continue
        if text:
            pages.append({"page_number": page_number, "text": text})

    if not pages:
        detail = "; ".join(page_errors[:3])
        if detail:
            detail = f" Extraction errors: {detail}"
        raise ValueError(f"no extractable text found in PDF; scanned/image-only PDFs need OCR.{detail}")
    return pages


def chunk_records_from_pages(pages: list[dict[str, Any]], max_chars: int = 1200, overlap: int = 150) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    chunk_index = 1
    for page in pages:
        page_text = clean(page.get("text"))
        if not page_text:
            continue
        page_chunks = chunk_text(page_text, max_chars=max_chars, overlap=overlap)
        for page_chunk_index, chunk in enumerate(page_chunks, 1):
            records.append(
                {
                    "text": chunk,
                    "metadata": {
                        "page_number": page.get("page_number"),
                        "page_chunk_index": page_chunk_index,
                        "chunk_index": chunk_index,
                    },
                }
            )
            chunk_index += 1
    return records


def bool_payload(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def find_pdf_paths(paths_or_roots: list[Path], recursive: bool) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for root in paths_or_roots:
        if root.is_file():
            candidates = [root] if root.suffix.lower() == ".pdf" else []
        elif root.is_dir():
            candidates = list(root.rglob("*.pdf") if recursive else root.glob("*.pdf"))
        else:
            continue
        for candidate in candidates:
            resolved = str(candidate.resolve())
            if resolved not in seen:
                seen.add(resolved)
                found.append(candidate.resolve())
    found.sort(key=lambda item: str(item).lower())
    return found


def existing_rag_document(agent_root: Path, project_name: str, source_path: str, source_type: str) -> dict[str, Any] | None:
    conn = connect(agent_root)
    row = conn.execute(
        """
        SELECT d.file_id, d.file_name, COUNT(c.id) AS chunk_count
        FROM documents d
        LEFT JOIN document_chunks c ON c.file_id=d.file_id
        WHERE d.project_name=? AND d.source_path=? AND d.source_type=?
        GROUP BY d.file_id, d.file_name
        """,
        (project_name, source_path, source_type),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def ingest_downloaded_pdfs_to_rag(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project_name = clean(payload.get("project_name"))
    if not project_name:
        raise ValueError("project_name is required")

    source_type = clean(payload.get("source_type")) or "paper"
    recursive = bool_payload(payload.get("recursive"), True)
    force = bool_payload(payload.get("force"), False)
    max_files = int(payload.get("max_files") or 200)
    max_chars = int(payload.get("chunk_size") or 1200)
    overlap = int(payload.get("chunk_overlap") or 150)

    explicit_paths = payload.get("pdf_paths") or payload.get("file_paths")
    roots: list[Path] = []
    if isinstance(explicit_paths, list) and explicit_paths:
        roots = [Path(str(path)) for path in explicit_paths if str(path).strip()]
    else:
        pdf_dir = clean(payload.get("pdf_dir") or payload.get("download_dir") or payload.get("download_root"))
        roots = [Path(pdf_dir)] if pdf_dir else [agent_root]

    pdf_paths = find_pdf_paths(roots, recursive=recursive)
    if max_files > 0:
        pdf_paths = pdf_paths[:max_files]

    documents: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for pdf_path in pdf_paths:
        source_path = str(pdf_path.resolve())
        existing = existing_rag_document(agent_root, project_name, source_path, source_type)
        if existing and not force:
            documents.append(
                {
                    "status": "skipped_existing",
                    "file_id": existing["file_id"],
                    "file_name": existing["file_name"],
                    "source_path": source_path,
                    "chunk_count": existing["chunk_count"],
                }
            )
            continue

        try:
            result = ingest_rag_document(
                agent_root,
                {
                    "project_name": project_name,
                    "source_type": source_type,
                    "file_path": source_path,
                    "chunk_size": max_chars,
                    "chunk_overlap": overlap,
                },
            )
            result["status"] = "ingested"
            documents.append(result)
        except Exception as exc:
            failures.append({"file_name": pdf_path.name, "source_path": source_path, "error": str(exc)})

    return {
        "project_name": project_name,
        "source_type": source_type,
        "scan_roots": [str(root.resolve()) if root.exists() else str(root) for root in roots],
        "pdf_count": len(pdf_paths),
        "ingested_count": sum(1 for item in documents if item.get("status") == "ingested"),
        "skipped_count": sum(1 for item in documents if item.get("status") == "skipped_existing"),
        "failed_count": len(failures),
        "documents": documents,
        "failures": failures,
    }


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = clean(text)
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def embed(text: str) -> list[float]:
    vec = [0.0] * VECTOR_SIZE
    for token in tokens_for_vector(text):
        idx = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % VECTOR_SIZE
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def tokens_for_vector(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9\u4e00-\u9fa5]{2,}", text)]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def query_rag(agent_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    question = clean(payload.get("question"))
    if not question:
        raise ValueError("question is required")
    project_name = clean(payload.get("project_name"))
    limit = int(payload.get("limit") or 5)
    qvec = embed(question)
    conn = connect(agent_root)
    rows = conn.execute(
        """
        SELECT c.*, d.project_name
        FROM document_chunks c
        LEFT JOIN documents d ON d.file_id=c.file_id
        WHERE (?='' OR d.project_name=?)
        """,
        (project_name, project_name),
    ).fetchall()
    conn.close()
    scored = []
    for row in rows:
        try:
            vec = json.loads(row["embedding_json"])
        except json.JSONDecodeError:
            continue
        score = cosine(qvec, vec)
        if score > 0:
            metadata = json.loads(row["metadata_json"] or "{}")
            scored.append(
                {
                    "score": score,
                    "file_name": row["file_name"],
                    "chunk_id": row["id"],
                    "page_number": metadata.get("page_number"),
                    "matched_text": row["chunk_text"][:500],
                    "source_type": row["source_type"],
                }
            )
    scored.sort(key=lambda item: item["score"], reverse=True)
    citations = scored[:limit]
    if not citations or citations[0]["score"] < 0.05:
        return {"answer": "No sufficient evidence was found in the local knowledge base.", "citations": []}
    answer = "Based on the local knowledge base, the most relevant evidence is found in: " + "; ".join(f"{c['file_name']} ({c['chunk_id']})" for c in citations[:3])
    return {"answer": answer, "citations": citations}
