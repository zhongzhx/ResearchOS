from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


STOPWORDS = {
    "about", "above", "across", "after", "again", "against", "also", "although", "among", "and",
    "another", "are", "article", "available", "because", "been", "before", "being", "between",
    "both", "can", "copyright", "could", "data", "during", "each", "elsevier", "et", "figure",
    "for", "from", "further", "have", "having", "here", "however", "into", "journal", "license",
    "may", "more", "most", "not", "other", "our", "paper", "permission", "plos", "published",
    "publisher", "rights", "reserved", "show", "shown", "study", "such", "supplementary",
    "table", "than", "that", "the", "their", "there", "these", "this", "those", "through",
    "using", "was", "were", "when", "where", "which", "while", "with", "within", "without",
    "would", "www",
}

SECTION_LABELS = {
    "background": "background",
    "objective": "background",
    "objectives": "background",
    "aim": "background",
    "aims": "background",
    "introduction": "background",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "design": "methods",
    "setting": "methods",
    "participants": "methods",
    "interventions": "methods",
    "results": "results",
    "findings": "results",
    "outcomes": "results",
    "conclusions": "conclusion",
    "conclusion": "conclusion",
    "interpretation": "conclusion",
}

METHOD_CUES = {
    "we used", "we performed", "we conducted", "we analyzed", "we analysed", "we evaluated",
    "we compared", "we assessed", "we measured", "we developed", "we tested", "randomized",
    "cohort", "cross-sectional", "case-control", "trial", "survey", "assay", "sequencing",
    "model", "models", "regression", "method", "methods", "participants", "samples",
}

RESULT_CUES = {
    "we found", "results showed", "showed that", "revealed", "increased", "decreased",
    "associated with", "significantly", "higher", "lower", "improved", "reduced", "led to",
    "indicated", "demonstrated", "observed", "identified", "resulted",
}

BACKGROUND_CUES = {
    "is unknown", "remain unclear", "limited", "important", "aim", "objective", "investigate",
    "understand", "need", "challenge", "background", "purpose",
}


@dataclass
class ArticleSource:
    source_type: str
    path: str
    doi: str = ""
    title: str = ""
    journal: str = ""
    publication_date: str = ""
    keyword_query: str = ""
    abstract: str = ""


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


def clean_markup(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def usable_abstract(text: str) -> bool:
    text = clean_markup(text)
    if len(text) < 80:
        return False
    if len(split_sentences(text)) < 2 and len(text.split()) < 25:
        return False
    return True


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def resolve_output_path(output_path: str, run_root: Path) -> Path | None:
    raw = Path(output_path)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend([raw, run_root / raw, run_root / "downloads" / raw.name])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def row_to_source(row: dict[str, str], source_type: str, path: str) -> ArticleSource:
    return ArticleSource(
        source_type=source_type,
        path=path,
        doi=row.get("doi", ""),
        title=row.get("title", ""),
        journal=row.get("journal", ""),
        publication_date=row.get("publication_date", ""),
        keyword_query=row.get("keyword_query") or row.get("query", ""),
        abstract=clean_markup(row.get("abstract", "")),
    )


def first_downloaded_from_run(run_root: Path) -> ArticleSource | None:
    access_log = run_root / "access_log.csv"
    if access_log.exists():
        for row in read_csv_rows(access_log):
            output_path = (row.get("output_path") or "").strip()
            if row.get("status") == "downloaded" and output_path:
                path = resolve_output_path(output_path, run_root)
                if path and path.exists():
                    return row_to_source(row, "downloaded_file", str(path))

    candidates = run_root / "keyword_candidates.csv"
    if candidates.exists():
        rows = read_csv_rows(candidates)
        if rows:
            return row_to_source(rows[0], "metadata_fallback", str(candidates))
    return None


def first_from_candidate_csv(path: Path) -> ArticleSource:
    rows = read_csv_rows(path)
    if not rows:
        raise ValueError(f"No rows found in candidate CSV: {path}")
    return row_to_source(rows[0], "metadata_fallback", str(path))


def source_from_record_json(path: Path) -> ArticleSource:
    record = json.loads(path.read_text(encoding="utf-8"))
    file_path = record.get("output_path") or record.get("path") or str(path)
    source_type = "downloaded_file" if record.get("output_path") else record.get("source_type", "metadata_fallback")
    return ArticleSource(
        source_type=source_type,
        path=file_path,
        doi=record.get("doi", ""),
        title=record.get("title", ""),
        journal=record.get("journal", ""),
        publication_date=record.get("publication_date", ""),
        keyword_query=record.get("keyword_query") or record.get("query", ""),
        abstract=clean_markup(record.get("abstract", "")),
    )


def read_html_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    parser = TextHTMLParser()
    parser.feed(raw)
    return clean_markup(parser.text())


def read_plain_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_pdf_text(path: Path) -> tuple[str, str]:
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
        if text.strip():
            return text, "pypdf"
    except Exception:
        pass

    try:
        import PyPDF2  # type: ignore

        reader = PyPDF2.PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
        if text.strip():
            return text, "PyPDF2"
    except Exception:
        pass

    try:
        from pdfminer.high_level import extract_text  # type: ignore

        text = extract_text(str(path), maxpages=20)
        if text.strip():
            return text, "pdfminer.six"
    except Exception:
        pass

    return "", "pdf_text_unavailable"


def extract_abstract_from_full_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text)
    match = re.search(
        r"\bAbstract\b\s*(.*?)(?:\bIntroduction\b|\bBackground\b|\bKeywords\b|\bMethods\b|\bMaterials and Methods\b)",
        normalized,
        flags=re.I,
    )
    if match:
        candidate = clean_markup(match.group(1))
        if 120 <= len(candidate) <= 5000:
            return candidate
    return ""


