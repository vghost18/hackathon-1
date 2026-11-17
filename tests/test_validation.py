from __future__ import annotations

from idp_assistant.validation import run_validations


def test_invoice_arithmetic_mismatch_is_flagged() -> None:
    value = {
        "document_type": "invoice",
        "fields": {
            "subtotal": {"value": "1000", "source_page": 1, "source_text": "1000"},
            "tax": {"value": "100", "source_page": 1, "source_text": "100"},
            "discount": {"value": "50", "source_page": 1, "source_text": "50"},
            "total": {"value": "1200", "source_page": 1, "source_text": "1200"},
        },
    }
    issues = run_validations(value)
    assert any(issue.get("rule_id") == "invoice_total_mismatch" for issue in issues)


def test_invalid_email_and_date_are_flagged() -> None:
    value = {
        "document_type": "invoice",
        "fields": {
            "customer_email": {"value": "bad-email@", "source_page": 2, "source_text": "bad-email@"},
            "invoice_date": {"value": "31/31/2026", "source_page": 2, "source_text": "31/31/2026"},
            "subtotal": {"value": "100", "source_page": 2, "source_text": "100"},
            "total": {"value": "100", "source_page": 2, "source_text": "100"},
        },
    }
    issues = run_validations(value)
    rule_ids = {issue.get("rule_id") for issue in issues}
    assert "invalid_email_format" in rule_ids
    assert "invalid_date_format" in rule_ids


def test_low_confidence_or_missing_source_is_flagged() -> None:
    value = {
        "document_type": "receipt",
        "fields": {
            "merchant_name": {"value": "Shop A", "source_page": 1, "source_text": "Shop A", "confidence": 0.4},
            "payment_method": {"value": "card", "source_page": "", "source_text": "card"},
        },
    }
    issues = run_validations(value)
    rule_ids = {issue.get("rule_id") for issue in issues}
    assert "low_confidence_field" in rule_ids or "low_confidence_missing_source" in rule_ids
