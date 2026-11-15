# Remaining Phases Implementation Plan

**Goal:** Complete Phases 2–9 as one modular Streamlit release built on the approved Phase 1 foundation.

**Scope:** PDF ingestion and deduplication; page-aware text analysis; optional Gemini intelligence; stored conversations; editable corrected extractions; CSV/Excel/Word/JSON/ZIP exports; controlled plugin registry; Microsoft Graph sending; controlled API publishing; documentation and runtime smoke checks.

**Architecture:**
- `storage.py` owns PDF validation, SHA-256 storage, SQLite retrieval, pages, conversations, corrections, and audit writes.
- `intelligence.py` owns Gemini-only interpretation behind an explicit configuration gate. It never triggers Python operations.
- `processing.py` coordinates safe Python extraction coverage and validated AI results.
- `exporters.py`, `plugins.py`, and `integrations.py` execute allowlisted local actions and report every outcome.
- `ui.py` composes the Streamlit workflow without containing persistence, model, or export logic.

**Key implementation rulings:**
- Gemini requests are optional: no credentials means the UI remains useful for storage, native-text coverage, editing, and exports.
- AI JSON is validated, preserved as original data, and never executes Python, SQL, shell, URL, or plugin code.
- Outlook and API publishing are explicit user-button actions, remain unavailable until their environment configuration exists, and log outcomes.
- Runtime and compile smoke checks replace pytest in this run at the user’s instruction.

**Build order:** dependencies/schema → domain/storage → intelligence/processing → exports/plugins/integrations → expanded UI → docs/runtime smoke check.

