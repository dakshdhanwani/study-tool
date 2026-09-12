"""
Three-column workspace layout.
Delegates rendering to component modules.
"""
from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.app.panel_left   import render_left_panel
from src.app.panel_center import render_center_panel
from src.app.panel_right  import render_right_panel


def render_workspace() -> None:
    """Render the full three-column Course Companion UI."""
    # We use three Streamlit columns to approximate the three-panel layout.
    # Ratio  2.2 : 5.8 : 3.0  (left : center : right)
    left_col, center_col, right_col = st.columns([2.2, 5.8, 3.0], gap="small")

    with left_col:
        render_left_panel()

    with center_col:
        render_center_panel()

    with right_col:
        render_right_panel()
