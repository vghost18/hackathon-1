"""Python-only exports from corrected structured extraction."""
from __future__ import annotations
import io,json,zipfile
from typing import Any
import pandas as pd
from docx import Document
def _fields(value:dict[str,Any])->dict[str,Any]:
    raw = value.get("fields", {})
    if isinstance(raw, dict):
        return {k:(v.get("value") if isinstance(v,dict) and "value" in v else v) for k,v in raw.items()}
    if isinstance(raw, list):
        return {
            str(item.get("field_name") or item.get("name") or f"field_{index + 1}"): item.get("value", item)
            for index, item in enumerate(raw) if isinstance(item, dict)
        }
    return {}
def _flatten(prefix:str,value:Any)->dict[str,Any]:
    if isinstance(value,dict):
        result={}
        for key,item in value.items(): result.update(_flatten(f"{prefix}.{key}" if prefix else str(key),item))
        return result
    if isinstance(value,list):
        result={}
        for index,item in enumerate(value): result.update(_flatten(f"{prefix}.{index}",item))
        return result
    return {prefix:value}
def _export_fields(value:dict[str,Any])->dict[str,Any]:
    result=_fields(value)
    sections=value.get("sections",{})
    if isinstance(sections,dict):
        for section,content in sections.items():
            result.update(_flatten(str(section),content))
    return result
def _tables(value:dict[str,Any])->list[dict[str,Any]]:
    normalized=[]
    for index, table in enumerate(value.get("tables",[]) if isinstance(value.get("tables",[]),list) else []):
        if not isinstance(table,dict): continue
        columns=table.get("columns") or table.get("headers") or []
        rows=table.get("rows") or []
        if rows and isinstance(rows[0],list) and columns:
            rows=[dict(zip(columns,row)) for row in rows]
        normalized.append({"name":table.get("name") or table.get("table_name") or f"Table {index + 1}","columns":columns,"rows":rows})
    return normalized
def as_json(value): return json.dumps(value,indent=2,ensure_ascii=False).encode()
def as_csv(value):
    out=io.StringIO(); pd.DataFrame([_export_fields(value)]).to_csv(out,index=False)
    for table in _tables(value):
        out.write("\n"+table.get("name","Table")+"\n"); pd.DataFrame(table.get("rows",[]),columns=table.get("columns") or None).to_csv(out,index=False)
    return out.getvalue().encode()
def as_excel(value):
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        pd.DataFrame([_export_fields(value)]).T.rename(columns={0:"Value"}).to_excel(writer,sheet_name="Details")
        for i,t in enumerate(_tables(value),1): pd.DataFrame(t.get("rows",[]),columns=t.get("columns") or None).to_excel(writer,sheet_name=(t.get("name") or f"Table {i}")[:31],index=False)
    return out.getvalue()
def as_word(value):
    doc=Document(); doc.add_heading(value.get("document_type","Document"),0); doc.add_paragraph(value.get("summary",""))
    doc.add_heading("Details",1)
    for key,item in _export_fields(value).items(): doc.add_paragraph(f"{key}: {item}")
    sections=value.get("sections",{})
    if isinstance(sections,dict):
        for section,content in sections.items():
            doc.add_heading(str(section).replace("_"," ").title(),1)
            if isinstance(content,list):
                for item in content: doc.add_paragraph(json.dumps(item,ensure_ascii=False),style="List Bullet")
            elif isinstance(content,dict):
                for key,item in content.items(): doc.add_paragraph(f"{key}: {item}")
            else: doc.add_paragraph(str(content))
    for table in _tables(value):
        doc.add_heading(table.get("name","Table"),1); rows=table.get("rows",[]); columns=table.get("columns") or (list(rows[0]) if rows else [])
        grid=doc.add_table(rows=1,cols=len(columns)); grid.style="Light Shading Accent 1"
        for cell,name in zip(grid.rows[0].cells,columns): cell.text=str(name)
        for row in rows:
            cells=grid.add_row().cells
            for cell,name in zip(cells,columns): cell.text=str(row.get(name,"") if isinstance(row,dict) else "")
    out=io.BytesIO(); doc.save(out); return out.getvalue()
def all_exports(value):
    files={"extraction.json":as_json(value),"extraction.csv":as_csv(value),"extraction.xlsx":as_excel(value),"extraction.docx":as_word(value)}
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,content in files.items(): archive.writestr(name,content)
    files["all_exports.zip"]=out.getvalue(); return files
