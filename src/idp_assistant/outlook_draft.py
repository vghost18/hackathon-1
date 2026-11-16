"""Windows Outlook draft creation for user-reviewed messages."""
from __future__ import annotations

from pathlib import Path
import sys


class OutlookDraftError(RuntimeError):
    """Raised when a local Outlook draft cannot be opened."""


def open_draft(
    data_dir: Path,
    filename: str,
    content: bytes,
    document_name: str,
) -> None:
    """Write an attachment locally and open, but never send, an Outlook draft."""
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise OutlookDraftError(
            "Outlook draft support needs pywin32 in the same interpreter running this app.\n"
            f"Current interpreter: {sys.executable}\n"
            "Install with:\n"
            f"  \"{sys.executable}\" -m pip install -r requirements.txt\n"
            f"  \"{sys.executable}\" -m pip install pywin32\n"
            "Then restart Streamlit using the same interpreter:\n"
            f"  \"{sys.executable}\" -m streamlit run app.py\n"
            f"Original import error: {exc}"
        ) from exc

    attachment_dir = data_dir / "outlook_drafts"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    attachment_path = attachment_dir / filename
    attachment_path.write_bytes(content)

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        draft = outlook.CreateItem(0)
        draft.Subject = f"DocuMind document export — {document_name}"
        draft.Body = "A DocuMind document export is attached for your review."
        draft.Attachments.Add(str(attachment_path.resolve()))
        draft.Display()
    except Exception as exc:
        raise OutlookDraftError(
            "Unable to open a local Outlook draft. Confirm classic Outlook (desktop) is installed, "
            "a mail profile is configured, and Outlook can open normally. "
            f"Current interpreter: {sys.executable}. "
            f"Underlying error: {exc}"
        ) from exc
