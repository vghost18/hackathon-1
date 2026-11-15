# DocuMind

DocuMind is an intelligent document-processing assistant built with Python and Streamlit.

## Phase 1

DocuMind supports local PDF storage with SHA-256 duplicate prevention, page-level native text coverage, optional Gemini classification/summarization/extraction/Q&A, editable corrected JSON, exports, and controlled integrations.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Gemini is optional. Without a key, document storage, native-text coverage, correction, and exports still work; Gemini analysis and Q&A are disabled. API publishing and Outlook actions execute only after an explicit button click and configuration.

## Tests

```powershell
python -m pytest -v
```

## Configuration

- `IDP_DATA_DIR`: directory for the SQLite database; defaults to `data/`.
- `GEMINI_API_KEY`: optional Gemini key, reserved for Phase 3.
- `GEMINI_MODEL`: optional model preference; defaults to `gemini-2.5-flash`.