def read_article_text(source: ArticleSource) -> tuple[str, str, str]:
    metadata_text = " ".join(
        part for part in [source.keyword_query, source.title, source.journal, source.doi] if part
    )
    if source.abstract and usable_abstract(source.abstract):
        return source.abstract, "abstract_from_metadata", metadata_text

    if source.source_type == "metadata_fallback":
        return metadata_text, "metadata_fallback_no_abstract", metadata_text

    path = Path(source.path)
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm", ".xml"}:
        full_text = read_html_text(path)
        abstract = extract_abstract_from_full_text(full_text)
        if abstract:
            return abstract, "abstract_from_html_xml", metadata_text
        if len(tokenize(full_text)) >= 80:
            return full_text[:5000], "full_text_html_xml_no_abstract", metadata_text
        return metadata_text, "metadata_fallback_no_usable_abstract", metadata_text
    if suffix in {".txt", ".md"}:
        full_text = read_plain_text(path)
        abstract = extract_abstract_from_full_text(full_text)
        if abstract:
            return abstract, "abstract_from_plain_text", metadata_text
        if len(tokenize(full_text)) >= 80:
            return full_text[:5000], "full_text_plain_no_abstract", metadata_text
        return metadata_text, "metadata_fallback_no_usable_abstract", metadata_text
    if suffix == ".pdf":
        full_text, method = read_pdf_text(path)
        if full_text.strip():
            abstract = extract_abstract_from_full_text(full_text)
            if abstract:
                return abstract, f"abstract_from_pdf:{method}", metadata_text
            return full_text[:5000], f"full_text_pdf_no_abstract:{method}", metadata_text
        return metadata_text, "metadata_fallback_pdf_text_unavailable", metadata_text

    try:
        full_text = read_plain_text(path)
        return full_text[:5000], "full_text_unknown_as_text", metadata_text
    except Exception:
        return metadata_text, "metadata_fallback_unreadable_file", metadata_text


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", clean_markup(text))
    return [part.strip() for part in parts if len(part.strip()) >= 30]


