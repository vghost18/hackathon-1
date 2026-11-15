import sqlite3
from pathlib import Path

import pytest

from idp_assistant.db import get_connection, initialize_database


def _table_names(database_path: Path) -> set[str]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row["name"] for row in rows}


def test_initialize_database_creates_schema_in_nested_directory(tmp_path: Path) -> None:
    """A fresh data path must receive the complete persistence foundation."""
    database_path = tmp_path / "nested" / "documind.sqlite3"

    initialize_database(database_path)

    assert database_path.exists()
    assert {
        "documents",
        "conversations",
        "messages",
        "extraction_versions",
        "generated_files",
        "plugin_executions",
    }.issubset(_table_names(database_path))


def test_initialize_database_preserves_existing_rows(tmp_path: Path) -> None:
    """Re-initialization must not erase durable conversation data."""
    database_path = tmp_path / "documind.sqlite3"
    initialize_database(database_path)

    with get_connection(database_path) as connection:
        connection.execute(
            "INSERT INTO conversations (title) VALUES (?)", ("Quarterly review",)
        )
        connection.commit()

    initialize_database(database_path)

    with get_connection(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    assert count == 1


def test_connection_enforces_message_foreign_key(tmp_path: Path) -> None:
    """Messages without a real conversation must be rejected."""
    database_path = tmp_path / "documind.sqlite3"
    initialize_database(database_path)

    with get_connection(database_path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (999, "user", "orphan"),
        )
