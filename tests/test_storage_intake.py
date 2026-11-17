from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from idp_assistant.db import initialize_database
from idp_assistant.storage import DocumentError, ingest_document


def _make_pdf(text: str = "hello world") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_encrypted_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "protected")
    data = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    doc.close()
    return data


def test_ingest_valid_native_pdf_generates_id_and_hash(tmp_path: Path) -> None:
    database_path = tmp_path / "documind.sqlite3"
    data_dir = tmp_path / "data"
    initialize_database(database_path)

    content = _make_pdf("native content")
    doc, duplicate = ingest_document(database_path, data_dir, "resume.pdf", content)

    assert duplicate is False
    assert doc["id"] > 0
    assert doc["file_hash"]
    assert len(doc["file_hash"]) == 64
    assert doc["filename"] == "resume.pdf"
    assert doc["page_count"] >= 1


def test_ingest_rejects_renamed_non_pdf_with_clear_signature_error(tmp_path: Path) -> None:
    database_path = tmp_path / "documind.sqlite3"
    data_dir = tmp_path / "data"
    initialize_database(database_path)

    fake_pdf_content = b"this is not a real pdf"

    with pytest.raises(DocumentError) as exc:
        ingest_document(database_path, data_dir, "fake.pdf", fake_pdf_content)

    message = str(exc.value).lower()
    assert "signature" in message or "not a valid pdf" in message


def test_ingest_rejects_pdf_above_page_limit_with_limit_message(tmp_path: Path) -> None:
    database_path = tmp_path / "documind.sqlite3"
    data_dir = tmp_path / "data"
    initialize_database(database_path)

    doc = fitz.open()
    for i in range(11):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    over_limit_pdf = doc.tobytes()
    doc.close()

    with pytest.raises(DocumentError) as exc:
        ingest_document(database_path, data_dir, "large.pdf", over_limit_pdf)

    message = str(exc.value).lower()
    assert "page limit" in message
    assert "10" in message


def test_ingest_password_protected_pdf_is_reported_gracefully(tmp_path: Path) -> None:
    database_path = tmp_path / "documind.sqlite3"
    data_dir = tmp_path / "data"
    initialize_database(database_path)

    protected_pdf = _make_encrypted_pdf()

    with pytest.raises(DocumentError) as exc:
        ingest_document(database_path, data_dir, "protected.pdf", protected_pdf)

    message = str(exc.value).lower()
    assert "password" in message or "protected" in message
