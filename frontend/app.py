"""Streamlit application entry point."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_project_app_package() -> None:
    current = sys.modules.get("app")
    current_file = getattr(current, "__file__", None)
    if current_file is not None and Path(current_file).resolve() != Path(__file__).resolve():
        return

    app_dir = PROJECT_ROOT / "app"
    spec = importlib.util.spec_from_file_location(
        "app",
        app_dir / "__init__.py",
        submodule_search_locations=[str(app_dir)],
    )
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules["app"] = module
    spec.loader.exec_module(module)


_ensure_project_app_package()

from frontend.game_view import render_game_view
from frontend.task_inputs import render_task_inputs
from frontend.trace_view import render_trace_view


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="SurvivalAgent", layout="wide")
    st.title("SurvivalAgent 控制台")
    render_task_inputs()

    game_tab, trace_tab = st.tabs(["实时运行", "轨迹回放"])
    with game_tab:
        render_game_view()
    with trace_tab:
        render_trace_view()


if __name__ == "__main__":
    main()
