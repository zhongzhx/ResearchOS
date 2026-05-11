from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc


def request_text(base_url: str, path: str) -> tuple[int, str]:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=20) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def wait_until_ready(base_url: str, timeout_seconds: int = 20) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            health = request_json(base_url, "GET", "/health")
            if health.get("status") == "ok":
                return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"API did not become ready: {last_error}")


def make_minimal_pdf(path: Path, text_value: str) -> None:
    text = f"BT /F1 18 Tf 72 720 Td ({text_value}) Tj ET".encode("ascii", errors="ignore")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(text)).encode("ascii") + b" >>\nstream\n" + text + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for idx, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{idx} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode("ascii")
    body += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    path.write_bytes(body)


class ClosedLoopRunner:
    def __init__(self, base_url: str, temp_root: Path) -> None:
        self.base_url = base_url
        self.temp_root = temp_root
        self.results: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {}

    def record(self, name: str, ok: bool, detail: str, evidence: dict[str, Any] | None = None) -> None:
        self.results.append({"name": name, "status": "pass" if ok else "fail", "detail": detail, "evidence": evidence or {}})

    def run_step(self, name: str, fn: Any) -> None:
        try:
            evidence = fn()
            self.record(name, True, "passed", evidence if isinstance(evidence, dict) else {"value": evidence})
        except Exception as exc:
            self.record(name, False, str(exc))

    def run(self) -> dict[str, Any]:
        self.run_step("health_and_ui", self.health_and_ui)
        self.run_step("backend_system_prompt_messages", self.backend_system_prompt_messages)
        self.run_step("agent_memory_full_loop", self.agent_memory_full_loop)
        self.run_step("research_interests_weekly_digest", self.research_interests_weekly_digest)
        self.run_step("protocol_to_sop", self.protocol_to_sop)
        self.run_step("failure_log_and_matching", self.failure_log_and_matching)
        self.run_step("peer_review_simulation", self.peer_review_simulation)
        self.run_step("data_parse_to_result_narrative", self.data_parse_to_result_narrative)
        self.run_step("text_rag_ingest_and_query", self.text_rag_ingest_and_query)
        self.run_step("pdf_rag_ingest_and_query", self.pdf_rag_ingest_and_query)
        passed = sum(1 for item in self.results if item["status"] == "pass")
        failed = len(self.results) - passed
        return {
            "summary": {"total": len(self.results), "passed": passed, "failed": failed},
            "results": self.results,
            "state": self.state,
        }

    def health_and_ui(self) -> dict[str, Any]:
        health = request_json(self.base_url, "GET", "/health")
        status, html = request_text(self.base_url, "/ui")
        if health.get("status") != "ok" or status != 200:
            raise AssertionError("health or UI did not pass")
        return {"health": health, "ui_status": status, "ui_length": len(html)}

    def backend_system_prompt_messages(self) -> dict[str, Any]:
        prompt = request_json(self.base_url, "GET", "/agent/system-prompt")
        messages = request_json(
            self.base_url,
            "POST",
            "/agent/messages",
            {
                "user_message": "请基于本地记忆总结实验进展",
                "context": {"file_name": "demo.md", "chunk_id": "c1", "matched_excerpt": "local evidence"},
            },
        )
        if prompt.get("agent_name") != "ResearchOS Agent":
            raise AssertionError("wrong agent prompt")
        if messages["messages"][0]["role"] != "system":
            raise AssertionError("first message is not system")
        return {"prompt_chars": prompt.get("character_count"), "message_count": len(messages["messages"])}

    def agent_memory_full_loop(self) -> dict[str, Any]:
        group = request_json(self.base_url, "POST", "/memory/groups", {"name": "Closed loop lab"})["group"]
        project = request_json(
            self.base_url,
            "POST",
            "/memory/projects",
            {
                "group_id": group["id"],
                "title": "Closed-loop RAW264.7 project",
                "research_question": "Does compound 3 reduce inflammatory readouts?",
                "hypothesis": "Compound 3 reduces LPS-induced inflammatory response.",
                "stage": "pilot",
                "target_output": "manuscript",
            },
        )["project"]
        sample = request_json(
            self.base_url,
            "POST",
            "/memory/samples",
            {"group_id": group["id"], "project_id": project["id"], "sample_code": "C3-B01", "sample_type": "compound", "batch": "B01"},
        )["sample"]
        experiment = request_json(
            self.base_url,
            "POST",
            "/memory/experiments",
            {
                "project_id": project["id"],
                "title": "ELISA TNF-alpha pilot",
                "experiment_type": "ELISA",
                "sample_ids": ["C3-B01", "RAW264.7-P18"],
                "groups": {"control": "LPS only", "treatment": "LPS + compound 3 10 uM"},
                "result_summary": "TNF-alpha showed a decreasing trend; statistics missing.",
                "conclusion": "Preliminary only.",
                "status": "completed",
            },
        )["experiment"]
        data_file = request_json(
            self.base_url,
            "POST",
            "/memory/data-files",
            {
                "project_id": project["id"],
                "experiment_id": experiment["id"],
                "filename": "elisa_tnf_closed_loop.csv",
                "file_type": "csv",
                "columns": ["sample", "group", "TNF_alpha"],
                "parsed_summary": "ELISA TNF-alpha pilot table.",
            },
        )["data_file"]
        old_decision = request_json(
            self.base_url,
            "POST",
            "/memory/create",
            {"project_id": project["id"], "memory_type": "decision_memory", "subject": "animal plan", "content": "Move to animal experiments next."},
        )["memory"]
        new_decision = request_json(
            self.base_url,
            "POST",
            "/memory/create",
            {
                "project_id": project["id"],
                "memory_type": "decision_memory",
                "subject": "animal plan",
                "content": "Superseded: complete cell-only validation before animal work.",
                "supersedes": [old_decision["id"]],
            },
        )["memory"]
        failure = request_json(
            self.base_url,
            "POST",
            "/memory/experiments",
            {
                "project_id": project["id"],
                "title": "Failed qPCR run",
                "experiment_type": "qPCR",
                "sample_ids": ["RAW264.7-P18"],
                "result_summary": "No amplification; RNA QC missing.",
                "conclusion": "Invalid result.",
                "status": "failed",
            },
        )["experiment"]
        request_json(self.base_url, "POST", "/memory/consolidate", {"user_id": "local_user", "project_id": project["id"]})
        retrieved = request_json(
            self.base_url,
            "POST",
            "/memory/retrieve",
            {"user_id": "local_user", "project_id": project["id"], "query": "failed qPCR animal plan C3-B01", "max_results": 10},
        )["memory"]
        context = request_json(
            self.base_url,
            "POST",
            "/memory/context",
            {"user_id": "local_user", "project_id": project["id"], "query": "write manuscript", "max_tokens": 900},
        )["memory_context"]
        view = request_json(self.base_url, "GET", f"/memory/projects/{project['id']}/view")["project_view"]
        if not retrieved or "Relevant Research Memory" not in context or not view:
            raise AssertionError("memory loop did not retrieve/consolidate/contextualize")
        self.state.update({"group_id": group["id"], "project_id": project["id"], "experiment_id": experiment["id"], "sample_id": sample["id"], "data_file_id": data_file["id"]})
        return {
            "project_id": project["id"],
            "experiment_id": experiment["id"],
            "failure_experiment_id": failure["id"],
            "new_decision_id": new_decision["id"],
            "retrieved_count": len(retrieved),
            "context_chars": len(context),
            "view_type": view.get("view_type"),
        }

    def research_interests_weekly_digest(self) -> dict[str, Any]:
        project_name = "closed_loop_project"
        request_json(self.base_url, "POST", "/research-interests", {"project_name": project_name, "keyword": "cell biology", "description": "assay robustness"})
        request_json(self.base_url, "POST", "/research-interests", {"project_name": project_name, "keyword": "machine learning for science", "description": "condition optimization"})
        interests = request_json(self.base_url, "GET", f"/research-interests?project_name={project_name}")["research_interests"]
        digest = request_json(self.base_url, "POST", "/weekly-digest", {"project_name": project_name, "max_items": 4, "language": "zh"})["digest"]
        history = request_json(self.base_url, "GET", f"/weekly-digest?project_name={project_name}&limit=5")["digests"]
        if len(interests) < 2 or not digest.get("items") or not history:
            raise AssertionError("weekly digest loop failed")
        return {"interest_count": len(interests), "digest_items": len(digest["items"]), "history_count": len(history)}

    def protocol_to_sop(self) -> dict[str, Any]:
        methods = "RAW264.7 cells were seeded in 96-well plates and treated with compound 3 at 10 μM for 24 h. LPS-only and vehicle controls were included. TNF-alpha was measured by ELISA at 450 nm."
        protocol = request_json(self.base_url, "POST", "/protocol-extract", {"paper_text": methods, "experiment_type": "ELISA", "language": "zh"})["protocol"]
        sop = request_json(self.base_url, "POST", "/sop-generate", {"experiment_goal": "Generate ELISA validation SOP", "protocol_json": protocol, "language": "zh", "target_format": "markdown"})["sop"]
        if not protocol.get("concentrations") or not sop.get("quality_control_points"):
            raise AssertionError("protocol to SOP loop failed")
        return {"concentration_count": len(protocol.get("concentrations", [])), "sop_qc_count": len(sop.get("quality_control_points", []))}

    def failure_log_and_matching(self) -> dict[str, Any]:
        record = request_json(
            self.base_url,
            "POST",
            "/failure-records",
            {
                "project": "closed_loop_project",
                "title": "Poor qPCR reproducibility",
                "research_field": "cell biology",
                "experiment_type": "qPCR",
                "observed_failure": "No amplification and unstable Ct values.",
                "suspected_causes": ["RNA degradation", "missing QC"],
                "solution_attempted": ["Add RNA integrity check"],
                "tags": ["qPCR", "RNA", "QC"],
            },
        )["failure_record"]
        match = request_json(self.base_url, "POST", "/failure-records/match", {"project": "closed_loop_project", "experimental_plan": "Run qPCR without RNA QC", "limit": 5})
        if not record.get("id") or not match.get("matched_failures"):
            raise AssertionError("failure matching failed")
        return {"record_id": record["id"], "risk_level": match.get("risk_level"), "matches": len(match.get("matched_failures", []))}

    def peer_review_simulation(self) -> dict[str, Any]:
        review = request_json(
            self.base_url,
            "POST",
            "/peer-review",
            {
                "manuscript_text": "Compound 3 reduced TNF-alpha in one ELISA pilot, therefore it fully blocks macrophage inflammation.",
                "review_mode": "hostile_reviewer",
                "research_field": "cell biology",
                "language": "zh",
            },
        )["review"]
        if not review.get("overclaimed_conclusions"):
            raise AssertionError("review did not flag overclaiming")
        return {"major_concerns": len(review.get("major_concerns", [])), "overclaims": len(review.get("overclaimed_conclusions", []))}

    def data_parse_to_result_narrative(self) -> dict[str, Any]:
        csv_text = "sample,group,TNF_alpha\nS1,control,120\nS2,control,125\nS3,treatment,90\nS4,treatment,88\n"
        parsed = request_json(self.base_url, "POST", "/data-parse", {"csv_text": csv_text, "file_name": "tnf.csv"})["parsed_table"]
        narrative = request_json(
            self.base_url,
            "POST",
            "/result-narrative",
            {"data_summary": "Treatment group has lower TNF-alpha values, but no p value is provided.", "parsed_table": parsed, "experiment_type": "ELISA", "target_style": "journal"},
        )["narrative"]
        if parsed.get("row_count") != 4 or not narrative.get("unsupported_claims_to_avoid"):
            raise AssertionError("data parse to narrative failed")
        return {"rows": parsed.get("row_count"), "numeric_columns": parsed.get("numeric_columns"), "conclusion_strength": narrative.get("conclusion_strength")}

    def text_rag_ingest_and_query(self) -> dict[str, Any]:
        doc = request_json(
            self.base_url,
            "POST",
            "/rag/documents",
            {
                "project_name": "closed_loop_project",
                "file_name": "local_note.txt",
                "source_type": "experimental note",
                "text": "Compound 3 ELISA pilot used RAW264.7 cells and LPS-only control. qPCR failed because RNA QC was missing.",
            },
        )["document"]
        query = request_json(self.base_url, "POST", "/rag/query", {"project_name": "closed_loop_project", "question": "Why did qPCR fail?", "limit": 3})
        if not doc.get("chunk_count") or not query.get("citations"):
            raise AssertionError("text RAG failed")
        return {"chunk_count": doc["chunk_count"], "citation_count": len(query["citations"])}

    def pdf_rag_ingest_and_query(self) -> dict[str, Any]:
        pdf_dir = self.temp_root / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / "closed_loop_pdf.pdf"
        make_minimal_pdf(pdf_path, "Closed loop PDF RAG test about RAW264.7 ELISA and compound 3.")
        ingest = request_json(
            self.base_url,
            "POST",
            "/rag/ingest-pdfs",
            {"project_name": "closed_loop_project", "pdf_dir": str(pdf_dir), "recursive": True, "source_type": "paper", "force": True},
        )
        query = request_json(self.base_url, "POST", "/rag/query", {"project_name": "closed_loop_project", "question": "RAW264.7 ELISA compound 3", "limit": 3})
        if ingest.get("ingested_count") != 1 or not query.get("citations"):
            raise AssertionError("PDF RAG failed")
        return {"pdf_count": ingest.get("pdf_count"), "ingested_count": ingest.get("ingested_count"), "citation_count": len(query["citations"])}


def run_closed_loop() -> dict[str, Any]:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    temp = tempfile.TemporaryDirectory()
    temp_root = Path(temp.name)
    script = Path(__file__).resolve().parent / "research_agent_api.py"
    process = subprocess.Popen(
        [
            sys.executable,
            str(script),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--agent-root",
            str(temp_root / "agent_data"),
        ],
        cwd=str(workspace_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_until_ready(base_url)
        runner = ClosedLoopRunner(base_url, temp_root)
        result = runner.run()
        result["server"] = {"base_url": base_url, "agent_root": str(temp_root / "agent_data")}
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        temp.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run closed-loop API tests for the local ResearchOS Agent backend.")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = run_closed_loop()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
