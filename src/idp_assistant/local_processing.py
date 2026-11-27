"""Local-only document processing using PyMuPDF and pymupdf4llm (no external LLM calls)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf4llm

from idp_assistant.ocr_easy import dedupe_lines, ocr_image_bytes, ocr_pdf_bytes
from idp_assistant.storage import DocumentError


_CANONICAL_DOC_TYPES = {
    "resume": "resume",
    "cv": "resume",
    "curriculum vitae": "resume",
    "invoice": "invoice",
    "receipt": "receipt",
    "bank statement": "bank_statement",
    "statement": "bank_statement",
    "flight ticket": "flight_ticket",
    "air ticket": "flight_ticket",
    "hotel bill": "hotel_bill",
    "hotel invoice": "hotel_bill",
}


def _detect_doc_type(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["curriculum vitae", "resume", "professional summary", "work experience"]):
        return "resume"
    if any(x in t for x in ["invoice", "amount due", "bill to", "tax invoice"]):
        return "invoice"
    if any(x in t for x in ["receipt", "payment received", "merchant"]):
        return "receipt"
    if any(x in t for x in ["statement period", "opening balance", "closing balance", "account number"]):
        return "bank_statement"
    if any(x in t for x in ["flight", "boarding", "pnr", "departure"]):
        return "flight_ticket"
    if any(x in t for x in ["hotel", "check-in", "check-out", "room"]):
        return "hotel_bill"
    return "unknown"


def _match(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    value = " ".join((m.group(1) or "").split()).strip(" .;|")
    return value or None


def _field(value: str, source_page: int = 1, source_text: str = "local_pattern") -> dict[str, Any]:
    return {"value": value, "source_page": source_page, "source_text": source_text}


def _first_strong_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        v = _match(pattern, text)
        if v:
            return v
    return None


def _clean_id_value(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", "", value).strip(" .;|:-")
    cleaned = re.sub(r"^[#:\-]+", "", cleaned)
    return cleaned or None


def _clean_amount(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().replace(",", "")
    match = re.search(r"([+-]?\d+(?:\.\d{1,2})?)", raw)
    if not match:
        return None
    return match.group(1)


def _extract_candidates(patterns: list[str], text: str) -> list[str]:
    out: list[str] = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE | re.MULTILINE):
            v = " ".join((m.group(1) or "").split()).strip(" .;|")
            if v:
                out.append(v)
    return out


def _choose_best_id(candidates: list[str]) -> str | None:
    if not candidates:
        return None
    ranked = sorted(
        {_clean_id_value(v) for v in candidates if _clean_id_value(v)},
        key=lambda s: (
            -(sum(ch.isdigit() for ch in s) + sum(ch.isalpha() for ch in s)),
            -len(s),
            s,
        ),
    )
    return ranked[0] if ranked else None


def _extract_fields(text: str, doc_type: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}

    date_v = _first_strong_match(
        [
            r"(?:invoice\s*date|receipt\s*date|bill\s*date|issued on|date)\s*[:#-]?\s*([0-3]?\d[/-][01]?\d[/-](?:\d{2}|\d{4})|\d{4}[/-][01]?\d[/-][0-3]?\d|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
        ],
        text,
    )
    if date_v:
        fields["date"] = _field(date_v)

    total_raw = _first_strong_match(
        [
            r"(?:grand\s*total|amount\s*due|total\s*amount|net\s*payable|total)\s*[:#-]?\s*([^\n|]{1,40})",
        ],
        text,
    )
    total_v = _clean_amount(total_raw) or total_raw
    if total_v:
        fields["total"] = _field(total_v)

    if doc_type in {"invoice", "receipt"}:
        invoice_candidates = _extract_candidates(
            [
                r"(?:invoice|inv)\s*(?:number|no|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
                r"(?:tax\s*invoice)\s*(?:number|no|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
            ],
            text,
        )
        order_candidates = _extract_candidates(
            [
                r"(?:order|po|purchase\s*order)\s*(?:number|no|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
            ],
            text,
        )
        receipt_candidates = _extract_candidates(
            [
                r"(?:receipt)\s*(?:number|no|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
                r"(?:transaction)\s*(?:number|no|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
            ],
            text,
        )

        invoice_like_id = _choose_best_id(invoice_candidates)
        order_like_id = _choose_best_id(order_candidates)
        receipt_like_id = _choose_best_id(receipt_candidates)

        if invoice_like_id:
            fields["invoice_number"] = _field(invoice_like_id)
        if receipt_like_id:
            fields["receipt_number"] = _field(receipt_like_id)
        if order_like_id:
            fields["order_number"] = _field(order_like_id)

        if not invoice_like_id and not receipt_like_id and not order_like_id:
            generic_doc_id = _clean_id_value(
                _first_strong_match(
                    [
                        r"(?:document|reference|ref)\s*(?:number|no|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
                    ],
                    text,
                )
            )
            if generic_doc_id:
                fields["reference_number"] = _field(generic_doc_id)

        mapping = {
            "vendor": r"(?:vendor|merchant|seller|from)\s*[:#-]?\s*([^\n|]{2,80})",
            "customer": r"(?:bill to|customer|buyer)\s*[:#-]?\s*([^\n|]{2,80})",
            "tax": r"(?:tax|vat|gst)\s*[:#-]?\s*([^\n|]{1,30})",
            "subtotal": r"sub\s*total\s*[:#-]?\s*([^\n|]{1,30})",
        }
        for key, pattern in mapping.items():
            v = _match(pattern, text)
            if not v:
                continue
            if key in {"tax", "subtotal"}:
                v = _clean_amount(v) or v
            fields[key] = _field(v)

    if doc_type == "bank_statement":
        mapping = {
            "account_number": r"(?:account|a/c)\s*(?:number|no|#)?\s*[:#-]?\s*([\dXx* -]{4,})",
            "opening_balance": r"opening\s*balance\s*[:#-]?\s*([^\n|]{1,30})",
            "closing_balance": r"closing\s*balance\s*[:#-]?\s*([^\n|]{1,30})",
            "statement_period": r"(?:statement\s*period|period)\s*[:#-]?\s*([^\n|]{4,60})",
        }
        for key, pattern in mapping.items():
            v = _match(pattern, text)
            if not v:
                continue
            if key in {"opening_balance", "closing_balance"}:
                v = _clean_amount(v) or v
            fields[key] = _field(v)

    return fields


def _merge_fields(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Prefer primary (native) values; fill missing from secondary (OCR)."""
    merged = dict(primary)
    for key, value in secondary.items():
        if key not in merged or not str((merged.get(key) or {}).get("value", "")).strip():
            merged[key] = value
    return merged


