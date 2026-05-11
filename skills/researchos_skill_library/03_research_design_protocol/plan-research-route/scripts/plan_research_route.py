from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RouteCandidate:
    name: str
    question: str
    value: str
    feasibility: str
    risk: str
    first_validation: str


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def safe_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    if not text:
        return "research_route"
    if len(text) <= 48:
        return text
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{text[:39]}_{digest}"


def split_csv(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        for item in value.split(","):
            item = clean(item)
            if item:
                result.append(item)
    return result


def infer_field_key(topic: str, field: str) -> str:
    text = f"{topic} {field}".lower()
    if any(word in text for word in ["bio", "medical", "medicine", "cancer", "cell", "gene", "protein", "clinical", "drug"]):
        return "biomedicine"
    if any(word in text for word in ["machine learning", "deep learning", "algorithm", "computer", "model", "dataset", "software"]):
        return "computer_science"
    if any(word in text for word in ["education", "survey", "interview", "social", "policy", "psychology", "management"]):
        return "social_science"
    if any(word in text for word in ["material", "catalyst", "battery", "polymer", "synthesis", "nanoparticle"]):
        return "materials"
    return "general"


def databases(field_key: str) -> list[str]:
    mapping = {
        "biomedicine": ["PubMed", "Web of Science", "Scopus", "ClinicalTrials.gov", "Google Scholar"],
        "computer_science": ["Google Scholar", "Semantic Scholar", "arXiv", "ACM Digital Library", "IEEE Xplore"],
        "social_science": ["Google Scholar", "Web of Science", "Scopus", "ERIC", "SSRN"],
        "materials": ["Web of Science", "Scopus", "Google Scholar", "ScienceDirect", "ACS Publications"],
        "general": ["Google Scholar", "Semantic Scholar", "Web of Science", "Scopus"],
    }
    return mapping.get(field_key, mapping["general"])


def method_blocks(field_key: str, topic: str, available_methods: list[str]) -> dict[str, list[str]]:
    if available_methods:
        method_seed = available_methods
    elif field_key == "biomedicine":
        method_seed = ["systematic literature mapping", "public dataset or database analysis", "mechanism-oriented validation plan"]
    elif field_key == "computer_science":
        method_seed = ["baseline reproduction", "dataset construction or cleaning", "model comparison and ablation"]
    elif field_key == "social_science":
        method_seed = ["conceptual framework", "survey/interview design", "statistical or qualitative analysis"]
    elif field_key == "materials":
        method_seed = ["literature-based material selection", "synthesis or simulation plan", "characterization and comparison"]
    else:
        method_seed = ["literature mapping", "case or data collection", "comparative analysis"]

    return {
        "primary_method": [
            f"Turn '{topic}' into measurable variables or observable phenomena.",
            f"Run the first feasible method: {method_seed[0]}.",
            "Create a small pilot result before expanding the project.",
        ],
        "validation_plan": [
            "Check whether the required data/materials can be obtained within the first two weeks.",
            "Compare against at least one standard baseline or accepted explanation.",
            "Define failure criteria before investing in the full route.",
        ],
        "backup_method": [
            f"If the primary route is blocked, switch to {method_seed[-1]}.",
            "Narrow the research question instead of expanding the workload.",
            "Preserve a thesis-ready output even if the ambitious result is not reached.",
        ],
    }


def keyword_blocks(topic: str, field_key: str) -> dict[str, list[str]]:
    base = [clean(topic)]
    words = [word for word in re.findall(r"[A-Za-z0-9-]{3,}", topic) if len(word) >= 3]
    base.extend(words[:8])

    field_terms = {
        "biomedicine": ["mechanism", "biomarker", "diagnosis", "therapy", "clinical", "pathway"],
        "computer_science": ["benchmark", "dataset", "baseline", "model", "evaluation", "ablation"],
        "social_science": ["framework", "survey", "interview", "effect", "moderator", "policy"],
        "materials": ["synthesis", "characterization", "performance", "mechanism", "stability", "comparison"],
        "general": ["review", "method", "evidence", "application", "limitation", "trend"],
    }
    terms = []
    for item in base + field_terms.get(field_key, field_terms["general"]):
        if item and item.lower() not in [term.lower() for term in terms]:
            terms.append(item)

    return {
        "core_terms": terms[:12],
        "background_block": [topic, "review", "background", "current status"],
        "method_block": [topic, "method", "protocol", "benchmark", "validation"],
        "gap_block": [topic, "limitation", "challenge", "future direction", "unresolved"],
        "application_block": [topic, "application", "translation", "case study", "performance"],
    }


def build_candidates(topic: str, degree: str, field_key: str) -> list[RouteCandidate]:
    degree_text = degree.lower()
    if "doctor" in degree_text or "phd" in degree_text:
        novelty = "requires clear novelty and independent contribution"
    else:
        novelty = "should prioritize feasibility while keeping a visible contribution"

    return [
        RouteCandidate(
            name="Conservative route",
            question=f"What is the current evidence landscape for {topic}, and which methods/results are most reproducible?",
            value="Low-risk route that can support a proposal, thesis chapter, or review section.",
            feasibility=f"High; {novelty}.",
            risk="Novelty may be weak if it stops at summary.",
            first_validation="Collect 30-50 recent papers and build a literature matrix.",
        ),
        RouteCandidate(
            name="Differentiated route",
            question=f"Which specific gap in {topic} can be addressed with a feasible method in this project period?",
            value="Balanced route for a graduate project: literature gap plus executable method.",
            feasibility="Medium; depends on data/material access and supervisor alignment.",
            risk="Scope may become too broad without a strict variable and outcome boundary.",
            first_validation="Select one gap, one method, one evaluation outcome, and test with a pilot.",
        ),
        RouteCandidate(
            name="Ambitious route",
            question=f"Can a new or improved method/framework for {topic} produce stronger evidence than existing approaches?",
            value="Higher novelty route, suitable if time, data, and advisor support are sufficient.",
            feasibility="Lower; should only proceed after the conservative route is secure.",
            risk="May fail due to missing data, weak baseline, or insufficient validation time.",
            first_validation="Define a strict go/no-go checkpoint after the first pilot result.",
        ),
    ]


def monthly_milestones(duration_months: int) -> list[dict[str, str]]:
    labels = [
        "Route confirmation and search strategy",
        "Literature matrix and gap selection",
        "Pilot method and feasibility check",
        "Main method execution",
        "Result analysis and comparison",
        "Writing, revision, and advisor feedback",
        "Extended validation",
        "Manuscript/thesis consolidation",
        "Defense or submission preparation",
    ]
    milestones = []
    for index in range(max(1, duration_months)):
        label = labels[index] if index < len(labels) else "Iteration, writing, and final polishing"
        milestones.append({"month": f"Month {index + 1}", "milestone": label})
    return milestones


def build_route(args: argparse.Namespace) -> dict[str, Any]:
    topic = clean(args.topic)
    field = clean(args.field)
    degree = clean(args.degree)
    constraints = split_csv(args.constraint)
    available_data = split_csv(args.available_data)
    available_methods = split_csv(args.available_method)
    expected_outputs = split_csv(args.expected_output) or ["proposal", "literature matrix", "method plan", "advisor summary"]
    field_key = infer_field_key(topic, field)

    route = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_name": clean(args.project_name) or safe_slug(topic),
        "topic": topic,
        "field": field or field_key,
        "field_key": field_key,
        "degree": degree,
        "duration_months": args.duration_months,
        "background": clean(args.background),
        "constraints": constraints,
        "available_data": available_data,
        "available_methods": available_methods,
        "expected_outputs": expected_outputs,
        "scope": {
            "in_scope": [
                f"Clarify the research gap around {topic}.",
                "Build an evidence-backed literature matrix.",
                "Run the smallest feasible method or pilot that can validate the route.",
            ],
            "out_of_scope": [
                "Claims not supported by collected literature or user-owned data.",
                "Full-scale experiments before feasibility is confirmed.",
                "Unapproved human/animal/clinical/restricted-data work.",
            ],
            "needs_validation": [
                "Whether the selected gap is novel enough.",
                "Whether data/materials are accessible.",
                "Whether the advisor accepts the chosen method boundary.",
            ],
        },
        "research_question_candidates": [asdict(item) for item in build_candidates(topic, degree, field_key)],
        "literature_route": {
            "databases": databases(field_key),
            "keyword_blocks": keyword_blocks(topic, field_key),
            "screening_rules": [
                "Prefer recent review papers first, then high-quality method papers, then latest applications.",
                "Exclude papers that only mention the topic without method/result relevance.",
                "Separate background papers, method papers, benchmark/comparison papers, and conflicting evidence.",
            ],
            "review_matrix_columns": [
                "title",
                "year",
                "research question",
                "data/materials",
                "method",
                "main result",
                "limitation",
                "how it helps this project",
            ],
        },
        "method_route": method_blocks(field_key, topic, available_methods),
        "first_month_plan": [
            {"week": "Week 1", "task": "Confirm topic boundary, build first keyword groups, collect 10 seed papers."},
            {"week": "Week 2", "task": "Expand to 30-50 papers, classify background/method/result/gap."},
            {"week": "Week 3", "task": "Choose one conservative and one differentiated route; check data/material feasibility."},
            {"week": "Week 4", "task": "Prepare advisor summary, decide go/no-go route, start pilot."},
        ],
        "monthly_milestones": monthly_milestones(args.duration_months),
        "risk_register": [
            {
                "risk": "Topic is too broad",
                "signal": "Search results are scattered and no stable variables appear.",
                "mitigation": "Narrow to one population/material/system, one method, and one outcome.",
                "decision_point": "End of Week 2",
            },
            {
                "risk": "Novelty is weak",
                "signal": "Recent papers already answer the same question with similar methods.",
                "mitigation": "Shift contribution to comparison, context, validation, or a narrower gap.",
                "decision_point": "Week 3 advisor meeting",
            },
            {
                "risk": "Data/materials unavailable",
                "signal": "No accessible dataset, sample, equipment, or permission.",
                "mitigation": "Use public data, literature-based analysis, simulation, or a smaller pilot.",
                "decision_point": "Before main method execution",
            },
            {
                "risk": "Compliance or ethics blocker",
                "signal": "Human subjects, animal work, clinical data, restricted data, or dangerous procedures are involved.",
                "mitigation": "Pause execution and confirm institutional approval requirements.",
                "decision_point": "Before any data collection or experiment",
            },
        ],
        "advisor_summary": [
            f"Topic: {topic}",
            f"Recommended route: start conservative, then move to differentiated route after literature and feasibility validation.",
            "This week: build literature matrix, confirm scope boundary, and prepare two route options for advisor decision.",
            "Key decision needed from advisor: acceptable novelty level, available data/materials, and preferred method boundary.",
        ],
        "next_7_days": [
            "Write one paragraph defining the research object and outcome.",
            "Run the first search using the background/method/gap keyword blocks.",
            "Read 5 review papers and 5 method papers.",
            "Create a literature matrix with at least 10 rows.",
            "Schedule an advisor checkpoint with two route options.",
        ],
    }
    return route


