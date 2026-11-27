"""Safe local PDF storage and SQLite data access."""
from __future__ import annotations
import hashlib, json
import io
from pathlib import Path
from typing import Any
import fitz
from docx import Document as WordDocument
from PIL import Image
from idp_assistant.db import get_connection
class DocumentError(ValueError): pass
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 10

def _document_pages(filename: str, content: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentError("File extension is .pdf but the PDF signature is invalid.")
        pdf = fitz.open(stream=content, filetype="pdf")
        try:
            if pdf.needs_pass:
                raise DocumentError("This PDF is password-protected. Please upload an unprotected PDF.")
            if len(pdf) > MAX_PDF_PAGES:
                raise DocumentError(f"PDF page limit exceeded: maximum is {MAX_PDF_PAGES} pages.")
            pages = [
                {
                    "number": i + 1,
                    "text": page.get_text("text"),
                    "image": page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png"),
                }
                for i, page in enumerate(pdf)
            ]
            metadata = dict(pdf.metadata or {})
            metadata["input_type"] = "pdf"
            return pages, metadata
        finally:
            pdf.close()
    if extension == ".docx":
        word=WordDocument(io.BytesIO(content))
        chunks=[paragraph.text for paragraph in word.paragraphs if paragraph.text.strip()]
        for table in word.tables:
            chunks.extend(" | ".join(cell.text for cell in row.cells) for row in table.rows)
        return [{"number":1,"text":"\n".join(chunks),"image":None}],{"input_type":"docx"}
    if extension in {".png",".jpg",".jpeg"}:
        image=Image.open(io.BytesIO(content)); image.verify()
        return [{"number":1,"text":"","image":content}],{"input_type":"image","image_format":extension.lstrip(".")}
    raise DocumentError("Supported file types are PDF, PNG, JPG, JPEG, and DOCX.")

def ingest_document(database_path: Path, data_dir: Path, filename: str, content: bytes, reuse_existing: bool = True) -> tuple[dict[str, Any], bool]:
    if not content or Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise DocumentError("Supported file types are PDF, PNG, JPG, JPEG, and DOCX.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentError(f"File size limit exceeded: maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        pages, metadata = _document_pages(filename, content)
        page_count = len(pages)
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"Invalid or unreadable file: {exc}") from exc
    digest=hashlib.sha256(content).hexdigest(); target_dir=data_dir/"documents"; target_dir.mkdir(parents=True,exist_ok=True)
    with get_connection(database_path) as conn:
        existing=conn.execute("SELECT * FROM documents WHERE file_hash=?",(digest,)).fetchone()
        if existing and reuse_existing:
            return dict(existing),True
        if existing and not reuse_existing:
            # DB enforces UNIQUE(file_hash), so for "fresh ingest" mode we remove prior row first.
            conn.execute("DELETE FROM documents WHERE file_hash=?",(digest,))
            conn.commit()
        target=target_dir/f"{digest}{Path(filename).suffix.lower()}"; target.write_bytes(content)
        cur=conn.execute("INSERT INTO documents(file_hash,filename,storage_path,metadata_json,page_count,processing_status) VALUES(?,?,?,?,?,'stored')",(digest,filename,str(target),json.dumps(metadata),page_count))
        doc_id=cur.lastrowid; conn.executemany("INSERT INTO document_pages(document_id,page_number,native_text,processing_status,review_required) VALUES(?,?,?,'native_text',?)",[(doc_id,p["number"],p["text"],int(not p["text"].strip())) for p in pages]); conn.commit()
        return get_document(database_path,doc_id),False

def ingest_pdf(database_path: Path, data_dir: Path, filename: str, content: bytes) -> tuple[dict[str, Any], bool]:
    return ingest_document(database_path, data_dir, filename, content)
def get_document(database_path:Path,document_id:int)->dict[str,Any]:
    with get_connection(database_path) as conn:
        row=conn.execute("SELECT * FROM documents WHERE id=?",(document_id,)).fetchone()
        if not row: raise DocumentError("Document no longer exists.")
        data=dict(row); data["metadata"]=json.loads(data.pop("metadata_json") or "{}"); data["pages"]=[dict(p) for p in conn.execute("SELECT * FROM document_pages WHERE document_id=? ORDER BY page_number",(document_id,))]; return data
def load_processing_pages(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Recreate text and visual page inputs from the stored source file."""
    source=Path(document["storage_path"])
    pages,_=_document_pages(document["filename"],source.read_bytes())
    return pages
def list_documents(database_path:Path)->list[dict[str,Any]]:
    with get_connection(database_path) as conn: return [dict(r) for r in conn.execute("SELECT id,filename,page_count,document_type,processing_status,summary,created_at FROM documents ORDER BY id DESC")]
def save_processing(database_path:Path,document_id:int,document_type:str,summary:str,value:dict[str,Any],status:str,pages:list[dict[str,Any]])->None:
    payload=json.dumps(value)
    with get_connection(database_path) as conn:
        conn.execute("UPDATE documents SET document_type=?,summary=?,original_extraction_json=?,corrected_extraction_json=CASE WHEN corrected_extraction_json IS NULL OR corrected_extraction_json=original_extraction_json THEN ? ELSE corrected_extraction_json END,processing_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(document_type,summary,payload,payload,status,document_id))
        conn.executemany("UPDATE document_pages SET processing_status=?,review_required=?,error_message=? WHERE document_id=? AND page_number=?",[(p["status"],int(p["review_required"]),p.get("error"),document_id,p["page_number"]) for p in pages]); conn.commit()
def extraction(database_path:Path,document_id:int,corrected:bool=True)->dict[str,Any]:
    with get_connection(database_path) as conn: row=conn.execute("SELECT original_extraction_json,corrected_extraction_json FROM documents WHERE id=?",(document_id,)).fetchone()
    raw=(row["corrected_extraction_json"] if corrected else row["original_extraction_json"]) if row else None; return json.loads(raw or "{}")
def save_correction(database_path:Path,document_id:int,value:dict[str,Any])->None:
    payload=json.dumps(value)
    with get_connection(database_path) as conn: conn.execute("UPDATE documents SET corrected_extraction_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(payload,document_id)); conn.execute("INSERT INTO extraction_versions(document_id,version_kind,payload_json) VALUES(?,?,?)",(document_id,"corrected",payload)); conn.commit()
def log_plugin(database_path:Path,document_id:int|None,name:str,status:str,inp:dict[str,Any],out:dict[str,Any]|None=None,error:str|None=None)->None:
    with get_connection(database_path) as conn: conn.execute("INSERT INTO plugin_executions(document_id,plugin_name,status,input_json,output_json,error_message,completed_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",(document_id,name,status,json.dumps(inp),json.dumps(out or {}),error)); conn.commit()