def _confidence(doc_type: str, fields: dict[str, Any], text: str) -> float:
    if doc_type == "unknown":
        return 0.35
    score = 0.55
    score += min(0.3, len(fields) * 0.03)
    if text.strip():
        score += 0.05
    return round(max(0.0, min(1.0, score)), 2)


def _split_resume_sections(text: str) -> dict[str, list[str]]:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return {}

    header_patterns = {
        "professional_summary": [r"^summary$", r"^professional summary$", r"^profile$", r"^objective$"],
        "experience": [r"^experience$", r"^work experience$", r"^employment history$", r"^professional experience$"],
        "projects": [r"^projects?$", r"^project experience$"],
        "education": [r"^education$", r"^academic background$"],
        "certifications": [r"^certifications?$", r"^licenses?$"],
        "skills": [r"^skills?$", r"^technical skills?$", r"^core competencies$"],
        "awards": [r"^awards?$", r"^achievements?$", r"^honors?$"],
        "languages": [r"^languages?$"],
        "publications": [r"^publications?$", r"^research$"],
    }

    section_text: dict[str, list[str]] = {k: [] for k in header_patterns}
    current = "professional_summary"

    for line in lines:
        normalized = re.sub(r"[:\-]+$", "", line.lower()).strip()
        switched = False
        for section, patterns in header_patterns.items():
            if any(re.match(p, normalized) for p in patterns):
                current = section
                switched = True
                break
        if switched:
            continue
        if len(normalized) < 2:
            continue
        section_text.setdefault(current, []).append(line)

    return section_text


def _split_bullets(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        line = line.strip().lstrip("•*- ").strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"\s{2,}| \| ", line) if p.strip()]
        if parts:
            out.extend(parts)
        else:
            out.append(line)
    return out


