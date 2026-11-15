"""Streamlit entry point for the DocuMind Phase 1 foundation."""

import sys
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parent / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from idp_assistant.config import load_settings
from idp_assistant.db import initialize_database
from idp_assistant.ui import render_application

import streamlit as st


st.set_page_config(
    page_title="DocuMind",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = load_settings()
initialize_database(settings.database_path)
render_application(settings)
