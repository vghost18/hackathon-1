"""Chat-first Streamlit experience for DocuMind."""
from __future__ import annotations
import json
import io
import zipfile
import webbrowser
import pandas as pd
import streamlit as st
from idp_assistant.storage import ingest_document,list_documents,get_document,extraction,save_correction,log_plugin,DocumentError
from idp_assistant.processing import process_document
from idp_assistant.intelligence import answer,IntelligenceError
from idp_assistant.exporters import all_exports

def _init():
    st.session_state.setdefault("view","Chat"); st.session_state.setdefault("messages",[]); st.session_state.setdefault("document_id",None); st.session_state.setdefault("batch_document_ids",[]); st.session_state.setdefault("session_document_ids",[]); st.session_state.setdefault("reset_nonce",0)

def _reset_session():
    """Clear transient conversation state while keeping stored documents intact."""
    for key in list(st.session_state):
        if key.startswith(("json_", "table_", "format_", "active_document_")):
            del st.session_state[key]
    st.session_state.messages=[]
    st.session_state.document_id=None
    st.session_state.batch_document_ids=[]
    st.session_state.session_document_ids=[]
    st.session_state.view="Chat"
    st.session_state.reset_nonce=st.session_state.get("reset_nonce",0)+1

def _style():
    st.markdown("""<style>
    .stApp {background:linear-gradient(135deg,#010101,#0E287C)}
    [data-testid="stSidebar"] {background:#101827}
    [data-testid="stSidebar"] * {color:#f8fafc}
    .hero {padding:1.4rem 0 .5rem}.hero h1{margin:0;color:#E0E3EB}.hero p{color:#B8BCC2;font-size:1.05rem}
    .doc-chip{padding:.6rem .8rem;border-radius:10px;background:#e0e7ff;color:#3730a3;font-weight:600}
    .stButton>button {border-radius:9px;border:0;background:#4f46e5;color:white;font-weight:600}
    [data-testid="stChatMessage"] {border-radius:14px}
    </style>""",unsafe_allow_html=True)

def _sidebar(settings):
    with st.sidebar:
        st.markdown("## ◈ DocuMind")
        st.caption("Document intelligence, in one conversation.")
        if st.button("＋ New conversation",use_container_width=True):
            st.session_state.messages=[]; st.session_state.document_id=None; st.session_state.view="Chat"; st.rerun()
        if st.button("↺ Reset session",use_container_width=True,help="Clear the current document, chat, extraction tables, and selections. Stored documents remain in the library."):
            _reset_session()
            st.rerun()
        st.divider()
        if st.button("💬 Chat",use_container_width=True): st.session_state.view="Chat"; st.rerun()
        if st.button("▣ Document library",use_container_width=True): st.session_state.view="Library"; st.rerun()
        st.divider()
        st.success("Gemini ready") if settings.gemini_configured else st.info("Gemini key not set")
        st.caption(f"Model: {settings.gemini_model}")

def _session_documents(db):
    """Return only documents uploaded during this browser session."""
    allowed=set(st.session_state.get("session_document_ids",[]))
    return [doc for doc in list_documents(db) if doc["id"] in allowed]

def _document_picker(db):
    docs=_session_documents(db)
    if not docs: return None
    options={f"{d['filename']}  ·  {d['page_count']} pages  ·  {d['processing_status']}":d["id"] for d in docs}
    labels=["— No active document —",*options]
    current=next((i+1 for i,x in enumerate(options.values()) if x==st.session_state.document_id),0)
    label=st.selectbox("Active document",labels,index=current,key=f"active_document_{st.session_state.reset_nonce}")
    if label==labels[0]:
        st.session_state.document_id=None
        return None
    st.session_state.document_id=options[label]
    return get_document(db,options[label])

def _upload(settings,db):
    with st.expander("Attach documents",expanded=not st.session_state.document_id):
        files=st.file_uploader("Up to 3 PDFs, images, or DOCX files",type=["pdf","png","jpg","jpeg","docx"],accept_multiple_files=True,label_visibility="collapsed")
        if files and st.button("Add documents to conversation",type="primary"):
            if len(files)>3:
                st.error("Choose no more than 3 documents at once."); return
            added=[]
            try:
                for file in files:
                    doc,duplicate=ingest_document(db,settings.data_dir,file.name,file.getvalue())
                    added.append((doc,duplicate))
                st.session_state.session_document_ids.extend(doc["id"] for doc,_ in added if doc["id"] not in st.session_state.session_document_ids)
                st.session_state.document_id=added[0][0]["id"]; st.session_state.batch_document_ids=[doc["id"] for doc,_ in added]
                st.session_state.setdefault("export_dirty_docs",{})
                for doc,_ in added:
                    st.session_state.export_dirty_docs[str(doc["id"])]=False
                names=", ".join(f"**{doc['filename']}**" for doc,_ in added)
                st.session_state.messages.append({"role":"assistant","content":f"I attached {names}. You can analyze this batch together or select one as the active document."})
                st.rerun()
            except DocumentError as exc: st.error(str(exc))

