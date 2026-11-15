import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_renders_phase_one_chat_shell(tmp_path: Path, monkeypatch) -> None:
    """The actual Streamlit entry point must render without a configured key."""
    monkeypatch.setenv("IDP_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    source_path = str(Path(__file__).resolve().parents[1] / "src")
    monkeypatch.setattr(
        sys, "path", [entry for entry in sys.path if Path(entry).resolve() != Path(source_path)]
    )

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run(timeout=10)

    assert not app.exception
    assert any("DocuMind" in header.value for header in app.header)
    assert any("not configured" in markdown.value.lower() for markdown in app.markdown)
