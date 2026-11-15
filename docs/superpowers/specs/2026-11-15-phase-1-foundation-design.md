# Phase 1 Foundation Design

## Intent

Create the first usable shell of an intelligent document-processing assistant: a polished, ChatGPT-inspired Streamlit experience backed by persistent SQLite. It gives users a credible workspace before document upload, AI processing, extraction, exports, and integrations are introduced in later phases.

## Scope

Phase 1 delivers only the project foundation, chat-oriented UI shell, settings surface, SQLite initialization, and automated tests for these foundations. It does not upload, store, analyse, or send documents; it does not call Gemini or any external service.

## Goals

- A runnable Python 3.11+ Streamlit application with a responsive chat workspace.
- Sidebar sections for new chat, document library, recent conversations, processing history, settings, and Gemini connection status.
- Session-state-backed placeholder conversation interactions that are clearly non-AI until Phase 3.
- An idempotent SQLite schema for documents, conversations, messages, extraction versions, generated files, and plugin execution history, ready for future phases.
- Environment-driven settings and safe handling of an optional Gemini API key.
- Focused tests for database creation, schema presence, and UI-independent configuration behavior.

## Non-goals / anti-goals

- No fake PDF processing, AI extraction, export, Outlook, API publishing, or plugin execution.
- No external network calls or Gemini quota consumption.
- No monolithic `app.py`; UI orchestration remains small and application concerns live in modules.
- No credentials committed to the repository.

## Constraints

- Python, Streamlit, SQLite, and the libraries mandated by the product brief.
- The provided project brief is the requirements source; Phase 1 declares `streamlit`, `python-dotenv`, and `pytest`. Later phases add only the brief's relevant packages when their features are implemented (PyMuPDF, Google Gen AI SDK, Pydantic, Pandas, OpenPyXL, python-docx, MSAL, and HTTP client support).
- Preserve durable data across restarts in a configurable application-data directory.
- Future schemas must preserve original and corrected extraction data separately and retain foreign-key relationships.
- The user chose the modular Streamlit approach.

## Approaches considered

1. **Modular Streamlit application (selected):** a small Streamlit entry point delegates to database, configuration, and UI modules. This makes Phase 2+ additions independently testable and maintainable.
2. **Single-file Streamlit app:** quickest initial screen but conflicts with the brief's maintainability requirement and would make later plugins and storage difficult to isolate.
3. **Separate web backend plus frontend:** useful for multi-user scale, but unnecessary complexity for the requested initial Streamlit product.

## Architecture

```
Streamlit entry point
  ├── app configuration / session state
  ├── UI components and custom CSS
  └── services
       ├── settings (environment configuration)
       └── database (SQLite connection + migrations)

tests
  ├── database schema / persistence tests
  └── settings tests
```

### Proposed layout

- `app.py`: minimal executable entry point.
- `src/idp_assistant/config.py`: typed environment settings.
- `src/idp_assistant/db.py`: SQLite connection and idempotent schema initialization.
- `src/idp_assistant/ui.py`: chat shell, sidebar, and presentation helpers.
- `tests/`: pytest tests for non-UI foundations.
- `.env.example`, `requirements.txt`, `README.md`, and `DEVELOPMENT_STATUS.md`: setup and project status.

### UI behavior

The application starts on a conversation screen with a branded sidebar. Selecting New Chat clears the current in-memory placeholder conversation. The composer records a visible local message and replies that document intelligence will arrive in Phase 3; it makes no model call. The document library and history areas visibly state that their operational functionality begins in later phases. Settings expose non-secret configuration status and the Gemini key's configured/not-configured state without displaying the key.

### Database behavior

`initialize_database()` creates the data directory, enables foreign keys, and runs `CREATE TABLE IF NOT EXISTS` statements. The schema is intentionally broader than the Phase 1 UI so later phases can add behavior without a destructive migration. It includes indexed document hashes and timestamps, conversation/message relationships, extraction original/corrected payload columns, generated-file records, and plugin-execution audit records.

#### Phase 1 schema contract

| Table | Foundation columns and relationships |
| --- | --- |
| `documents` | ID, unique SHA-256 hash, filename, storage path, metadata JSON, page count, type, status, summary, original/corrected extraction JSON, timestamps. |
| `conversations` | ID, optional active document reference, title, timestamps. |
| `messages` | ID, required conversation reference, role, content, optional metadata JSON, timestamp. |
| `extraction_versions` | ID, required document reference, version kind (`original`/`corrected`), payload JSON, timestamp. |
| `generated_files` | ID, required document reference, optional conversation reference, format, storage path, metadata JSON, timestamp. |
| `plugin_executions` | ID, optional document/conversation references, plugin name, status, input/output JSON, error text, timestamps. |

Foreign keys use `ON DELETE CASCADE` for child records; `documents.file_hash`, document status/type, message conversation IDs, and audit foreign-key columns are indexed. This initializes persistence only—no Phase 1 UI writes document, export, or execution records.

## Builder decisions

- Use a local `data/` directory by default, overridable with `IDP_DATA_DIR`.
- Use a neutral product identity, **DocuMind**, until branding is supplied.
- Use built-in Streamlit widgets plus scoped custom CSS rather than third-party UI packages.
- Treat the Gemini configuration as optional and report only connection readiness, not a verified connection, because Phase 1 must not make external calls.

## Verification

- Install declared dependencies in an isolated environment.
- Run `pytest` for schema/configuration tests.
- Launch Streamlit and inspect the app through its local server response; where available, perform a browser/UI smoke check.
- Update `DEVELOPMENT_STATUS.md` with commands and actual test results.

## Open implementation details

Exact CSS values, database column naming, and internal helper names are implementation choices as long as the behavior and boundaries above are retained.
