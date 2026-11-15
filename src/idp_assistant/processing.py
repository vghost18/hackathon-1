"""Coverage-aware processing orchestration."""
from __future__ import annotations
from idp_assistant.intelligence import analyse
from idp_assistant.storage import save_processing
def process_document(settings,database_path,document):
    pages=[{"number":p["page_number"],"text":p["native_text"] or ""} for p in document["pages"]]
    report=[{"page_number":p["number"],"status":"native_text" if p["text"].strip() else "needs_visual_review","review_required":not bool(p["text"].strip())} for p in pages]
    result=analyse(settings,pages); result["coverage_report"]={"total_pages":len(pages),"processed_pages":len(pages),"successful_pages":sum(not p["review_required"] for p in report),"pages_requiring_review":[p["page_number"] for p in report if p["review_required"]],"failed_pages":[]}
    save_processing(database_path,document["id"],result.get("document_type","Other"),result.get("summary",""),result,"partial" if result["coverage_report"]["pages_requiring_review"] else "complete",report); return result