def markdown(route: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.extend(
        [
            "# Research Route Plan",
            "",
            f"- Topic: {route['topic']}",
            f"- Field: {route['field']}",
            f"- Degree: {route['degree']}",
            f"- Duration: {route['duration_months']} months",
            f"- Created at: {route['created_at']}",
            "",
            "## Scope",
            "",
            "In scope:",
        ]
    )
    lines.extend(f"- {item}" for item in route["scope"]["in_scope"])
    lines.append("")
    lines.append("Out of scope:")
    lines.extend(f"- {item}" for item in route["scope"]["out_of_scope"])
    lines.append("")
    lines.append("Needs validation:")
    lines.extend(f"- {item}" for item in route["scope"]["needs_validation"])

    lines.extend(["", "## Research Question Candidates", ""])
    for item in route["research_question_candidates"]:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- Question: {item['question']}",
                f"- Value: {item['value']}",
                f"- Feasibility: {item['feasibility']}",
                f"- Risk: {item['risk']}",
                f"- First validation: {item['first_validation']}",
                "",
            ]
        )

    literature = route["literature_route"]
    lines.extend(["## Literature Route", "", "Databases:"])
    lines.extend(f"- {item}" for item in literature["databases"])
    lines.extend(["", "Keyword blocks:"])
    for name, values in literature["keyword_blocks"].items():
        lines.append(f"- {name}: {', '.join(values)}")
    lines.extend(["", "Screening rules:"])
    lines.extend(f"- {item}" for item in literature["screening_rules"])
    lines.extend(["", "Review matrix columns:"])
    lines.append(", ".join(literature["review_matrix_columns"]))

    method = route["method_route"]
    lines.extend(["", "## Method Route", "", "Primary method:"])
    lines.extend(f"- {item}" for item in method["primary_method"])
    lines.extend(["", "Validation plan:"])
    lines.extend(f"- {item}" for item in method["validation_plan"])
    lines.extend(["", "Backup method:"])
    lines.extend(f"- {item}" for item in method["backup_method"])

    lines.extend(["", "## First Month Plan", ""])
    for item in route["first_month_plan"]:
        lines.append(f"- {item['week']}: {item['task']}")
    lines.extend(["", "## Monthly Milestones", ""])
    for item in route["monthly_milestones"]:
        lines.append(f"- {item['month']}: {item['milestone']}")

    lines.extend(["", "## Risk Register", ""])
    for item in route["risk_register"]:
        lines.extend(
            [
                f"### {item['risk']}",
                f"- Signal: {item['signal']}",
                f"- Mitigation: {item['mitigation']}",
                f"- Decision point: {item['decision_point']}",
                "",
            ]
        )

    lines.extend(["## Advisor Summary", ""])
    lines.extend(f"- {item}" for item in route["advisor_summary"])
    lines.extend(["", "## Next 7 Days", ""])
    lines.extend(f"- {item}" for item in route["next_7_days"])
    lines.extend(["", "## Boundary", "", "This route is a planning draft. Confirm novelty, feasibility, and compliance with literature evidence and advisor feedback before execution."])
    return "\n".join(lines)


