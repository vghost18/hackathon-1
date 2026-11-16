"""Gemini-only interpretation boundary; it never executes application operations."""
from __future__ import annotations
import json
import re
from typing import Any
from google import genai
from google.genai import types
from idp_assistant.config import Settings
class IntelligenceError(RuntimeError): pass

def _local_candidates(text:str)->dict[str,str]:
    patterns={
        "invoice_number":r"(?:invoice|inv)\s*(?:no|number|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
        "invoice_date":r"(?:invoice|issue|issued)\s*date\s*[:#-]?\s*([^\n|]{4,30})",
        "due_date":r"due\s*date\s*[:#-]?\s*([^\n|]{4,30})",
        "receipt_number":r"(?:receipt|transaction)\s*(?:no|number|#|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
        "account_number":r"(?:account|a/c)\s*(?:number|no|#)?\s*[:#-]?\s*([\dXx* -]{4,})",
        "opening_balance":r"opening\s*balance\s*[:#-]?\s*([^\n|]{1,30})",
        "closing_balance":r"closing\s*balance\s*[:#-]?\s*([^\n|]{1,30})",
        "subtotal":r"sub\s*total\s*[:#-]?\s*([^\n|]{1,30})",
        "tax":r"(?:tax|vat|gst)\s*[:#-]?\s*([^\n|]{1,30})",
        "total":r"(?:grand\s*total|amount\s*due|total\s*amount|total)\s*[:#-]?\s*([^\n|]{1,30})",
    }
    result={}
    for key,pattern in patterns.items():
        match=re.search(pattern,text,re.IGNORECASE)
        if match:
            value=re.sub(r"\s+"," ",match.group(1)).strip(" .;|")
            if value: result[key]=value
    return result

def _normalize_extraction(value:dict[str,Any])->dict[str,Any]:
    fields=value.get("fields",{})
    if isinstance(fields,list):
        normalized={}
        for item in fields:
            if isinstance(item,dict):
                name=item.get("field_name") or item.get("name") or item.get("key")
                if name: normalized[str(name)]=item
        value["fields"]=normalized
    elif not isinstance(fields,dict):
        value["fields"]={}
    tables=value.get("tables",[])
    if isinstance(tables,dict): tables=[tables]
    normalized_tables=[]
    for table in tables if isinstance(tables,list) else []:
        if not isinstance(table,dict): continue
        rows=table.get("rows") or table.get("data") or []
        columns=table.get("columns") or table.get("headers") or []
        if rows and isinstance(rows[0],list): rows=[dict(zip(columns,row)) for row in rows]
        table["columns"]=columns; table["rows"]=rows if isinstance(rows,list) else []
        normalized_tables.append(table)
    value["tables"]=normalized_tables
    value.setdefault("sections",{})
    return value
def _ask(settings:Settings,prompt:str)->str:
    if not settings.gemini_configured: raise IntelligenceError("Gemini is not configured. Add GEMINI_API_KEY to .env.")
    client = genai.Client(api_key=settings.gemini_api_key)
    try: return client.models.generate_content(model=settings.gemini_model,contents=prompt,config=types.GenerateContentConfig(response_mime_type="application/json") if "Return a JSON object" in prompt else None).text or ""
    except Exception as exc: raise IntelligenceError(f"Gemini request failed: {exc}") from exc
def analyse(settings:Settings,pages:list[dict[str,Any]])->dict[str,Any]:
    text="\n\n".join(f"[PAGE {p['number']}]\n{p.get('text','')}" for p in pages)
    local_hints=_local_candidates(text)
    prompt=f"""Analyze this document. Use supplied page images to read scanned content.
Return JSON with document_type, summary, fields, sections, tables, warnings.
The fields object MUST be a flat JSON object where every key maps to an object
with exactly value, source_page, and source_text. Put the human-readable value
in value, never a nested object or label. Use the page where the value appears.
For invoices and receipts extract vendor/merchant, customer (if present),
invoice/receipt number, dates, line items, subtotal, tax, discount, total,
currency, payment method, and amount due. For bank statements extract bank,
account holder, masked account number, statement period, opening/closing
balance, transactions, deposits, withdrawals, fees, and ending balance.
For every other document preserve all meaningful key/value fields with source_page
and source_text. Never put confidence or verification fields in the output.
If document_type is Resume, sections MUST include these keys even when empty:
personal_information, professional_summary, experience, projects, education,
certifications, skills, awards, languages, publications.
Represent experience, projects, education, certifications, awards, languages,
and publications as arrays of complete objects. Never silently omit a section
and never invent missing values. These are local text-parser hints only; verify
each against the document and correct or omit them when wrong:
{json.dumps(local_hints,ensure_ascii=False)}
SOURCE:
{text[:180000]}"""
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
    return _normalize_extraction(value)
def answer(settings:Settings,pages:list[dict[str,Any]],question:str)->str:
    text="\n".join(f"[Page {p['number']}] {p['text']}" for p in pages); return _ask(settings,f"Answer only from this document. Cite page numbers. If unavailable say so. DOCUMENT:\n{text[:120000]}\nQUESTION: {question}")
