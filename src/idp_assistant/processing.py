"""Coverage-aware processing orchestration."""
from __future__ import annotations
from idp_assistant.workflow import process_document_with_graph
def process_document(settings,database_path,document):
    return process_document_with_graph(settings, database_path, document)
