from __future__ import annotations

import streamlit as st

from quantumnet.gui.config_io import default_config_path
from quantumnet.gui.pages.parameters import render_parameters_page
from quantumnet.gui.pages.version import render_version_page
from quantumnet.gui.ui import setup_page


def main() -> None:
    setup_page()
    config_path = default_config_path()

    def _parameters_page() -> None:
        render_parameters_page(config_path)

    def _version_page() -> None:
        render_version_page(config_path)

    navigation = st.navigation(
        [
            st.Page(_parameters_page, title="Parameters", url_path="parameters", default=True),
            st.Page(_version_page, title="Version", url_path="version"),
        ],
        position="sidebar",
    )
    navigation.run()


if __name__ == "__main__":
    main()
