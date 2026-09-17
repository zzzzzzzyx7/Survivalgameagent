"""Agent trace and replay view."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LIVE_EPISODE_KEY = "live_episode"


def render_trace_view(log_dir: str | Path = "logs") -> None:
    import streamlit as st

    st.subheader("轨迹回放")
    live_episode = current_live_episode()
    logs = find_episode_logs(log_dir)
    if live_episode is None and not logs:
        st.info("暂无 episode 轨迹。")
        return

    if live_episode is not None:
        st.write("当前实时运行")
        _render_trace_episode(
            _live_episode_snapshot(live_episode),
            key_prefix="current_live_trace",
        )

    if logs:
        with st.expander("历史日志回放", expanded=live_episode is None):
            selected = st.selectbox(
                "Episode",
                logs,
                format_func=lambda path: path.name,
                key="history_trace_episode",
            )
            _render_trace_episode(
                _load_log_episode(selected),
                key_prefix=f"history_trace_{logs.index(selected)}",
            )


def _render_trace_episode(episode: dict[str, Any], *, key_prefix: str) -> None:
    import streamlit as st

    trace = episode.get("trace", [])
    if not trace:
        st.info("当前 episode 没有轨迹。")
        return

    _render_episode_header(episode)
    _render_day_tables(trace)
    _render_step_detail(trace, key_prefix=key_prefix)


def current_live_episode() -> dict[str, Any] | None:
    import streamlit as st

    live_episode = st.session_state.get(LIVE_EPISODE_KEY)
    if isinstance(live_episode, dict) and live_episode.get("trace"):
        return live_episode
    return None


def _load_log_episode(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _live_episode_snapshot(episode: dict[str, Any]) -> dict[str, Any]:
    game = episode.get("game")
    observation = game.observe() if game is not None else {}
    task = _mapping(episode.get("task"))
    return {
        "agent_type": episode.get("agent_type"),
        "task_id": task.get("task_id"),
        "seed": episode.get("seed"),
        "success": _mapping(observation).get("success"),
        "done": _mapping(observation).get("done"),
        "steps": _mapping(observation).get("step"),
        "total_actions": episode.get("total_actions"),
        "invalid_actions": episode.get("invalid_actions"),
        "replan_count": episode.get("replan_count"),
        "trace": episode.get("trace", []),
    }


def _render_episode_header(episode: dict[str, Any]) -> None:
    import streamlit as st

    cols = st.columns(6)
    cols[0].metric("任务", str(episode.get("task_id", "")))
    cols[1].metric("Agent", str(episode.get("agent_type", "")))
    cols[2].metric("Seed", str(episode.get("seed", "")))
    cols[3].metric("步数", int(episode.get("steps") or 0))
    cols[4].metric("动作", int(episode.get("total_actions") or len(episode.get("trace", []))))
    cols[5].metric("无效", int(episode.get("invalid_actions") or 0))


def _render_day_tables(trace: object) -> None:
    import streamlit as st

    st.write("每日动作链")
    day_groups = group_trace_by_day(trace)
    if not day_groups:
        st.info("当前 episode 没有可回放的每日动作链。")
        return

    last_day = day_groups[-1][0]
    for day, entries in day_groups:
        with st.expander(f"Day {day} 动作链", expanded=day == last_day):
            plan = _first_day_plan(entries)
            if plan:
                final_actions = str(plan.get("final_day_actions", "")).strip()
                if final_actions:
                    st.info(final_actions)
                objective = str(plan.get("day_objective", "")).strip()
                if objective:
                    st.caption(f"本日目标：{objective}")
            st.dataframe(
                action_chain_rows_from_entries(entries, include_day=False),
                use_container_width=True,
                hide_index=True,
            )


def _render_step_detail(trace: object, *, key_prefix: str) -> None:
    import streamlit as st

    trace_entries = _trace_entries(trace)
    st.write("单步详情")
    if len(trace_entries) == 1:
        index = 0
    else:
        index = st.slider(
            "步骤",
            1,
            len(trace_entries),
            1,
            key=f"{key_prefix}_step",
        ) - 1
    step = _mapping(trace_entries[index])
    st.caption(
        f"当前查看 Day {trace_entry_day(step)} / Step {step.get('step')}，"
        f"第 {index + 1} 条记录 / 共 {len(trace_entries)} 条。"
    )
    st.json(
        {
            "decision": step.get("decision"),
            "result": step.get("result"),
            "state_after": step.get("state_after"),
        }
    )


def group_trace_by_day(trace: object) -> list[tuple[int, list[dict[str, Any]]]]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for entry in _trace_entries(trace):
        mapped = _mapping(entry)
        day = trace_entry_day(mapped)
        groups.setdefault(day, []).append(mapped)
    return [(day, groups[day]) for day in sorted(groups)]


def action_chain_rows_from_entries(
    entries: object,
    *,
    include_day: bool = True,
) -> list[dict[str, object]]:
    rows = []
    for index, entry in enumerate(_trace_entries(entries), start=1):
        mapped = _mapping(entry)
        result = _mapping(mapped.get("result"))
        state_after = _mapping(mapped.get("state_after"))
        success = bool(result.get("success"))
        row = {
            "序号": index,
            "状态": "完成" if success else "失败，已触发重规划",
            "动作": _decision_label(mapped.get("decision")),
            "理由": _mapping(mapped.get("decision")).get("reason"),
            "结果": result.get("observation"),
            "错误": result.get("error_code") or "",
            "体力变化": _state_change(result, "energy"),
            "位置": state_after.get("location"),
            "金币": state_after.get("gold"),
            "体力": state_after.get("energy"),
        }
        if include_day:
            row = {"Day": trace_entry_day(mapped), **row}
        rows.append(row)
    return rows


def trace_entry_day(entry: dict[str, Any]) -> int:
    for source_name in ("day",):
        value = entry.get(source_name)
        if value is not None:
            return int(value)
    for state_name in ("state_before", "state_after"):
        state = _mapping(entry.get(state_name))
        value = state.get("day")
        if value is not None:
            return int(value)
    return 1


def _first_day_plan(entries: list[dict[str, Any]]) -> dict[str, Any]:
    for entry in entries:
        plan = _mapping(entry.get("day_plan"))
        if plan:
            return plan
    return {}


def _trace_entries(trace: object) -> list[object]:
    return trace if isinstance(trace, list) else []


def _state_change(result: object, key: str) -> object:
    changes = _mapping(result).get("state_changes")
    return _mapping(changes).get(key) or ""


def _decision_label(decision: object) -> str:
    mapped = _mapping(decision)
    tool = str(mapped.get("tool", ""))
    args = mapped.get("args", {})
    if not isinstance(args, dict) or not args:
        return f"{tool}()"
    args_text = ", ".join(f"{key}={value}" for key, value in args.items())
    return f"{tool}({args_text})"


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def find_episode_logs(log_dir: str | Path = "logs") -> list[Path]:
    return sorted(Path(log_dir).rglob("*.json"))