def _analysis(settings,db,doc):
    if not doc: return
    left,right=st.columns([3,1])
    doc_type=doc.get("document_type") or "Type not identified yet"
    with left: st.markdown(f"<div class='doc-chip'>📄 {doc['filename']} · {doc['page_count']} pages · {doc['processing_status']} · <b>{doc_type}</b></div>",unsafe_allow_html=True)
    with right:
        batch_ids=st.session_state.batch_document_ids
        analyze_label=f"Analyze all {len(batch_ids)} documents" if len(batch_ids)>1 else "Analyze document"
        if st.button(analyze_label,disabled=not settings.gemini_configured,use_container_width=True):
            ids=batch_ids if len(batch_ids)>1 else [doc["id"]]
            failures=[]
            try:
                with st.spinner(f"Reading and extracting {len(ids)} document{'s' if len(ids)>1 else ''}..."):
                    results=[]
                    for document_id in ids:
                        try: results.append((get_document(db,document_id),process_document(settings,db,get_document(db,document_id))))
                        except IntelligenceError as exc: failures.append(str(exc))
                if results:
                    names=", ".join(f"**{item[0]['filename']}** ({item[1].get('document_type','Other')})" for item in results)
                    st.session_state.messages.append({"role":"assistant","content":f"Analysis complete for {names}. Each document is shown in its own output tab below."})
                if failures: st.error("Some documents could not be analyzed: "+"; ".join(failures))
                st.rerun()
            except IntelligenceError as exc: st.error(str(exc))
    if not settings.gemini_configured: st.caption("Add GEMINI_API_KEY in .env, then restart the app to enable analysis.")

