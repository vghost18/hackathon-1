"""EasyOCR helper for local OCR fallback in LOCAL mode."""
from __future__ import annotations

import io
from typing import Iterable

import easyocr
import fitz
from PIL import Image


_READER = None


def _reader():
    global _READER
    if _READER is None:
        _READER = easyocr.Reader(["en"], gpu=False)
    return _READER


def ocr_image_bytes(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result = _reader().readtext(image, detail=0, paragraph=True)
    return "\n".join(str(x).strip() for x in result if str(x).strip())


def ocr_pdf_bytes(pdf_bytes: bytes, max_pages: int = 10) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks: list[str] = []
    try:
        for index, page in enumerate(doc):
            if index >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            page_text = ocr_image_bytes(pix.tobytes("png"))
            if page_text.strip():
                chunks.append(f"[PAGE {index + 1} OCR]\n{page_text}")
    finally:
        doc.close()
    return "\n\n".join(chunks)


def dedupe_lines(primary_text: str, secondary_text: str) -> str:
    seen: set[str] = set()
    merged: list[str] = []

    def add_lines(lines: Iterable[str]) -> None:
        for raw in lines:
            line = " ".join(raw.strip().split())
            if not line:
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(line)

    add_lines(primary_text.splitlines())
    add_lines(secondary_text.splitlines())
    return "\n".join(merged)
