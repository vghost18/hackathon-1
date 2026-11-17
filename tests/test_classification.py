from __future__ import annotations

from idp_assistant.intelligence import _canonical_doc_type, _normalize_extraction


def _sample_value(document_type: str) -> dict:
    return {
        "document_type": document_type,
        "summary": "sample",
        "fields": {"name": {"value": "John", "source_page": 1, "source_text": "John"}},
        "sections": {},
        "tables": [],
    }


def _sample_pages() -> list[dict]:
    return [{"number": 1, "text": "sample text", "image": None}]


def test_canonical_resume() -> None:
    assert _canonical_doc_type("Resume") == "resume"
    assert _canonical_doc_type("CV") == "resume"


def test_canonical_invoice() -> None:
    assert _canonical_doc_type("Invoice") == "invoice"


def test_canonical_receipt() -> None:
    assert _canonical_doc_type("receipt") == "receipt"


def test_canonical_bank_statement() -> None:
    assert _canonical_doc_type("Bank Statement") == "bank_statement"


def test_canonical_flight_ticket() -> None:
    assert _canonical_doc_type("flight ticket") == "flight_ticket"


def test_canonical_hotel_bill() -> None:
    assert _canonical_doc_type("hotel invoice") == "hotel_bill"


def test_unknown_defaults_to_unknown() -> None:
    assert _canonical_doc_type("passport") == "unknown"
    assert _canonical_doc_type("") == "unknown"


def test_normalize_adds_confidence_and_hides_extra_fields() -> None:
    value = _sample_value("invoice")
    value["classification_confidence"] = 0.92
    value["top_k"] = [{"type": "invoice", "score": 0.92}]
    value["rationale"] = "contains invoice fields"
    value["signals"] = ["invoice number", "total"]

    normalized = _normalize_extraction(value, _sample_pages())

    assert normalized["document_type"] == "invoice"
    assert normalized["confidence"] == 0.92
    assert "top_k" not in normalized
    assert "rationale" not in normalized
    assert "signals" not in normalized