def _workspace(settings,db,doc):
    if not doc: return
    value=extraction(db,doc["id"])
    if not value: return
    st.subheader("Structured extraction")
    sections=value.get("sections",{})
    if isinstance(sections,dict) and sections:
        section_tabs=st.tabs([str(name).replace("_"," ").title() for name in sections])
        for tab,(name,content) in zip(section_tabs,sections.items()):
            with tab:
                if isinstance(content,list):
                    rows=[]
                    for item in content:
                        rows.append(item if isinstance(item,dict) else {"Value":item})
                    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                elif isinstance(content,dict):
                    st.dataframe(pd.DataFrame([{"Key":key,"Value":item} for key,item in content.items()]),use_container_width=True,hide_index=True)
                else:
                    st.write(content)
    fields=value.get("fields",{})
    if isinstance(fields,dict):
        field_rows=[
            {
                "Field":key,
                "Value":item.get("value",item) if isinstance(item,dict) else item,
                "Source page":item.get("source_page","") if isinstance(item,dict) else "",
            }
            for key,item in fields.items()
        ]
    else:
        field_rows=[
            {
                "Field":item.get("field_name",item.get("name","")),
                "Value":item.get("value",""),
                "Source page":item.get("source_page",""),
            }
            for item in fields if isinstance(item,dict)
        ]
    if field_rows:
        st.dataframe(pd.DataFrame(field_rows),use_container_width=True,hide_index=True)
    tables=value.get("tables",[])
    for table_index,table in enumerate(tables if isinstance(tables,list) else []):
        if not isinstance(table,dict):
            continue
        columns=table.get("columns") or table.get("headers") or []
        rows=table.get("rows") or []
        if rows and isinstance(rows[0],list):
            rows=[dict(zip(columns,row)) for row in rows]
        st.markdown(f"**{table.get('name') or table.get('table_name') or f'Table {table_index+1}'}**")
        st.dataframe(pd.DataFrame(rows,columns=columns or None),use_container_width=True,hide_index=True)
    with st.expander("Review and correct extraction"):
        text=st.text_area("Corrected JSON",json.dumps(value,indent=2),height=320,key=f"json_{doc['id']}")
        if st.button("Save corrections",key=f"save_corrections_{doc['id']}"):
            try: save_correction(db,doc["id"],json.loads(text)); st.success("Corrections saved."); st.rerun()
            except json.JSONDecodeError as exc: st.error(f"Invalid JSON: {exc}")
    with st.expander("Export or send"):
        st.session_state.setdefault("export_dirty_docs",{})
        st.session_state.setdefault("last_saved_export_snapshot",{})
        st.session_state.setdefault("saved_correction_snapshot",{})
        st.session_state.setdefault("export_edit_buffers",{})
        doc_key=str(doc["id"])
        latest_value=extraction(db,doc["id"])
        latest_snapshot=json.dumps(latest_value,sort_keys=True,default=str)
        if st.session_state.saved_correction_snapshot.get(doc_key)!=latest_snapshot:
            st.session_state.last_saved_export_snapshot[doc_key]=latest_snapshot
            st.session_state.saved_correction_snapshot[doc_key]=latest_snapshot
            st.session_state.export_edit_buffers[doc_key]=json.loads(json.dumps(latest_value))
            st.session_state.export_dirty_docs[doc_key]=False
        editable_value=json.loads(json.dumps(st.session_state.export_edit_buffers.get(doc_key,latest_value)))
        st.caption("Choose an output format and edit only that output preview. Save appears whenever new changes are detected.")
        formats={"JSON":"extraction.json","CSV":"extraction.csv","Excel":"extraction.xlsx","Word":"extraction.docx","ZIP":"all_exports.zip"}
        selected_format=st.selectbox("Choose output format",list(formats),key=f"format_{doc['id']}")
        if selected_format=="JSON":
            st.json(editable_value)
        elif selected_format=="CSV":
            csv_df=pd.DataFrame([{k:(v.get("value",v) if isinstance(v,dict) else v) for k,v in editable_value.get("fields",{}).items()}])
            edited_csv_df=st.data_editor(csv_df,num_rows="dynamic",use_container_width=True,key=f"preview_csv_{doc['id']}")
            if not edited_csv_df.empty:
                first_row=edited_csv_df.iloc[0].to_dict()
                editable_value["fields"]={key:{"value":val,"source_page":editable_value.get("fields",{}).get(key,{}).get("source_page","")} for key,val in first_row.items()}
        elif selected_format=="Excel":
            excel_tabs=st.tabs(["Fields","Tables"])
            with excel_tabs[0]:
                fields_df=pd.DataFrame([
                    {
                        "Field":key,
                        "Value":item.get("value",item) if isinstance(item,dict) else item,
                        "Source page":item.get("source_page","") if isinstance(item,dict) else "",
                    }
                    for key,item in editable_value.get("fields",{}).items()
                ])
                edited_fields_df=st.data_editor(fields_df,num_rows="dynamic",use_container_width=True,key=f"preview_excel_fields_{doc['id']}")
                rebuilt_fields={}
                for _,row in edited_fields_df.iterrows():
                    field_name=str(row.get("Field","")).strip()
                    if not field_name:
                        continue
                    rebuilt_fields[field_name]={"value":row.get("Value",""),"source_page":row.get("Source page","")}
                editable_value["fields"]=rebuilt_fields
            with excel_tabs[1]:
                updated_tables=[]
                for table_index,table in enumerate(editable_value.get("tables",[]) if isinstance(editable_value.get("tables",[]),list) else []):
                    if not isinstance(table,dict):
                        continue
                    table_rows=table.get("rows") or []
                    if table_rows and isinstance(table_rows[0],list):
                        columns=table.get("columns") or table.get("headers") or []
                        table_rows=[dict(zip(columns,row)) for row in table_rows]
                    edited_rows=st.data_editor(pd.DataFrame(table_rows),num_rows="dynamic",use_container_width=True,key=f"preview_excel_table_{doc['id']}_{table_index}")
                    updated_table=dict(table)
                    updated_table["rows"]=edited_rows.fillna("").to_dict(orient="records")
                    updated_tables.append(updated_table)
                if updated_tables:
                    editable_value["tables"]=updated_tables
        elif selected_format=="Word":
            st.markdown("#### Document preview")
            st.markdown(editable_value.get("summary","No summary available."))
            st.json({"document_type":editable_value.get("document_type"),"fields":editable_value.get("fields"),"tables":editable_value.get("tables")})
        else:
            files=all_exports(latest_value)
            with zipfile.ZipFile(io.BytesIO(files["all_exports.zip"])) as archive:
                st.dataframe(pd.DataFrame({"Files in ZIP":archive.namelist()}),use_container_width=True,hide_index=True)
        st.session_state.export_edit_buffers[doc_key]=json.loads(json.dumps(editable_value))
        edited_export_snapshot=json.dumps(editable_value,sort_keys=True,default=str)
        current_edit_detected=edited_export_snapshot!=st.session_state.last_saved_export_snapshot.get(doc_key,latest_snapshot)
        st.session_state.export_dirty_docs[doc_key]=current_edit_detected
        export_edits_detected=current_edit_detected
        selected_name=formats[selected_format]
        selected_data=all_exports(extraction(db,doc["id"]))[selected_name]
        action_left,action_right=st.columns(2)
        if export_edits_detected:
            with action_left:
                if st.button("Save and export edits",use_container_width=True,key=f"save_export_edits_{doc['id']}"):
                    save_correction(db,doc["id"],editable_value)
                    saved_snapshot=json.dumps(editable_value,sort_keys=True,default=str)
                    st.session_state.last_saved_export_snapshot[doc_key]=saved_snapshot
                    st.session_state.saved_correction_snapshot[doc_key]=saved_snapshot
                    st.session_state.export_dirty_docs[doc_key]=False
                    st.success("Export edits saved. Download and Outlook actions are now enabled with updated data.")
                    st.rerun()
            with action_right:
                st.info("Save changes to enable Download and Outlook actions.")
        else:
            with action_left:
                st.download_button(f"Download {selected_format}",selected_data,file_name=selected_name,use_container_width=True,key=f"download_{doc['id']}_{selected_format.lower()}")
            with action_right:
                if st.link_button("Send via Outlook",url="https://outlook.office.com/mail/",width="stretch",key=f"outlook_{doc['id']}_{selected_format.lower()}"):
                    log_plugin(db,doc["id"],"outlook_web_open","success",{"format":selected_format})
                    st.rerun()

