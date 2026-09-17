"""Shared frontend task text inputs."""

from __future__ import annotations

DEFAULT_TASK_TEXTS = [
    "拥有至少 900 金币",
    "制作一把铁剑",
]

TASK_TEXTS_KEY = "custom_task_texts"


def render_task_inputs() -> None:
    import streamlit as st

    _ensure_task_texts()
    with st.container(border=True):
        title_col, action_col = st.columns([5, 1])
        title_col.subheader("任务")
        if action_col.button("新增任务", use_container_width=True):
            st.session_state[TASK_TEXTS_KEY].append("")
            st.rerun()

        updated = []
        for index, text in enumerate(st.session_state[TASK_TEXTS_KEY], start=1):
            text_col, delete_col = st.columns([8, 1])
            with text_col:
                updated.append(
                    st.text_area(
                        f"任务 {index}",
                        value=text,
                        height=78,
                        key=f"custom_task_text_{index}",
                    )
                )
            with delete_col:
                st.write("")
                st.write("")
                if st.button(
                    "删除",
                    key=f"delete_task_{index}",
                    disabled=len(st.session_state[TASK_TEXTS_KEY]) <= 1,
                    use_container_width=True,
                ):
                    st.session_state[TASK_TEXTS_KEY].pop(index - 1)
                    _clear_task_widget_keys()
                    st.rerun()
        st.session_state[TASK_TEXTS_KEY] = updated


def get_task_texts() -> list[str]:
    _ensure_task_texts()
    return [text.strip() for text in _raw_task_texts() if text.strip()]


def _ensure_task_texts() -> None:
    import streamlit as st

    if TASK_TEXTS_KEY not in st.session_state:
        st.session_state[TASK_TEXTS_KEY] = list(DEFAULT_TASK_TEXTS)


def _raw_task_texts() -> list[str]:
    import streamlit as st

    value = st.session_state.get(TASK_TEXTS_KEY, DEFAULT_TASK_TEXTS)
    return value if isinstance(value, list) else list(DEFAULT_TASK_TEXTS)


def _clear_task_widget_keys() -> None:
    import streamlit as st

    for key in list(st.session_state):
        if str(key).startswith(("custom_task_text_", "delete_task_")):
            st.session_state.pop(key, None)
