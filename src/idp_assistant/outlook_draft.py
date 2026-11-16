"""Windows Outlook draft creation for user-reviewed messages."""
from __future__ import annotations

from pathlib import Path
import os
import platform
import subprocess
import sys
import tempfile


class OutlookDraftError(RuntimeError):
    """Raised when a local Outlook draft cannot be opened."""


def open_draft(
    data_dir: Path,
    filename: str,
    content: bytes,
    document_name: str,
) -> None:
    """Write an attachment locally and open, but never send, an Outlook draft."""
    attachment_dir = data_dir / "outlook_drafts"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    attachment_path = attachment_dir / filename
    attachment_path.write_bytes(content)

    subject = f"DocuMind document export — {document_name}"
    body = (
        "Please find the selected DocuMind export attached.\n"
        "Review the draft and send when ready."
    )

    if platform.system().lower().startswith("win"):
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

        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            draft = outlook.CreateItem(0)
            draft.Subject = subject
            draft.Body = body
            draft.Attachments.Add(str(attachment_path.resolve()))
            draft.Display()
            return
        except Exception as exc:
            raise OutlookDraftError(
                "Unable to open a local Outlook draft via Outlook COM. Confirm classic Outlook (desktop) "
                "is installed, a mail profile is configured, and Outlook can open normally. "
                f"Current interpreter: {sys.executable}. Underlying error: {exc}"
            ) from exc

    # Non-Windows fallback: open default mail client with subject/body and local file path in body.
    try:
        import urllib.parse
        body_with_hint = body + f"\n\nAttachment file path:\n{attachment_path.resolve()}"
        mailto_url = (
            "mailto:"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body_with_hint)}"
        )
        if platform.system().lower() == "darwin":
            subprocess.run(["open", mailto_url], check=True)
        else:
            subprocess.run(["xdg-open", mailto_url], check=True)
    except Exception as exc:
        raise OutlookDraftError(
            "Outlook COM attachment flow is Windows-only. On this OS, a mail draft can be opened without auto-attachment. "
            f"Attachment has been saved at: {attachment_path.resolve()}. "
            f"Open it manually and attach it in your mail client. Underlying error: {exc}"
        ) from exc