def _extract_resume_personal_information(text: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    email = _match(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
    phone = _match(r"(\+?\d[\d \-()]{7,}\d)", text)
    linkedin = _match(r"(https?://(?:www\.)?linkedin\.com/[^\s]+)", text)
    github = _match(r"(https?://(?:www\.)?github\.com/[^\s]+)", text)
    if email:
        info["email"] = email
    if phone:
        info["phone"] = re.sub(r"\s+", " ", phone).strip()
    if linkedin:
        info["linkedin"] = linkedin
    if github:
        info["github"] = github
    return info


def _resume_sections(text: str) -> dict[str, Any]:
    parsed = _split_resume_sections(text)

    summary_lines = parsed.get("professional_summary", [])
    professional_summary = " ".join(summary_lines[:4]).strip()

    experience = _split_bullets(parsed.get("experience", []))
    projects = _split_bullets(parsed.get("projects", []))
    education = _split_bullets(parsed.get("education", []))
    certifications = _split_bullets(parsed.get("certifications", []))
    skills = _split_bullets(parsed.get("skills", []))
    awards = _split_bullets(parsed.get("awards", []))
    languages = _split_bullets(parsed.get("languages", []))
    publications = _split_bullets(parsed.get("publications", []))

    return {
        "personal_information": _extract_resume_personal_information(text),
        "professional_summary": professional_summary or (text[:300] if text else ""),
        "experience": experience,
        "projects": projects,
        "education": education,
        "certifications": certifications,
        "skills": skills,
        "awards": awards,
        "languages": languages,
        "publications": publications,
    }


def local_analyse_document(storage_path: str | Path, filename: str) -> dict[str, Any]:
    source = Path(storage_path)
    if not source.exists():
        raise DocumentError("Stored source file not found for local processing.")

    try:
        md = pymupdf4llm.to_markdown(str(source))
    except Exception as exc:
        raise DocumentError(f"Local extraction failed: {exc}") from exc

    native_text = md or ""
    suffix = Path(filename).suffix.lower()
    file_bytes = source.read_bytes()

    ocr_text = ""
    warnings: list[str] = []
    try:
        if suffix == ".pdf":
            ocr_text = ocr_pdf_bytes(file_bytes, max_pages=10)
        elif suffix in {".png", ".jpg", ".jpeg"}:
            ocr_text = ocr_image_bytes(file_bytes)
    except Exception as exc:
        warnings.append(f"OCR fallback failed: {exc}")

    doc_type_native = _CANONICAL_DOC_TYPES.get(_detect_doc_type(native_text), "unknown")
    native_fields = _extract_fields(native_text, doc_type_native)

    ocr_fields: dict[str, Any] = {}
    doc_type_ocr = "unknown"
    if ocr_text.strip():
        doc_type_ocr = _CANONICAL_DOC_TYPES.get(_detect_doc_type(ocr_text), "unknown")
        ocr_fields = _extract_fields(ocr_text, doc_type_ocr)

    low_native_coverage = len(native_text.strip()) < 120 or len(native_fields) < 2
    use_ocr_merge = bool(ocr_text.strip()) and (low_native_coverage or len(ocr_fields) > len(native_fields))

    if use_ocr_merge:
        text = dedupe_lines(native_text, ocr_text)
        doc_type = doc_type_native if doc_type_native != "unknown" else doc_type_ocr
        fields = _merge_fields(native_fields, ocr_fields)
        warnings.append("OCR fallback was used to enhance extraction.")
    else:
        text = native_text
        doc_type = doc_type_native
        fields = native_fields
        if ocr_text.strip():
            warnings.append("OCR was available but native extraction was sufficient; native values preferred.")

    if len(text.strip()) < 120:
        warnings.append("Low text coverage detected. Extraction may be incomplete.")

    sections: dict[str, Any] = {}
    if doc_type == "resume":
        sections = _resume_sections(text)

    result: dict[str, Any] = {
        "document_type": doc_type,
        "confidence": _confidence(doc_type, fields, text),
        "summary": (text[:600].strip() or "No textual content extracted."),
        "fields": fields,
        "sections": sections,
        "tables": [],
        "warnings": warnings,
    }
    return result
