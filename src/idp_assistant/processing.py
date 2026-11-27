"""Coverage-aware processing orchestration."""
from __future__ import annotations

from idp_assistant.local_processing import local_analyse_document
from idp_assistant.storage import save_processing
from idp_assistant.validation import run_validations
from idp_assistant.workflow import process_document_with_graph


def _process_document_local(settings, database_path, document):
    result = local_analyse_document(document["storage_path"], document["filename"])
    validation_issues = run_validations(result)
    result["validation_issues"] = validation_issues
    coverage = {
        "total_pages": document.get("page_count", 1),
        "processed_pages": document.get("page_count", 1),
        "successful_pages": document.get("page_count", 1),
        "pages_requiring_review": [],
        "failed_pages": [],
        "validation_issue_count": len(validation_issues),
        "validation_error_count": sum(1 for issue in validation_issues if issue.get("severity") == "error"),
        "validation_warning_count": sum(1 for issue in validation_issues if issue.get("severity") == "warning"),
    }
    result["coverage_report"] = coverage
    pages = [
        {
            "page_number": page["page_number"],
            "status": "native_text",
            "review_required": False,
            "error": None,
        }
        for page in document.get("pages", [])
    ]
    save_processing(
        database_path,
        document["id"],
        result.get("document_type", "unknown"),
        result.get("summary", ""),
        result,
        "partial" if validation_issues else "complete",
        pages,
    )
    return result


def process_document(settings,database_path,document):
    if getattr(settings, "local_mode", False):
        return _process_document_local(settings, database_path, document)
    return process_document_with_graph(settings, database_path, document)
