"""Deterministic validation rules for extracted document payloads."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _field_value(fields: dict[str, Any], key: str) -> tuple[Any, Any]:
    raw = fields.get(key)
    if isinstance(raw, dict):
        return raw.get("value"), raw.get("source_page")
    return raw, None


def _issue(
    rule_id: str,
    severity: str,
    field: str,
    message: str,
    source_page: Any = None,
    actual: Any = None,
    expected: Any = None,
    confidence: Any = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "field": field,
        "message": message,
        "source_page": source_page,
        "actual": actual,
        "expected": expected,
        "confidence": confidence,
        "review_required": True,
    }


def validate_invoice_totals(value: dict[str, Any]) -> list[dict[str, Any]]:
    if str(value.get("document_type", "")).lower() != "invoice":
        return []
    fields = value.get("fields", {})
    if not isinstance(fields, dict):
        return []

    subtotal, subtotal_page = _field_value(fields, "subtotal")
    tax, tax_page = _field_value(fields, "tax")
    discount, discount_page = _field_value(fields, "discount")
    total, total_page = _field_value(fields, "total")
    shipping, shipping_page = _field_value(fields, "shipping")
    fees, fees_page = _field_value(fields, "fees")

    subtotal_num = _as_float(subtotal)
    tax_num = _as_float(tax) or 0.0
    discount_num = _as_float(discount) or 0.0
    total_num = _as_float(total)
    shipping_num = _as_float(shipping) or 0.0
    fees_num = _as_float(fees) or 0.0

    if subtotal_num is None or total_num is None:
        return []

    expected_total = subtotal_num + tax_num + shipping_num + fees_num - discount_num
    if abs(expected_total - total_num) > 0.5:
        return [
            _issue(
                "invoice_total_mismatch",
                "error",
                "total",
                "Arithmetic mismatch: subtotal + tax + shipping + fees - discount does not match total.",
                source_page=total_page or subtotal_page or tax_page or discount_page or shipping_page or fees_page,
                actual=total,
                expected=f"{expected_total:.2f}",
            )
        ]
    return []


_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y")


def _looks_like_date_field(name: str) -> bool:
    lowered = name.lower()
    return "date" in lowered or "period" in lowered


def _is_valid_date(text: str) -> bool:
    raw = text.strip()
    if not raw:
        return True
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(raw, fmt)
            return True
        except ValueError:
            continue
    return False


def validate_field_formats(value: dict[str, Any]) -> list[dict[str, Any]]:
    fields = value.get("fields", {})
    if not isinstance(fields, dict):
        return []
    issues: list[dict[str, Any]] = []
    for key, item in fields.items():
        if isinstance(item, dict):
            field_value = item.get("value")
            source_page = item.get("source_page")
        else:
            field_value = item
            source_page = None
        text = str(field_value or "").strip()

        if "email" in key.lower() and text and not _EMAIL_PATTERN.match(text):
            issues.append(
                _issue(
                    "invalid_email_format",
                    "warning",
                    key,
                    "Invalid email format. Field is flagged and not silently accepted.",
                    source_page=source_page,
                    actual=field_value,
                )
            )

        if _looks_like_date_field(key) and text and not _is_valid_date(text):
            issues.append(
                _issue(
                    "invalid_date_format",
                    "warning",
                    key,
                    "Invalid date format. Field is flagged and not silently accepted.",
                    source_page=source_page,
                    actual=field_value,
                )
            )
    return issues


def flag_low_confidence_fields(value: dict[str, Any], threshold: float = 0.6) -> list[dict[str, Any]]:
    fields = value.get("fields", {})
    if not isinstance(fields, dict):
        return []
    issues: list[dict[str, Any]] = []
    for key, item in fields.items():
        if not isinstance(item, dict):
            continue
        confidence = item.get("confidence")
        source_page = item.get("source_page")
        if confidence is None:
            if not source_page:
                issues.append(
                    _issue(
                        "low_confidence_missing_source",
                        "warning",
                        key,
                        "Low-confidence field highlighted in the review screen with source page.",
                        source_page=source_page,
                        actual=item.get("value"),
                        confidence=0.5,
                    )
                )
            continue
        try:
            c = float(confidence)
        except Exception:
            c = 0.0
        if c < threshold:
            issues.append(
                _issue(
                    "low_confidence_field",
                    "warning",
                    key,
                    "Low-confidence field highlighted in the review screen with source page.",
                    source_page=source_page,
                    actual=item.get("value"),
                    confidence=round(c, 2),
                )
            )
    return issues


def run_validations(value: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    issues.extend(validate_invoice_totals(value))
    issues.extend(validate_field_formats(value))
    issues.extend(flag_low_confidence_fields(value))
    return issues
