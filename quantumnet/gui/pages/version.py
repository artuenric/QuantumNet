from __future__ import annotations

import platform
from pathlib import Path

import streamlit as st


def render_version_page(default_config_path: Path) -> None:
    active_path = Path(st.session_state.get("qn_active_config_path", str(default_config_path))).resolve()
    st.title("Version")
    st.write("Interface and environment information.")

    st.markdown(f"- **Python**: `{platform.python_version()}`")
    st.markdown(f"- **Operating system**: `{platform.system()} {platform.release()}`")
    st.markdown(f"- **Active configuration file**: `{active_path}`")
    st.markdown("- **Streamlit**: active configuration interface")
