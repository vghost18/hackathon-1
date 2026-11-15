"""Gemini-only interpretation boundary; it never executes application operations."""
from __future__ import annotations
import json
from typing import Any
from google import genai
from google.genai import types
from idp_assistant.config import Settings
class IntelligenceError(RuntimeError): pass
def _ask(settings:Settings,prompt:str)->str:
    if not settings.gemini_configured: raise IntelligenceError("Gemini is not configured. Add GEMINI_API_KEY to .env.")
    client = genai.Client(api_key=settings.gemini_api_key)
    try: return client.models.generate_content(model=settings.gemini_model,contents=prompt,config=types.GenerateContentConfig(response_mime_type="application/json") if "Return a JSON object" in prompt else None).text or ""
    except Exception as exc: raise IntelligenceError(f"Gemini request failed: {exc}") from exc
def analyse(settings:Settings,pages:list[dict[str,Any]])->dict[str,Any]:
    text="\n\n".join(f"[PAGE {p['number']}]\n{p.get('text','')}" for p in pages)
    prompt=f"Analyze this document. Use supplied page images to read scanned content. Return a JSON object with document_type, summary, fields, tables, warnings. Document types: Resume, Invoice, Receipt, Travel Receipt, Expense Document, Bank Statement, Purchase Order, Contract, Business Report, Other. Field entries must include value, source_page, source_text, confidence null, verification_status. Do not invent values. SOURCE:\n{text[:180000]}"
    client=genai.Client(api_key=settings.gemini_api_key)
    parts=[prompt]
    for page in pages:
        if page.get("image"): parts.append(types.Part.from_bytes(data=page["image"],mime_type="image/png" if page["image"][:8]==b"\x89PNG\r\n\x1a\n" else "image/jpeg"))
    try: raw=client.models.generate_content(model=settings.gemini_model,contents=parts,config=types.GenerateContentConfig(response_mime_type="application/json")).text or ""
    except Exception as exc: raise IntelligenceError(f"Gemini request failed: {exc}") from exc
    fence=chr(96)*3
    try: value=json.loads(raw.strip().removeprefix(fence+"json").removeprefix(fence).removesuffix(fence).strip())
    except Exception as exc: raise IntelligenceError("Gemini returned invalid structured JSON.") from exc
    if not isinstance(value,dict): raise IntelligenceError("Gemini returned a non-object extraction.")
    return value
def answer(settings:Settings,pages:list[dict[str,Any]],question:str)->str:
    text="\n".join(f"[Page {p['number']}] {p['text']}" for p in pages); return _ask(settings,f"Answer only from this document. Cite page numbers. If unavailable say so. DOCUMENT:\n{text[:120000]}\nQUESTION: {question}")
