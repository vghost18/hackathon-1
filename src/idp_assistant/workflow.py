"""LangGraph orchestration for document processing.

The graph coordinates deterministic Python steps and the existing Gemini
boundary. LangChain is used for prompt templating; no model output executes
application operations.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from idp_assistant.intelligence import analyse, IntelligenceError
from idp_assistant.storage import load_processing_pages, save_processing


class ProcessingState(TypedDict, total=False):
    settings: Any
    database_path: Any
    document: dict[str, Any]
    pages: list[dict[str, Any]]
    report: list[dict[str, Any]]
    result: dict[str, Any]
    error: str


ANALYSIS_INSTRUCTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a document analysis assistant. Return structured JSON only. "
            "Never invent values and preserve page provenance.",
        ),
        ("human", "{document_text}"),
    ]
)


def _prepare(state: ProcessingState) -> ProcessingState:
    pages = load_processing_pages(state["document"])
    report = [
        {
            "page_number": page["number"],
            "status": "native_text" if page.get("text", "").strip() else "needs_visual_review",
            "review_required": not bool(page.get("text", "").strip()),
        }
        for page in pages
    ]
    return {"pages": pages, "report": report}


def _analyze(state: ProcessingState) -> ProcessingState:
    try:
        return {"result": analyse(state["settings"], state["pages"])}
    except IntelligenceError as exc:
        return {"error": str(exc)}


def _persist(state: ProcessingState) -> ProcessingState:
    if state.get("error"):
        return state
    result = state["result"]
    report = state["report"]
    confidence = float(result.get("confidence", 0.0) or 0.0)
    if confidence < 0.45:
        result["document_type"] = "unknown"
    coverage = {
        "total_pages": len(report),
        "processed_pages": len(report),
        "successful_pages": sum(not page["review_required"] for page in report),
        "pages_requiring_review": [
            page["page_number"] for page in report if page["review_required"]
        ],
        "failed_pages": [],
    }
    result["coverage_report"] = coverage
    save_processing(
        state["database_path"],
        state["document"]["id"],
        result.get("document_type", "Other"),
        result.get("summary", ""),
        result,
        "partial" if coverage["pages_requiring_review"] else "complete",
        report,
    )
    return {"result": result}


def _route(state: ProcessingState) -> str:
    return "error" if state.get("error") else "persist"


def _build_graph():
    graph = StateGraph(ProcessingState)
    graph.add_node("prepare", _prepare)
    graph.add_node("analyze", _analyze)
    graph.add_node("persist", _persist)
    graph.add_node("error", lambda state: state)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "analyze")
    graph.add_conditional_edges("analyze", _route, {"persist": "persist", "error": "error"})
    graph.add_edge("persist", END)
    graph.add_edge("error", END)
    return graph.compile()


PROCESSING_GRAPH = _build_graph()


def process_document_with_graph(settings, database_path, document):
    """Run one document through the LangGraph processing workflow."""
    state = PROCESSING_GRAPH.invoke(
        {
            "settings": settings,
            "database_path": database_path,
            "document": document,
        }
    )
    if state.get("error"):
        raise IntelligenceError(state["error"])
    return state["result"]
