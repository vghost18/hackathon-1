from pathlib import Path

from idp_assistant.config import load_settings


def test_load_settings_uses_supplied_data_directory(tmp_path: Path) -> None:
    """Changing the supplied directory must change both persistence paths."""
    settings = load_settings(tmp_path)

    assert settings.data_dir == tmp_path
    assert settings.database_path == tmp_path / "documind.sqlite3"


def test_load_settings_reports_missing_gemini_key(
    monkeypatch, tmp_path: Path
) -> None:
    """A missing credential must never be treated as a configured connection."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert load_settings(tmp_path).gemini_configured is False


def test_load_settings_treats_whitespace_key_as_not_configured(
    monkeypatch, tmp_path: Path
) -> None:
    """Whitespace credentials cannot accidentally enable AI features."""
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    assert load_settings(tmp_path).gemini_api_key is None
