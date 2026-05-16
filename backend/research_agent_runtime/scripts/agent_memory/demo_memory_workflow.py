from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .api import (
    build_memory_context,
    consolidate_memory,
    create_experiment,
    create_group,
    create_memory,
    create_project,
    create_sample,
    register_data_file,
    retrieve_memory,
)


def run_demo(agent_root: Path | None = None) -> dict:
    temp = None
    if agent_root is None:
        temp = tempfile.TemporaryDirectory()
        agent_root = Path(temp.name)

    group = create_group(agent_root, {"name": "Local AI for Science Lab", "description": "Demo experimental research group"})
    project = create_project(
        agent_root,
        {
            "group_id": group["id"],
            "title": "Compound 3 macrophage inflammation project",
            "short_name": "C3 macrophage",
            "research_question": "Does compound 3 reduce LPS-induced inflammatory signaling in RAW264.7 cells?",
            "hypothesis": "Compound 3 reduces inflammatory readouts without strong cytotoxicity.",
            "stage": "pilot validation",
            "target_output": "journal manuscript",
            "target_journals": ["Journal of Ethnopharmacology", "Phytomedicine"],
        },
    )

    samples = [
        create_sample(agent_root, {"group_id": group["id"], "project_id": project["id"], "sample_code": "C3-B01", "sample_type": "compound", "batch": "B01", "current_status": "available"}),
        create_sample(agent_root, {"group_id": group["id"], "project_id": project["id"], "sample_code": "RAW264.7-P18", "sample_type": "cell line", "batch": "P18", "current_status": "in culture"}),
    ]

    experiments = [
        create_experiment(
            agent_root,
            {
                "project_id": project["id"],
                "title": "CCK-8 cytotoxicity pilot",
                "experiment_type": "cell viability assay",
                "date": "2026-04-01",
                "operator": "demo_user",
                "sample_ids": ["C3-B01", "RAW264.7-P18"],
                "groups": {"control": "0.1% DMSO", "treatment": ["2.5 uM", "5 uM", "10 uM"]},
                "result_summary": "No obvious viability loss below 10 uM in the pilot summary.",
                "conclusion": "10 uM is usable for inflammatory readout pilot; needs replicate confirmation.",
                "evidence_strength": "preliminary",
            },
        ),
        create_experiment(
            agent_root,
            {
                "project_id": project["id"],
                "title": "ELISA TNF-alpha pilot",
                "experiment_type": "ELISA",
                "date": "2026-04-05",
                "operator": "demo_user",
                "sample_ids": ["C3-B01", "RAW264.7-P18"],
                "groups": {"control": "LPS only", "treatment": "LPS + compound 3 10 uM"},
                "result_summary": "TNF-alpha trend decreased in treated group; no p value yet.",
                "conclusion": "Preliminary anti-inflammatory trend, statistical support missing.",
                "evidence_strength": "preliminary",
            },
        ),
        create_experiment(
            agent_root,
            {
                "project_id": project["id"],
                "title": "Failed qPCR run",
                "experiment_type": "qPCR",
                "date": "2026-04-08",
                "operator": "demo_user",
                "sample_ids": ["RAW264.7-P18"],
                "result_summary": "No amplification in target gene and reference gene; RNA quality not documented.",
                "conclusion": "Invalid qPCR run; do not interpret expression changes.",
                "status": "failed",
                "evidence_strength": "invalidated",
            },
        ),
    ]

    files = [
        register_data_file(agent_root, {"project_id": project["id"], "experiment_id": experiments[0]["id"], "filename": "cck8_pilot.csv", "file_type": "csv", "columns": ["sample", "group", "absorbance"], "parsed_summary": "CCK-8 pilot absorbance table."}),
        register_data_file(agent_root, {"project_id": project["id"], "experiment_id": experiments[1]["id"], "filename": "elisa_tnf_pilot.xlsx", "file_type": "xlsx", "columns": ["sample", "group", "TNF_alpha_pg_ml"], "parsed_summary": "ELISA TNF-alpha pilot table."}),
    ]

    old_decision = create_memory(agent_root, {"project_id": project["id"], "memory_type": "decision_memory", "subject": "animal experiment plan", "content": "Initial plan considered animal validation next."})
    create_memory(
        agent_root,
        {
            "project_id": project["id"],
            "memory_type": "decision_memory",
            "subject": "animal experiment plan",
            "content": "Decision changed: complete cell-only replicate validation before any animal proposal.",
            "supersedes": [old_decision["id"]],
        },
    )
    create_memory(agent_root, {"project_id": project["id"], "memory_type": "conclusion_memory", "subject": "current conclusion", "content": "Compound 3 has preliminary anti-inflammatory activity, but evidence is not publication-ready.", "evidence_strength": "preliminary"})
    create_memory(agent_root, {"project_id": project["id"], "memory_type": "task_memory", "subject": "next actions", "content": "Repeat ELISA with biological replicates and fix qPCR RNA QC before manuscript writing."})
    create_memory(agent_root, {"project_id": project["id"], "memory_type": "writing_memory", "subject": "style", "content": "Use concise journal style and avoid claiming mechanism before pathway validation."})

    view = consolidate_memory(agent_root, {"user_id": "local_user", "project_id": project["id"]})
    questions = {
        "done": retrieve_memory(agent_root, {"project_id": project["id"], "query": "What has already been done?", "max_results": 8}),
        "files": retrieve_memory(agent_root, {"project_id": project["id"], "query": "What data files are available?", "memory_types": ["dataset_memory"], "max_results": 8}),
        "failures": retrieve_memory(agent_root, {"project_id": project["id"], "query": "What failed experiments should we avoid repeating?", "memory_types": ["failure_memory"], "max_results": 8}),
        "conclusion": retrieve_memory(agent_root, {"project_id": project["id"], "query": "current conclusion", "memory_types": ["conclusion_memory"], "max_results": 8}),
    }
    context = build_memory_context(agent_root, {"user_id": "local_user", "project_id": project["id"], "query": "What should the assistant remember before writing the manuscript?", "max_tokens": 1200})
    result = {"group": group, "project": project, "samples": samples, "experiments": experiments, "files": files, "view": view, "questions": questions, "memory_context": context}
    if temp:
        result["demo_agent_root"] = str(agent_root)
    return result


def main() -> int:
    result = run_demo()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
