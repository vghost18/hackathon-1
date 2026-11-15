"""SQLite persistence primitives for the DocuMind application."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    file_hash TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    storage_path TEXT,
    metadata_json TEXT,
    page_count INTEGER,
    document_type TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    summary TEXT,
    original_extraction_json TEXT,
    corrected_extraction_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    title TEXT NOT NULL DEFAULT 'New conversation',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS extraction_versions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    version_kind TEXT NOT NULL CHECK (version_kind IN ('original', 'corrected')),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS generated_files (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    conversation_id INTEGER,
    file_format TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plugin_executions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    conversation_id INTEGER,
    plugin_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_pages (
    id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, page_number INTEGER NOT NULL,
    native_text TEXT, processing_status TEXT NOT NULL DEFAULT 'pending',
    review_required INTEGER NOT NULL DEFAULT 0, error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(document_id, page_number),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_processing_status
    ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_document_type
    ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_conversations_document_id
    ON conversations(document_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_extraction_versions_document_id
    ON extraction_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_generated_files_document_id
    ON generated_files(document_id);
CREATE INDEX IF NOT EXISTS idx_plugin_executions_document_id
    ON plugin_executions(document_id);
CREATE INDEX IF NOT EXISTS idx_plugin_executions_conversation_id
    ON plugin_executions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_document_pages_document_id ON document_pages(document_id);
"""


def get_connection(database_path: Path) -> sqlite3.Connection:
    """Open a connection with foreign-key enforcement enabled."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path) -> None:
    """Create parent storage and the Phase 1 schema without deleting data."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