def parse_structured_abstract(text: str) -> dict[str, list[str]]:
    sections = {"background": [], "methods": [], "results": [], "conclusion": []}
    pattern = re.compile(
        r"\b(Background|Objective|Objectives|Aim|Aims|Introduction|Methods|Method|Materials and Methods|Design|Setting|Participants|Interventions|Results|Findings|Outcomes|Conclusion|Conclusions|Interpretation)\s*[:.-]\s*",
        flags=re.I,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return sections
    for i, match in enumerate(matches):
        label = SECTION_LABELS.get(match.group(1).lower(), "")
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if label and chunk:
            sections[label].extend(split_sentences(chunk) or [chunk])
    return sections


def classify_sentence(sentence: str, index: int, total: int) -> str:
    lowered = sentence.lower()
    if any(cue in lowered for cue in METHOD_CUES):
        return "methods"
    if any(cue in lowered for cue in RESULT_CUES):
        return "results"
    if any(cue in lowered for cue in BACKGROUND_CUES):
        return "background"
    if index >= max(total - 2, 0) and re.search(r"\b(conclude|suggest|indicate|therefore|overall|in summary)\b", lowered):
        return "conclusion"
    if index <= max(total // 3, 1):
        return "background"
    if index >= max(total - 2, 0):
        return "conclusion"
    return "results"


def section_abstract(text: str) -> dict[str, list[str]]:
    sections = parse_structured_abstract(text)
    if any(sections.values()):
        return sections

    sentences = split_sentences(text)
    total = len(sentences)
    for index, sentence in enumerate(sentences):
        sections[classify_sentence(sentence, index, total)].append(sentence)
    return sections


def summarize_sections(sections: dict[str, list[str]]) -> dict[str, str]:
    return {name: " ".join(sentences[:3]).strip() for name, sentences in sections.items()}


def normalize_text(text: str) -> str:
    text = clean_markup(text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\bdoi\s*:\s*\S+", " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z0-9-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def looks_noisy_token(token: str) -> bool:
    if token in STOPWORDS:
        return True
    if any(char.isdigit() for char in token) and "-" in token:
        return True
    if len(token) > 32:
        return True
    if token.count("-") > 1:
        return True
    return False


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text):
        low = token.lower().strip("-")
        if len(low) < 3 or looks_noisy_token(low):
            continue
        tokens.append(low)
    return tokens


def candidate_phrases(tokens: list[str], min_n: int = 2, max_n: int = 5) -> Counter[str]:
    counts: Counter[str] = Counter()
    trimmed = tokens[:2500]
    for n in range(min_n, max_n + 1):
        for i in range(0, len(trimmed) - n + 1):
            phrase_tokens = trimmed[i : i + n]
            if any(looks_noisy_token(token) for token in phrase_tokens):
                continue
            if len(set(phrase_tokens)) == 1:
                continue
            counts[" ".join(phrase_tokens)] += 1
    return counts


def score_terms(section_text: dict[str, str], metadata_text: str) -> list[dict[str, Any]]:
    weights = {"background": 1.1, "methods": 1.25, "results": 1.35, "conclusion": 1.15}
    weighted: Counter[str] = Counter()
    raw: Counter[str] = Counter()
    metadata_tokens = set(tokenize(metadata_text))
    for section, text in section_text.items():
        tokens = tokenize(text)
        raw.update(tokens)
        for token in tokens:
            weighted[token] += weights.get(section, 1.0)
    rows = []
    total = max(sum(raw.values()), 1)
    for term, score_count in weighted.items():
        count = raw[term]
        specificity = math.log((total + 3) / (count + 1), 10)
        score = score_count * (1.0 + specificity)
        if term in metadata_tokens:
            score *= 1.35
        if len(term) <= 3:
            score *= 0.7
        rows.append({"term": term, "count": count, "score": round(score, 4)})
    rows.sort(key=lambda row: (-row["score"], row["term"]))
    return rows


def score_phrases(section_text: dict[str, str], metadata_text: str) -> list[dict[str, Any]]:
    weights = {"background": 1.1, "methods": 1.25, "results": 1.35, "conclusion": 1.15}
    phrase_scores: Counter[str] = Counter()
    phrase_counts: Counter[str] = Counter()
    metadata = " ".join(tokenize(metadata_text))
    for section, text in section_text.items():
        section_phrases = candidate_phrases(tokenize(text))
        for phrase, count in section_phrases.items():
            phrase_counts[phrase] += count
            phrase_scores[phrase] += count * weights.get(section, 1.0)

    rows = []
    for phrase, score_count in phrase_scores.items():
        words = phrase.split()
        if len(words) < 2:
            continue
        metadata_bonus = 1.25 if phrase in metadata else 1.0
        score = score_count * (len(words) ** 1.1) * metadata_bonus
        rows.append({"phrase": phrase, "count": phrase_counts[phrase], "score": round(score, 4)})
    rows.sort(key=lambda row: (-row["score"], row["phrase"]))
    return rows


def build_queries(primary_terms: list[str], phrases: list[str], original_query: str) -> list[str]:
    anchors = phrases[:10] + primary_terms[:10]
    queries: list[str] = []
    if original_query:
        for phrase in anchors[:8]:
            queries.append(f'{original_query} "{phrase}"')
    for i in range(0, min(len(anchors), 12), 2):
        if i + 1 < len(anchors):
            queries.append(f'"{anchors[i]}" "{anchors[i + 1]}"')
    for phrase in phrases[:8]:
        queries.append(f'"{phrase}"')

    deduped = []
    seen = set()
    for query in queries:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(query)
    return deduped[:20]


def analyze_abstract(text: str, metadata_text: str, original_query: str, top_n: int) -> dict[str, Any]:
    sections = summarize_sections(section_abstract(text))
    section_text = {name: value for name, value in sections.items() if value}
    if not section_text:
        section_text = {"background": text}

    term_rows = score_terms(section_text, metadata_text)
    phrase_rows = score_phrases(section_text, metadata_text)
    primary_terms = [row["term"] for row in term_rows[:top_n]]
    keyphrases = [row["phrase"] for row in phrase_rows[:top_n]]

    return {
        "abstract_summary": sections,
        "primary_keywords": term_rows[:top_n],
        "keyphrases": phrase_rows[:top_n],
        "search_queries": build_queries(primary_terms, keyphrases, original_query),
        "include_terms": (keyphrases[:12] + primary_terms[:12])[:24],
        "exclude_terms": ["review", "editorial", "correction", "comment", "protocol", "retraction"],
        "token_count": len(tokenize(text)),
        "text_character_count": len(text),
    }


def safe_slug(value: str, fallback: str = "article") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return (text[:80] or fallback).strip("_")


def short_article_id(source: ArticleSource) -> str:
    value = source.doi or source.title or source.path
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return digest


def write_outputs(output_root: Path, source: ArticleSource, text_mode: str, result: dict[str, Any]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    article_id = short_article_id(source)
    run_dir = output_root / f"article_abstract_{stamp}_{article_id}"
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = {"source": source.__dict__, "text_mode": text_mode, "result": result}
    (run_dir / "article_abstract_analysis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with (run_dir / "article_abstract_analysis.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["kind", "section", "value", "count", "score"])
        for section, summary in result["abstract_summary"].items():
            writer.writerow(["summary", section, summary, "", ""])
        for row in result["primary_keywords"]:
            writer.writerow(["keyword", "", row["term"], row["count"], row["score"]])
        for row in result["keyphrases"]:
            writer.writerow(["keyphrase", "", row["phrase"], row["count"], row["score"]])
        for query in result["search_queries"]:
            writer.writerow(["search_query", "", query, "", ""])
        for term in result["include_terms"]:
            writer.writerow(["include_term", "", term, "", ""])
        for term in result["exclude_terms"]:
            writer.writerow(["exclude_term", "", term, "", ""])

    (run_dir / "next_search_terms.txt").write_text("\n".join(result["search_queries"]) + "\n", encoding="utf-8")

    lines = [
        "# First Article Abstract Report",
        "",
        f"- Source type: {source.source_type}",
        f"- Text mode: {text_mode}",
        f"- Article file/table: {source.path}",
        f"- DOI: {source.doi or 'not available'}",
        f"- Title: {source.title or 'not available'}",
        f"- Journal: {source.journal or 'not available'}",
        f"- Token count: {result['token_count']}",
        "",
        "## Background",
        "",
        result["abstract_summary"].get("background") or "Not detected.",
        "",
        "## Methods",
        "",
        result["abstract_summary"].get("methods") or "Not detected.",
        "",
        "## Results",
        "",
        result["abstract_summary"].get("results") or "Not detected.",
        "",
        "## Conclusion",
        "",
        result["abstract_summary"].get("conclusion") or "Not detected.",
        "",
        "## Search Queries",
        "",
    ]
    lines.extend(f"- {query}" for query in result["search_queries"])
    lines.extend(["", "## Keyphrases", ""])
    lines.extend(f"- {row['phrase']} ({row['count']})" for row in result["keyphrases"][:20])
    lines.extend(["", "## Primary Keywords", ""])
    lines.extend(f"- {row['term']} ({row['count']})" for row in result["primary_keywords"][:20])
    lines.extend(["", "## Include Terms", ""])
    lines.extend(f"- {term}" for term in result["include_terms"])
    lines.extend(["", "## Exclude Hints", ""])
    lines.extend(f"- {term}" for term in result["exclude_terms"])
    (run_dir / "article_abstract_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_dir


def append_summary(summary_path: Path, source: ArticleSource, text_mode: str, result: dict[str, Any], report_dir: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    exists = summary_path.exists()
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "doi": source.doi,
        "title": source.title,
        "journal": source.journal,
        "publication_date": source.publication_date,
        "keyword_query": source.keyword_query,
        "source_type": source.source_type,
        "text_mode": text_mode,
        "background": result["abstract_summary"].get("background", ""),
        "methods": result["abstract_summary"].get("methods", ""),
        "results": result["abstract_summary"].get("results", ""),
        "conclusion": result["abstract_summary"].get("conclusion", ""),
        "top_keywords": "; ".join(row["term"] for row in result["primary_keywords"][:10]),
        "top_keyphrases": "; ".join(row["phrase"] for row in result["keyphrases"][:10]),
        "top_search_queries": " | ".join(result["search_queries"][:5]),
        "report_dir": str(report_dir),
    }
    with summary_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def choose_source(args: argparse.Namespace) -> ArticleSource:
    if args.record_json:
        return source_from_record_json(Path(args.record_json))
    if args.run_root:
        source = first_downloaded_from_run(Path(args.run_root))
        if source:
            return source
        raise ValueError(f"No downloaded article or candidate table found in run root: {args.run_root}")
    if args.article_file:
        return ArticleSource(source_type="article_file", path=str(Path(args.article_file)))
    if args.candidate_csv:
        return first_from_candidate_csv(Path(args.candidate_csv))
    raise ValueError("Provide --run-root, --article-file, or --candidate-csv.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize one article abstract and extract search-expansion terms.")
    parser.add_argument("--record-json", help="Single article record JSON with title, abstract, DOI, and optional output_path.")
    parser.add_argument("--run-root", help="Run folder containing access_log.csv and/or keyword_candidates.csv.")
    parser.add_argument("--article-file", help="Direct article file path: PDF, HTML, XML, TXT, or MD.")
    parser.add_argument("--candidate-csv", help="Candidate CSV to use when no full-text file is available.")
    parser.add_argument("--output-root", required=True, help="Parent folder for keyword extraction outputs.")
    parser.add_argument("--top-n", type=int, default=30, help="Number of top keywords/keyphrases to save.")
    parser.add_argument("--original-query", default="", help="Original user query to blend into next search queries.")
    parser.add_argument("--append-summary", help="Append a one-row article summary to this CSV.")
    args = parser.parse_args()

    try:
        source = choose_source(args)
        if args.original_query and not source.keyword_query:
            source.keyword_query = args.original_query
        text, text_mode, metadata_text = read_article_text(source)
        if not text.strip():
            raise ValueError("No abstract, article text, or metadata available for extraction.")
        result = analyze_abstract(text, metadata_text, source.keyword_query or args.original_query, args.top_n)
        run_dir = write_outputs(Path(args.output_root), source, text_mode, result)
        if args.append_summary:
            append_summary(Path(args.append_summary), source, text_mode, result, run_dir)
    except Exception as exc:
        print(f"Keyword extraction failed: {exc}", file=sys.stderr)
        return 1

    print(f"Output folder: {run_dir}")
    print(f"Text mode: {text_mode}")
    print(f"Top search query: {result['search_queries'][0] if result['search_queries'] else 'none'}")
    print(f"Article report: {run_dir / 'article_abstract_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