def write_outputs(route: dict[str, Any], output_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"research_route_{stamp}_{safe_slug(route['topic'])}"
    run_dir.mkdir(parents=True, exist_ok=False)

    (run_dir / "research_route.json").write_text(json.dumps(route, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "research_route.md").write_text(markdown(route), encoding="utf-8")
    (run_dir / "advisor_summary.md").write_text(
        "# Advisor Summary\n\n" + "\n".join(f"- {item}" for item in route["advisor_summary"]) + "\n",
        encoding="utf-8",
    )

    keyword_lines = []
    for name, values in route["literature_route"]["keyword_blocks"].items():
        keyword_lines.append(f"[{name}]")
        keyword_lines.extend(values)
        keyword_lines.append("")
    (run_dir / "search_queries.txt").write_text("\n".join(keyword_lines), encoding="utf-8")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Design a graduate research route from a broad topic.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--field", default="general")
    parser.add_argument("--degree", default="master")
    parser.add_argument("--duration-months", type=int, default=6)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--project-name", default="")
    parser.add_argument("--background", default="")
    parser.add_argument("--constraint", action="append", default=None)
    parser.add_argument("--available-data", action="append", default=None)
    parser.add_argument("--available-method", action="append", default=None)
    parser.add_argument("--expected-output", action="append", default=None)
    args = parser.parse_args()

    if args.duration_months < 1:
        raise SystemExit("--duration-months must be at least 1")

    route = build_route(args)
    run_dir = write_outputs(route, Path(args.output_root))
    print(f"Run folder: {run_dir}")
    print(json.dumps({"run_dir": str(run_dir), "topic": route["topic"], "field_key": route["field_key"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
