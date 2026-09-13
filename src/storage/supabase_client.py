"""
Supabase singleton client — cached across Streamlit rerenders.
"""
from __future__ import annotations

import streamlit as st
from src.config import SUPABASE_URL, SUPABASE_KEY


@st.cache_resource(show_spinner=False)
def get_supabase_client():
    """Return a Supabase client, cached by Streamlit for the server lifetime."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .env or .streamlit/secrets.toml. "
            "See .env.example for details."
        )
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

