"""Chat-first Streamlit experience for DocuMind."""
from __future__ import annotations
import json
import io
import zipfile
import pandas as pd
import streamlit as st
from idp_assistant.storage import ingest_pdf,list_documents,get_document,extraction,save_correction,log_plugin,DocumentError
from idp_assistant.processing import process_document
from idp_assistant.intelligence import answer,IntelligenceError
from idp_assistant.exporters import all_exports
from idp_assistant.outlook_draft import open_draft,OutlookDraftError

def _init():
    st.session_state.setdefault("view","Chat"); st.session_state.setdefault("messages",[]); st.session_state.setdefault("document_id",None)

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
        st.divider()
        if st.button("💬 Chat",use_container_width=True): st.session_state.view="Chat"; st.rerun()
        if st.button("▣ Document library",use_container_width=True): st.session_state.view="Library"; st.rerun()
        st.divider()
        st.success("Gemini ready") if settings.gemini_configured else st.info("Gemini key not set")
        st.caption(f"Model: {settings.gemini_model}")

def _document_picker(db):
    docs=list_documents(db)
    if not docs: return None
    options={f"{d['filename']}  ·  {d['page_count']} pages  ·  {d['processing_status']}":d["id"] for d in docs}
    current=next((i for i,x in enumerate(options.values()) if x==st.session_state.document_id),0)
    label=st.selectbox("Active document",list(options),index=current)
    st.session_state.document_id=options[label]
    return get_document(db,options[label])

def _upload(settings,db):
    with st.expander("Attach a PDF",expanded=not st.session_state.document_id):
        file=st.file_uploader("PDF document",type="pdf",label_visibility="collapsed")
        if file and st.button("Add to conversation",type="primary"):
            try:
                doc,duplicate=ingest_pdf(db,settings.data_dir,file.name,file.getvalue())
                st.session_state.document_id=doc["id"]
                st.session_state.messages.append({"role":"assistant","content":("I found this document in your library and attached it." if duplicate else f"I attached **{doc['filename']}**. Ask me about it, or choose Analyze document.")})
                st.rerun()
            except DocumentError as exc: st.error(str(exc))

def _analysis(settings,db,doc):
    if not doc: return
    left,right=st.columns([3,1])
    with left: st.markdown(f"<div class='doc-chip'>📄 {doc['filename']} · {doc['page_count']} pages · {doc['processing_status']}</div>",unsafe_allow_html=True)
    with right:
        if st.button("Analyze document",disabled=not settings.gemini_configured,use_container_width=True):
            try:
                with st.spinner("Reading pages, checking coverage, and extracting data..."): result=process_document(settings,db,doc)
                st.session_state.messages.append({"role":"assistant","content":f"Analysis complete. I identified this as **{result.get('document_type','Other')}**. {result.get('summary','')}"})
                st.rerun()
            except IntelligenceError as exc: st.error(str(exc))
    if not settings.gemini_configured: st.caption("Add GEMINI_API_KEY in .env, then restart the app to enable analysis.")

def _workspace(settings,db,doc):
    if not doc: return
    value=extraction(db,doc["id"])
    if not value: return
    with st.expander("Review and correct extraction"):
        text=st.text_area("Corrected JSON",json.dumps(value,indent=2),height=320,key=f"json_{doc['id']}")
        if st.button("Save corrections"):
            try: save_correction(db,doc["id"],json.loads(text)); st.success("Corrections saved.")
            except json.JSONDecodeError as exc: st.error(f"Invalid JSON: {exc}")
        for table in value.get("tables",[]):
            st.write(table.get("name","Table")); st.data_editor(table.get("rows",[]),num_rows="dynamic",key=f"table_{doc['id']}_{table.get('name','table')}")
    with st.expander("Export or send"):
        files=all_exports(value)
        formats={"JSON":"extraction.json","CSV":"extraction.csv","Excel":"extraction.xlsx","Word":"extraction.docx","ZIP":"all_exports.zip"}
        selected_format=st.selectbox("Choose output format",list(formats),key=f"format_{doc['id']}")
        selected_name=formats[selected_format]
        selected_data=files[selected_name]
        st.caption(f"Previewing {selected_format}. This is the file you will download or attach to Outlook.")
        if selected_format=="JSON":
            st.json(value)
        elif selected_format=="CSV":
            st.dataframe(pd.read_csv(io.BytesIO(selected_data)),use_container_width=True)
        elif selected_format=="Excel":
            workbook=pd.ExcelFile(io.BytesIO(selected_data))
            sheet_tabs=st.tabs(workbook.sheet_names)
            for tab,sheet in zip(sheet_tabs,workbook.sheet_names):
                with tab: st.dataframe(pd.read_excel(workbook,sheet_name=sheet),use_container_width=True)
        elif selected_format=="Word":
            st.markdown("#### Document preview")
            st.markdown(value.get("summary","No summary available."))
            st.json({"document_type":value.get("document_type"),"fields":value.get("fields"),"tables":value.get("tables")})
        else:
            with zipfile.ZipFile(io.BytesIO(selected_data)) as archive:
                st.dataframe(pd.DataFrame({"Files in ZIP":archive.namelist()}),use_container_width=True,hide_index=True)
        action_left,action_right=st.columns(2)
        with action_left:
            st.download_button(f"Download {selected_format}",selected_data,file_name=selected_name,use_container_width=True)
        with action_right:
            if st.button(f"Open {selected_format} draft in Outlook",use_container_width=True):
                try:
                    open_draft(settings.data_dir,selected_name,selected_data,doc["filename"])
                    log_plugin(db,doc["id"],"outlook_draft","success",{"format":selected_format})
                    st.success("Outlook opened a draft with the selected export attached. Review recipients, then send it yourself.")
                except OutlookDraftError as exc:
                    log_plugin(db,doc["id"],"outlook_draft","failed",{"format":selected_format},error=str(exc))
                    st.error(str(exc))

def _chat(settings,db):
    st.markdown("<div class='hero'><h1>Your document conversation</h1><p>Attach a PDF, analyze it, correct its data, export it, or simply ask a question.</p></div>",unsafe_allow_html=True)
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
    _workspace(settings,db,doc)

def _library(db):
    st.markdown("<div class='hero'><h1>Document library</h1><p>Your stored files and their processing metadata.</p></div>",unsafe_allow_html=True)
    docs=list_documents(db)
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

