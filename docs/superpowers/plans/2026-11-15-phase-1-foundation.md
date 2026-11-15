# Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable, polished Streamlit chat shell with durable SQLite initialization and Phase 1 documentation.

**Architecture:** A minimal `app.py` configures Streamlit and delegates to focused configuration, database, and UI modules under `src/idp_assistant`. SQLite initialization is idempotent and independently tested; the UI uses session state only for the Phase 1 placeholder conversation.

**Tech Stack:** Python 3.11+, Streamlit, SQLite, python-dotenv, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-phase-1-foundation-design.md`

## Global Constraints

- Implement only Phase 1: no PDF upload/storage workflow, Gemini call, extraction, export, email, API publishing, or plugin execution.
- Use a configurable `IDP_DATA_DIR`, defaulting to `data/`.
- Keep Gemini credentials optional and never display or commit them.
- SQLite initialization must enable foreign keys and preserve the original/corrected extraction separation for later phases.
- Use a modular Streamlit structure; do not create an oversized monolithic `app.py`.

## Review Focus

- Missing `GEMINI_API_KEY` must display a safe “not configured” state; tested in Task 1.
- A fresh, nested data directory must be created automatically before database connection; tested in Task 2.
- Re-running schema initialization must not erase existing durable records; tested in Task 2.
- Database foreign-key enforcement must reject orphan child records; tested in Task 2.
- Chat input must not imply a live AI response or call external services; smoke-checked in Task 3.

---

## File structure

- `app.py`: Streamlit entry point; page setup, database initialization, and screen rendering.
- `src/idp_assistant/__init__.py`: package marker.
- `src/idp_assistant/config.py`: immutable environment settings and Gemini readiness status.
- `src/idp_assistant/db.py`: connection creation and idempotent schema initialization.
- `src/idp_assistant/ui.py`: custom styling, sidebar, phase-aware sections, and chat-screen rendering.
- `tests/conftest.py`: makes `src/` importable in pytest.
- `tests/test_config.py`: configuration behavior tests.
- `tests/test_db.py`: database schema, idempotence, and foreign-key tests.
- `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `DEVELOPMENT_STATUS.md`: setup, project status, and safe defaults.

### Task 1: Project configuration

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/idp_assistant/__init__.py`
- Create: `src/idp_assistant/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` dataclass and `load_settings(data_dir: str | Path | None = None) -> Settings`.
- Consumes: environment variables `IDP_DATA_DIR`, `GEMINI_API_KEY`, and optional `GEMINI_MODEL`.

- [ ] **Step 1: Write the failing configuration tests**

```python
def test_load_settings_uses_supplied_data_directory(tmp_path):
    assert load_settings(tmp_path).data_dir == tmp_path

def test_load_settings_reports_missing_gemini_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert load_settings(tmp_path).gemini_configured is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_config.py -v`
Expected: FAIL because the package/module does not exist.

- [ ] **Step 3: Implement `Settings` and `load_settings` in `src/idp_assistant/config.py`**

`Settings` exposes `data_dir: Path`, `database_path: Path`, `gemini_api_key: str | None`, `gemini_model: str`, and `gemini_configured: bool`. Load `.env`, select an explicit argument before `IDP_DATA_DIR`, default to `data`, and strip whitespace-only keys to `None`.

- [ ] **Step 4: Add dependency, environment-template, import-path, and ignore files**

Declare exact Phase 1 dependencies (`streamlit`, `python-dotenv`, `pytest`), document safe non-secret variables in `.env.example`, and ignore `.env`, `data/`, caches, and virtual environments.

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore src/idp_assistant tests
git commit -m "feat: add foundation configuration"
```

### Task 2: SQLite persistence foundation

**Files:**
- Create: `src/idp_assistant/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Consumes: `database_path: Path` from `Settings`.
- Produces: `get_connection(database_path: Path) -> sqlite3.Connection` and `initialize_database(database_path: Path) -> None`.

- [ ] **Step 1: Write failing database tests**

```python
def test_initialize_database_creates_schema_and_indexes(tmp_path):
    initialize_database(tmp_path / "nested" / "idp.sqlite3")
    assert "documents" in table_names(...)

def test_initialize_database_is_idempotent_and_preserves_rows(tmp_path):
    # insert a conversation, initialize again, and assert it remains