def _chat(settings,db):
    st.markdown("<div class='hero'><h1>Your document conversation</h1><p>Attach a document, analyze it, correct its data, export it, or simply ask a question.</p></div>",unsafe_allow_html=True)
    _upload(settings,db)
    doc=_document_picker(db)
    _analysis(settings,db,doc)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    prompt=st.chat_input("Ask about your document…")
    if prompt:
        st.session_state.messages.append({"role":"user","content":prompt})
        if not doc: reply="Attach or select a PDF first."
        elif not settings.gemini_configured: reply="Your PDF is stored. Add GEMINI_API_KEY to .env and restart DocuMind for AI-powered answers."
        else:
            try: reply=answer(settings,[{"number":p["page_number"],"text":p["native_text"] or ""} for p in doc["pages"]],prompt)
            except IntelligenceError as exc: reply=str(exc)
        st.session_state.messages.append({"role":"assistant","content":reply}); st.rerun()
    batch_ids=st.session_state.batch_document_ids
    if len(batch_ids)>1:
        st.subheader("Document outputs")
        tabs=st.tabs([f"{get_document(db,document_id)['filename']} · {get_document(db,document_id).get('document_type') or 'Type pending'}" for document_id in batch_ids])
        for tab,document_id in zip(tabs,batch_ids):
            with tab:
                batch_doc=get_document(db,document_id)
                st.markdown(f"#### {batch_doc['filename']}")
                st.caption(f"Identified type: **{batch_doc.get('document_type') or 'Not identified yet'}** · {batch_doc['page_count']} pages · {batch_doc['processing_status']}")
                if batch_doc.get("processing_status") in ("complete","partial") and extraction(db,document_id):
                    _workspace(settings,db,batch_doc)
                else:
                    st.info("Analyze this batch to display this document's extraction.")
    else:
        _workspace(settings,db,doc)

def _library(db):
    st.markdown("<div class='hero'><h1>Document library</h1><p>Your stored files and their processing metadata.</p></div>",unsafe_allow_html=True)
    docs=_session_documents(db)
    if not docs: st.info("No documents stored yet. Add one from Chat."); return
    for d in docs:
        with st.container(border=True):
            a,b,c,dcol=st.columns([4,1,2,2])
            a.markdown(f"**{d['filename']}**"); b.write(f"{d['page_count']} pages"); c.write(d.get("document_type") or "Unclassified"); dcol.write(d["processing_status"])
            st.caption(f"Stored {d['created_at']} · {d.get('summary') or 'No summary yet'}")
            if st.button("Open in chat",key=f"open_{d['id']}"): st.session_state.document_id=d["id"]; st.session_state.view="Chat"; st.rerun()

def render_application(settings):
    _init(); _style(); _sidebar(settings)
    if st.session_state.view=="Library": _library(settings.database_path)
    else: _chat(settings,settings.database_path)
