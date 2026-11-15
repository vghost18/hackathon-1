"""Safe local PDF storage and SQLite data access."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any
import fitz
from idp_assistant.db import get_connection
class DocumentError(ValueError): pass
def ingest_pdf(database_path: Path, data_dir: Path, filename: str, content: bytes) -> tuple[dict[str, Any], bool]:
    if not content or not filename.lower().endswith(".pdf"): raise DocumentError("Please provide a non-empty PDF file.")
    try:
        pdf=fitz.open(stream=content,filetype="pdf"); pages=[{"number":i+1,"text":p.get_text("text")} for i,p in enumerate(pdf)]
        metadata=dict(pdf.metadata or {}); page_count=pdf.page_count; pdf.close()
    except Exception as exc: raise DocumentError(f"Invalid or unreadable PDF: {exc}") from exc
    digest=hashlib.sha256(content).hexdigest(); target_dir=data_dir/"documents"; target_dir.mkdir(parents=True,exist_ok=True)
    with get_connection(database_path) as conn:
        existing=conn.execute("SELECT * FROM documents WHERE file_hash=?",(digest,)).fetchone()
        if existing: return dict(existing),True
        target=target_dir/f"{digest}.pdf"; target.write_bytes(content)
        cur=conn.execute("INSERT INTO documents(file_hash,filename,storage_path,metadata_json,page_count,processing_status) VALUES(?,?,?,?,?,'stored')",(digest,filename,str(target),json.dumps(metadata),page_count))
        doc_id=cur.lastrowid; conn.executemany("INSERT INTO document_pages(document_id,page_number,native_text,processing_status,review_required) VALUES(?,?,?,'native_text',?)",[(doc_id,p["number"],p["text"],int(not p["text"].strip())) for p in pages]); conn.commit()
        return get_document(database_path,doc_id),False
def get_document(database_path:Path,document_id:int)->dict[str,Any]:
    with get_connection(database_path) as conn:
        row=conn.execute("SELECT * FROM documents WHERE id=?",(document_id,)).fetchone()
        if not row: raise DocumentError("Document no longer exists.")
        data=dict(row); data["metadata"]=json.loads(data.pop("metadata_json") or "{}"); data["pages"]=[dict(p) for p in conn.execute("SELECT * FROM document_pages WHERE document_id=? ORDER BY page_number",(document_id,))]; return data
def list_documents(database_path:Path)->list[dict[str,Any]]:
    with get_connection(database_path) as conn: return [dict(r) for r in conn.execute("SELECT id,filename,page_count,document_type,processing_status,summary,created_at FROM documents ORDER BY id DESC")]
def save_processing(database_path:Path,document_id:int,document_type:str,summary:str,value:dict[str,Any],status:str,pages:list[dict[str,Any]])->None:
    payload=json.dumps(value)
    with get_connection(database_path) as conn:
        conn.execute("UPDATE documents SET document_type=?,summary=?,original_extraction_json=?,corrected_extraction_json=COALESCE(corrected_extraction_json,?),processing_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(document_type,summary,payload,payload,status,document_id))
        conn.executemany("UPDATE document_pages SET processing_status=?,review_required=?,error_message=? WHERE document_id=? AND page_number=?",[(p["status"],int(p["review_required"]),p.get("error"),document_id,p["page_number"]) for p in pages]); conn.commit()
def extraction(database_path:Path,document_id:int,corrected:bool=True)->dict[str,Any]:
    with get_connection(database_path) as conn: row=conn.execute("SELECT original_extraction_json,corrected_extraction_json FROM documents WHERE id=?",(document_id,)).fetchone()
    raw=(row["corrected_extraction_json"] if corrected else row["original_extraction_json"]) if row else None; return json.loads(raw or "{}")
def save_correction(database_path:Path,document_id:int,value:dict[str,Any])->None:
    payload=json.dumps(value)
    with get_connection(database_path) as conn: conn.execute("UPDATE documents SET corrected_extraction_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(payload,document_id)); conn.execute("INSERT INTO extraction_versions(document_id,version_kind,payload_json) VALUES(?,?,?)",(document_id,"corrected",payload)); conn.commit()
def log_plugin(database_path:Path,document_id:int|None,name:str,status:str,inp:dict[str,Any],out:dict[str,Any]|None=None,error:str|None=None)->None:
    with get_connection(database_path) as conn: conn.execute("INSERT INTO plugin_executions(document_id,plugin_name,status,input_json,output_json,error_message,completed_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",(document_id,name,status,json.dumps(inp),json.dumps(out or {}),error)); conn.commit()
