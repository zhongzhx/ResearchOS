from __future__ import annotations

import sqlite3
from pathlib import Path


def memory_db(agent_root: Path) -> Path:
    agent_root.mkdir(parents=True, exist_ok=True)
    return agent_root / "agent_memory.sqlite"


def connect(agent_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(memory_db(agent_root), timeout=30)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS research_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_ledger (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            group_id TEXT,
            project_id TEXT,
            experiment_id TEXT,
            timestamp TEXT,
            source_type TEXT,
            source_id TEXT,
            memory_type TEXT NOT NULL,
            subject TEXT,
            content TEXT,
            structured_content_json TEXT,
            entities_json TEXT,
            tags_json TEXT,
            related_file_ids_json TEXT,
            related_sample_ids_json TEXT,
            related_protocol_ids_json TEXT,
            related_memory_ids_json TEXT,
            confidence REAL,
            evidence_strength TEXT,
            stability TEXT,
            valid_from TEXT,
            valid_until TEXT,
            status TEXT,
            supersedes_json TEXT,
            superseded_by TEXT,
            privacy_level TEXT,
            embedding_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_views (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            group_id TEXT,
            project_id TEXT,
            view_type TEXT,
            subject TEXT,
            summary TEXT,
            structured_summary_json TEXT,
            evidence_memory_ids_json TEXT,
            confidence REAL,
            last_consolidated_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            group_id TEXT,
            title TEXT,
            short_name TEXT,
            research_question TEXT,
            hypothesis TEXT,
            status TEXT,
            stage TEXT,
            target_output TEXT,
            target_journals_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            title TEXT,
            experiment_type TEXT,
            date TEXT,
            operator TEXT,
            purpose TEXT,
            design_summary TEXT,
            groups_json TEXT,
            sample_ids_json TEXT,
            protocol_id TEXT,
            raw_data_file_ids_json TEXT,
            processed_data_file_ids_json TEXT,
            result_summary TEXT,
            conclusion TEXT,
            status TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS samples (
            id TEXT PRIMARY KEY,
            group_id TEXT,
            project_id TEXT,
            sample_code TEXT,
            sample_type TEXT,
            name TEXT,
            source TEXT,
            batch TEXT,
            preparation_method TEXT,
            storage_condition TEXT,
            current_status TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS protocols (
            id TEXT PRIMARY KEY,
            group_id TEXT,
            name TEXT,
            version TEXT,
            purpose TEXT,
            materials_json TEXT,
            steps_json TEXT,
            parameters_json TEXT,
            critical_notes TEXT,
            troubleshooting TEXT,
            related_experiment_types_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS data_files (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            group_id TEXT,
            project_id TEXT,
            experiment_id TEXT,
            filename TEXT,
            file_type TEXT,
            path TEXT,
            checksum TEXT,
            upload_time TEXT,
            description TEXT,
            parsed_summary TEXT,
            columns_json TEXT,
            sample_mapping_json TEXT,
            analysis_status TEXT,
            related_memory_ids_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_review_queue (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            group_id TEXT,
            candidate_json TEXT,
            reason TEXT,
            confidence REAL,
            status TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_embeddings (
            id TEXT PRIMARY KEY,
            memory_id TEXT,
            provider TEXT,
            vector_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_ledger(user_id, group_id, project_id, experiment_id);
        CREATE INDEX IF NOT EXISTS idx_memory_type_status ON memory_ledger(memory_type, status);
        CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_ledger(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_views_project ON memory_views(project_id, view_type);
        CREATE INDEX IF NOT EXISTS idx_experiments_project ON experiments(project_id);
        CREATE INDEX IF NOT EXISTS idx_samples_project ON samples(project_id);
        CREATE INDEX IF NOT EXISTS idx_files_project ON data_files(project_id);
        """
    )
    conn.commit()