def test_connection_enforces_foreign_keys(tmp_path):
    # an orphan message insert raises sqlite3.IntegrityError
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_db.py -v`
Expected: FAIL because database module does not exist.

- [ ] **Step 3: Implement `get_connection` and `initialize_database` in `src/idp_assistant/db.py`**

Create parent directories, enable `PRAGMA foreign_keys = ON` for every connection, and use transactional idempotent DDL for the six specified tables: `documents`, `conversations`, `messages`, `extraction_versions`, `generated_files`, and `plugin_executions`. Add the indexes defined by the design contract.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/idp_assistant/db.py tests/test_db.py
git commit -m "feat: initialize durable SQLite foundation"
```

### Task 3: Streamlit chat shell

**Files:**
- Create: `src/idp_assistant/ui.py`
- Create: `app.py`
- Create: `README.md`
- Create: `DEVELOPMENT_STATUS.md`

**Interfaces:**
- Consumes: `Settings`, `initialize_database`, and Streamlit session state.
- Produces: `render_application(settings: Settings) -> None` and a runnable `app.py` entry point.

- [ ] **Step 1: Write UI behavior checklist**

Record a manual smoke checklist in `DEVELOPMENT_STATUS.md`: sidebar identity; New Chat; document-library and history placeholders; settings; Gemini configured/not-configured indicator; chat composer; local placeholder response; no external call.

- [ ] **Step 2: Implement `render_application(settings: Settings) -> None` in `src/idp_assistant/ui.py`**

Render scoped ChatGPT-inspired CSS, sidebar navigation, an accessible Gemini status indicator, conversation bubbles, empty state, and a composer. A submitted message is stored in session state and receives explicit Phase 1 local acknowledgement copy.

- [ ] **Step 3: Implement `app.py`**

Set page configuration, call `load_settings()`, initialize `settings.database_path`, and call `render_application(settings)`.

- [ ] **Step 4: Document installation and startup**

README must give virtual-environment setup, `pip install -r requirements.txt`, `streamlit run app.py`, environment configuration, tested commands, and Phase 1 boundaries. `DEVELOPMENT_STATUS.md` records completed scope, pending Phase 2, architecture decisions, known issues, and actual verification results after execution.

- [ ] **Step 5: Run automated tests and UI smoke check**

Run: `pytest -v`
Expected: PASS.

Run: `streamlit run app.py --server.headless true` and inspect the launched local server/UI.
Expected: app loads without exception, shows the branded chat shell, and creates the SQLite database.

- [ ] **Step 6: Commit**

```bash
git add app.py src/idp_assistant/ui.py README.md DEVELOPMENT_STATUS.md
git commit -m "feat: add Phase 1 Streamlit assistant shell"
```

### Task 4: Final Phase 1 verification

**Files:**
- Modify: `DEVELOPMENT_STATUS.md`

**Interfaces:**
- Consumes: complete Tasks 1–3.
- Produces: recorded, evidence-based Phase 1 completion status.

- [ ] **Step 1: Run final automated suite**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 2: Run final Streamlit startup smoke check**

Run: `streamlit run app.py --server.headless true`
Expected: server starts cleanly and SQLite data directory is present.

- [ ] **Step 3: Update actual results in `DEVELOPMENT_STATUS.md`**

Record commands, pass counts, UI smoke result, and any known Phase 1 limitations; do not claim an unperformed verification.

- [ ] **Step 4: Commit**

```bash
git add DEVELOPMENT_STATUS.md
git commit -m "docs: record Phase 1 verification"
```

## Self-review

- **Spec coverage:** Tasks 1–3 cover project initialization, full UI shell, settings, SQLite initialization, Gemini readiness status, and documentation. Later-phase document, AI, extraction, export, and integration requirements are intentionally excluded.
- **Step scan:** Each task has an explicit test or smoke outcome, named implementation interfaces, and one scope-delimited deliverable.
- **Type consistency:** `Settings`, `load_settings`, `get_connection`, `initialize_database`, and `render_application` use consistent names and signatures throughout.
- **Review focus:** Each listed risk maps to Task 1, 2, or 3 verification.
- **Proportion:** The plan defines interfaces, tests, and boundaries without prescribing module bodies.

