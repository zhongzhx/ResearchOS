from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass
class Entity:
    project_name: str
    entity_text: str
    entity_type: str
    field: str
    source_evidence_id: str
    source_path: str
    context: str
    confidence: float


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS domain_entities (
            entity_id TEXT PRIMARY KEY,
            project_name TEXT,
            entity_text TEXT,
            entity_type TEXT,
            field TEXT,
            source_evidence_id TEXT,
            source_path TEXT,
            context TEXT,
            confidence REAL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS domain_relationships (
            relationship_id TEXT PRIMARY KEY,
            project_name TEXT,
            subject_entity TEXT,
            relationship_type TEXT,
            object_entity TEXT,
            field TEXT,
            source_evidence_id TEXT,
            context TEXT,
            confidence REAL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def open_kb(kb_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(kb_root / "research_kb.sqlite")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".csv":
        rows = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(" ".join(clean(v) for v in row.values() if v))
        return "\n".join(rows)
    if path.suffix.lower() == ".json":
        return json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False)
    return path.read_text(encoding="utf-8", errors="replace")


def kb_sources(conn: sqlite3.Connection, project_name: str, limit: int) -> list[tuple[str, str, str]]:
    rows = []
    exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='research_evidence'").fetchone()
    if exists:
        rows.extend(
            (row["evidence_id"], row["source_path"] or "", (row["content_text"] or "")[:20000])
            for row in conn.execute(
                "SELECT evidence_id, source_path, content_text FROM research_evidence WHERE project_name=? ORDER BY updated_at DESC LIMIT ?",
                (project_name, limit),
            ).fetchall()
        )
    if not rows:
        article_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'").fetchone()
        if article_exists:
            rows.extend(
                (row["article_id"], "", f"{row['title'] or ''}. {row['abstract'] or ''}"[:20000])
                for row in conn.execute("SELECT article_id, title, abstract FROM articles LIMIT ?", (limit,)).fetchall()
            )
    return rows


def context_for(text: str, start: int, end: int, width: int = 90) -> str:
    return clean(text[max(0, start - width) : min(len(text), end + width)])


def add_matches(
    entities: list[Entity],
    project_name: str,
    text: str,
    source_id: str,
    source_path: str,
    field: str,
    entity_type: str,
    patterns: Iterable[str],
    confidence: float,
) -> None:
    seen = {(e.entity_text.lower(), e.entity_type, e.source_evidence_id) for e in entities}
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = clean(match.group(0))
            if len(value) < 2:
                continue
            key = (value.lower(), entity_type, source_id)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                Entity(
                    project_name=project_name,
                    entity_text=value,
                    entity_type=entity_type,
                    field=field,
                    source_evidence_id=source_id,
                    source_path=source_path,
                    context=context_for(text, match.start(), match.end()),
                    confidence=confidence,
                )
            )


def extract_from_text(project_name: str, source_id: str, source_path: str, text: str, field: str) -> list[Entity]:
    entities: list[Entity] = []
    selected = {field} if field != "all" else {"bio", "chem", "materials"}
    if "bio" in selected:
        add_matches(entities, project_name, text, source_id, source_path, "bio", "pathway", [r"\bPI3K/AKT\b", r"\bMAPK\b", r"\bNF-?kB\b", r"\bmTOR\b", r"\bp53\b", r"\bWnt\b", r"\bapoptosis\b", r"\bautophagy\b"], 0.82)
        add_matches(entities, project_name, text, source_id, source_path, "bio", "cell_line", [r"\b(?:HeLa|MCF-7|A549|HEK293|RAW264\.7|HCT116|HepG2|Jurkat|U2OS)\b"], 0.9)
        add_matches(entities, project_name, text, source_id, source_path, "bio", "assay", [r"\b(?:qPCR|Western blot|ELISA|MTT|CCK-8|flow cytometry|RNA-seq|ChIP-seq)\b"], 0.88)
        add_matches(entities, project_name, text, source_id, source_path, "bio", "disease", [r"\b[\w -]{0,30}(?:cancer|carcinoma|tumou?r|melanoma|leukemia|inflammation|fibrosis)\b"], 0.65)
        add_matches(entities, project_name, text, source_id, source_path, "bio", "gene_or_protein", [r"\b[A-Z][A-Z0-9]{2,7}\b(?=\s+(?:gene|protein|pathway|expression|activation|inhibition))"], 0.62)
    if "chem" in selected:
        add_matches(entities, project_name, text, source_id, source_path, "chem", "solvent", [r"\b(?:water|ethanol|methanol|DMSO|DMF|acetone|acetonitrile|toluene|chloroform|hexane)\b"], 0.86)
        add_matches(entities, project_name, text, source_id, source_path, "chem", "reaction", [r"\b(?:oxidation|reduction|coupling|substitution|polymerization|hydrolysis|amination|esterification)\b"], 0.78)
        add_matches(entities, project_name, text, source_id, source_path, "chem", "condition", [r"\b\d+(?:\.\d+)?\s?(?:deg C|C|K|h|min|M|mM|uM|pH)\b"], 0.7)
        add_matches(entities, project_name, text, source_id, source_path, "chem", "formula", [r"\b(?:[A-Z][a-z]?\d*){2,}\b"], 0.5)
        add_matches(entities, project_name, text, source_id, source_path, "chem", "catalyst", [r"\b[\w -]{0,30}(?:catalyst|photocatalyst|enzyme catalyst|Pd|Pt|Ni|Cu catalyst)\b"], 0.68)
    if "materials" in selected:
        add_matches(entities, project_name, text, source_id, source_path, "materials", "material", [r"\b(?:perovskite|MOF|COF|polymer|alloy|oxide|sulfide|graphene|nanoparticle|hydrogel|aerogel)\b"], 0.84)
        add_matches(entities, project_name, text, source_id, source_path, "materials", "synthesis_condition", [r"\b(?:annealing|calcination|solvothermal|hydrothermal|spin coating|sputtering|electrodeposition)\b"], 0.8)
        add_matches(entities, project_name, text, source_id, source_path, "materials", "characterization", [r"\b(?:XRD|SEM|TEM|FTIR|Raman|XPS|BET|DSC|TGA|UV-vis)\b"], 0.9)
        add_matches(entities, project_name, text, source_id, source_path, "materials", "performance_metric", [r"\b(?:efficiency|conductivity|capacity|stability|selectivity|yield|tensile strength|band gap)\b"], 0.72)
    return entities


def write_kb(conn: sqlite3.Connection, entities: list[Entity]) -> None:
    for entity in entities:
        entity_id = stable_id(entity.project_name, entity.entity_text.lower(), entity.entity_type, entity.source_evidence_id)
        conn.execute(
            """
            INSERT OR REPLACE INTO domain_entities(
                entity_id, project_name, entity_text, entity_type, field, source_evidence_id,
                source_path, context, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                entity.project_name,
                entity.entity_text,
                entity.entity_type,
                entity.field,
                entity.source_evidence_id,
                entity.source_path,
                entity.context,
                entity.confidence,
                now(),
            ),
        )
    conn.commit()


def write_outputs(output_root: Path, entities: list[Entity]) -> Path:
    run_dir = output_root / f"domain_entities_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "domain_entities.json").write_text(json.dumps([asdict(e) for e in entities], indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "domain_entities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(Entity.__dataclass_fields__.keys()))
        writer.writeheader()
        for entity in entities:
            writer.writerow(asdict(entity))
    lines = ["# Domain Entities", ""]
    for entity in entities[:200]:
        lines.append(f"- [{entity.field}/{entity.entity_type}] {entity.entity_text} ({entity.confidence:.2f})")
    (run_dir / "domain_entities.md").write_text("\n".join(lines), encoding="utf-8")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract biology, chemistry, and materials entities from evidence.")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--input-file", action="append", default=None)
    parser.add_argument("--field", choices=["bio", "chem", "materials", "all"], default="all")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--no-write-kb", action="store_true")
    args = parser.parse_args()

    kb_root = Path(args.kb_root)
    conn = open_kb(kb_root)
    sources: list[tuple[str, str, str]] = []
    for value in args.input_file or []:
        path = Path(value)
        sources.append((stable_id(args.project_name, str(path.resolve())), str(path.resolve()), read_file(path)))
    if not sources:
        sources = kb_sources(conn, clean(args.project_name), args.limit)

    entities: list[Entity] = []
    for source_id, source_path, text in sources:
        entities.extend(extract_from_text(clean(args.project_name), source_id, source_path, text, args.field))
    if not args.no_write_kb:
        write_kb(conn, entities)
    conn.close()

    run_dir = ""
    if args.output_root:
        run_dir = str(write_outputs(Path(args.output_root), entities))
    print(json.dumps({"entity_count": len(entities), "run_dir": run_dir, "kb_root": str(kb_root)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
