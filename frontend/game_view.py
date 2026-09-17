"""Live game view."""

from __future__ import annotations

import time
from typing import Any

from evaluation.runner import (
    make_agent,
    make_all_text_tasks,
    make_game,
    make_text_task,
    run_game_day,
)
from frontend.task_inputs import get_task_texts

AGENT_TYPE = "llm"
SESSION_KEY = "live_episode"
SEED_COUNTER_KEY = "live_seed_counter"
AUTO_RUNNING_KEY = "live_auto_running"
AUTO_STEPS_KEY = "live_auto_steps"
PENDING_ACTION_KEY = "live_pending_action"
TRACE_SLIDER_KEY = "live_trace_step"
AUTO_DAY_LIMIT = 14
AUTO_STEP_PAUSE_SECONDS = 0.25


def render_game_view() -> None:
    import streamlit as st

    st.subheader("实时运行")
    pending_action = st.session_state.get(PENDING_ACTION_KEY)
    auto_running = bool(st.session_state.get(AUTO_RUNNING_KEY, False))
    controls_locked = bool(pending_action) or auto_running
    task_texts = get_task_texts()
    if not task_texts:
        st.warning("请至少保留一条任务。")
        return
    task_options = ["__all__", *range(len(task_texts))]

    control_col, _ = st.columns([2, 3])
    with control_col:
        selected_task_option = st.selectbox(
            "当前任务",
            task_options,
            format_func=lambda option: _task_label(option, task_texts),
            key="live_task_index",
            disabled=controls_locked,
        )

    selected_task = _selected_task(task_texts, selected_task_option)
    config = (selected_task["goal"], selected_task["success_condition"], AGENT_TYPE)
    current = st.session_state.get(SESSION_KEY)
    current_config = current.get("config") if isinstance(current, dict) else None

    if pending_action == "new_game":
        st.session_state[SESSION_KEY] = _new_episode(
            selected_task,
            seed=_next_seed(),
        )
        _clear_pending_action()
        _reset_trace_slider()
        _rerun()
    elif SESSION_KEY not in st.session_state or (
        not controls_locked and current_config != config
    ):
        st.session_state[SESSION_KEY] = _new_episode(
            selected_task,
            seed=_next_seed(),
        )
        _reset_trace_slider()

    episode = st.session_state[SESSION_KEY]
    if _episode_finished(episode):
        auto_running = False
        st.session_state[AUTO_RUNNING_KEY] = False

    controls_locked = bool(st.session_state.get(PENDING_ACTION_KEY)) or auto_running
    run_disabled = controls_locked or _episode_finished(episode)
    new_disabled = controls_locked

    button_col = st.container()
    with button_col:
        new_col, next_col, auto_col, stop_col = st.columns(4)
        with new_col:
            st.button(
                "新游戏",
                use_container_width=True,
                disabled=new_disabled,
                on_click=_queue_action,
                args=("new_game",),
            )
        with next_col:
            st.button(
                "执行一天",
                use_container_width=True,
                disabled=run_disabled,
                on_click=_queue_action,
                args=("run_day",),
            )
        with auto_col:
            st.button(
                "自动运行",
                use_container_width=True,
                disabled=run_disabled,
                on_click=_start_auto_run,
            )
        with stop_col:
            st.button(
                "停止",
                use_container_width=True,
                disabled=not auto_running,
                on_click=_stop_auto_run,
            )

    status_box = st.empty()
    loading_box = st.empty()
    world_box = st.empty()
    action_chain_box = st.empty()
    trace_box = st.empty()

    should_run_day = (
        st.session_state.get(PENDING_ACTION_KEY) == "run_day" or auto_running
    ) and not _episode_finished(episode)
    _render_episode(
        episode,
        status_box,
        world_box,
        action_chain_box,
        trace_box,
        running=should_run_day,
        render_trace=not should_run_day,
    )

    if should_run_day:
        current_day = int(episode["game"].state.day)
        progress_box = loading_box.container()
        with progress_box, st.spinner(f"Agent 正在规划并执行 Day {current_day}..."):
            _run_one_day(
                episode,
                progress_box=progress_box,
                action_chain_box=action_chain_box,
            )
        loading_box.empty()
        if auto_running:
            st.session_state[AUTO_STEPS_KEY] = int(st.session_state.get(AUTO_STEPS_KEY, 0)) + 1
            if st.session_state[AUTO_STEPS_KEY] >= AUTO_DAY_LIMIT:
                st.session_state[AUTO_RUNNING_KEY] = False
        if _episode_finished(episode):
            st.session_state[AUTO_RUNNING_KEY] = False
        _clear_pending_action()
        _render_episode(
            episode,
            status_box,
            world_box,
            action_chain_box,
            trace_box,
            running=bool(st.session_state.get(AUTO_RUNNING_KEY, False)),
            render_trace=False,
        )
        time.sleep(AUTO_STEP_PAUSE_SECONDS)
        _rerun()
        return

    _clear_pending_action()


def _new_episode(task: dict[str, Any], seed: int) -> dict[str, Any]:
    game = make_game(task, seed)
    return _episode_payload(game=game, task=task, seed=seed)


def _episode_payload(
    *,
    game: Any,
    task: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    return {
        "game": game,
        "agent": make_agent(AGENT_TYPE),
        "agent_type": AGENT_TYPE,
        "task": task,
        "seed": seed,
        "config": (task["goal"], task["success_condition"], AGENT_TYPE),
        "trace": [],
        "day_plans": [],
        "total_actions": 0,
        "invalid_actions": 0,
        "replan_count": 0,
        "stopped": False,
        "last_decision": None,
        "last_result": None,
        "last_day_plan": None,
        "last_day_result": None,
        "current_day_plan": None,
        "current_action_chain": [],
        "current_plan_offset": 0,
    }


def _queue_action(action: str) -> None:
    import streamlit as st

    st.session_state[PENDING_ACTION_KEY] = action


def _start_auto_run() -> None:
    import streamlit as st

    st.session_state[AUTO_RUNNING_KEY] = True
    st.session_state[AUTO_STEPS_KEY] = 0


def _stop_auto_run() -> None:
    import streamlit as st

    st.session_state[AUTO_RUNNING_KEY] = False
    st.session_state[PENDING_ACTION_KEY] = None


def _clear_pending_action() -> None:
    import streamlit as st

    st.session_state[PENDING_ACTION_KEY] = None


def _reset_trace_slider() -> None:
    import streamlit as st

    st.session_state.pop(TRACE_SLIDER_KEY, None)


def _rerun() -> None:
    import streamlit as st

    if hasattr(st, "rerun"):
        st.rerun()
    st.experimental_rerun()


def _run_one_day(
    episode: dict[str, Any],
    *,
    progress_box: Any | None = None,
    action_chain_box: Any | None = None,
) -> None:
    if _episode_finished(episode):
        return
    episode["current_day_plan"] = None
    episode["current_action_chain"] = []
    episode["current_plan_offset"] = 0
    day_result = run_game_day(
        str(episode["agent_type"]),
        episode["agent"],
        episode["task"],
        episode["game"],
        on_plan=lambda plan: _handle_running_plan(
            episode,
            plan,
            progress_box=progress_box,
            action_chain_box=action_chain_box,
        ),
        on_trace_entry=lambda entry: _handle_running_entry(
            episode,
            entry,
            progress_box=progress_box,
            action_chain_box=action_chain_box,
        ),
    )
    trace_entries = day_result.get("trace_entries", [])
    if isinstance(trace_entries, list) and trace_entries:
        episode["trace"].extend(trace_entries)
        last_entry = trace_entries[-1]
        episode["last_decision"] = last_entry.get("decision")
        episode["last_result"] = last_entry.get("result")
    episode["last_day_plan"] = day_result.get("last_plan")
    episode["last_day_result"] = day_result
    plans = day_result.get("plans", [])
    if isinstance(plans, list):
        episode["day_plans"].extend(plans)
    episode["total_actions"] += int(day_result.get("total_actions", 0))
    episode["invalid_actions"] += int(day_result.get("invalid_actions", 0))
    episode["replan_count"] += int(day_result.get("replan_count", 0))
    if day_result["stopped"]:
        episode["stopped"] = True


def _handle_running_plan(
    episode: dict[str, Any],
    plan: dict[str, object],
    *,
    progress_box: Any | None,
    action_chain_box: Any | None,
) -> None:
    episode["current_day_plan"] = plan
    chain = episode.get("current_action_chain", [])
    if not isinstance(chain, list):
        chain = []
    episode["current_plan_offset"] = len(chain)
    chain.extend(_planned_action_rows(plan, offset=len(chain)))
    episode["current_action_chain"] = chain
    _render_running_plan(progress_box, plan)
    if action_chain_box is not None:
        with action_chain_box.container():
            _render_action_chain(episode, running=True)


def _handle_running_entry(
    episode: dict[str, Any],
    entry: dict[str, Any],
    *,
    progress_box: Any | None,
    action_chain_box: Any | None,
) -> None:
    _update_action_chain_from_entry(episode, entry)
    _render_running_entry(progress_box, entry)
    if action_chain_box is not None:
        with action_chain_box.container():
            _render_action_chain(episode, running=True)


def _render_running_plan(progress_box: Any | None, plan: dict[str, object]) -> None:
    if progress_box is None:
        return
    progress_box.info(str(plan.get("final_day_actions", "Agent 已生成当天计划。")))


def _render_running_entry(progress_box: Any | None, entry: dict[str, Any]) -> None:
    if progress_box is None:
        return
    result = entry.get("result", {})
    state_after = entry.get("state_after", {})
    progress_box.json(
        {
            "已完成动作": entry.get("decision"),
            "执行结果": result,
                "当前状态": {
                    "day": _mapping_get(state_after, "day"),
                    "energy": _mapping_get(state_after, "energy"),
                    "gold": _mapping_get(state_after, "gold"),
                    "location": _mapping_get(state_after, "location"),
            },
        }
    )


def _mapping_get(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, dict) else None


def _state_change(result: object, key: str) -> object:
    changes = _mapping_get(result, "state_changes")
    return _mapping_get(changes, key) or ""


def _planned_action_rows(plan: dict[str, object], *, offset: int) -> list[dict[str, object]]:
    actions = plan.get("actions", [])
    if not isinstance(actions, list):
        return []
    return [
        {
            "序号": offset + index,
            "状态": "待执行",
            "动作": _decision_label(action),
            "理由": _mapping_get(action, "reason"),
            "结果": "",
            "错误": "",
            "体力变化": "",
            "位置": "",
            "金币": "",
            "体力": "",
        }
        for index, action in enumerate(actions, start=1)
    ]


def _update_action_chain_from_entry(
    episode: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    chain = episode.get("current_action_chain", [])
    if not isinstance(chain, list):
        chain = []
    plan_offset = int(episode.get("current_plan_offset", 0) or 0)
    action_index = plan_offset + int(entry.get("day_action_index", 1) or 1)
    while len(chain) < action_index:
        chain.append(
            {
                "序号": len(chain) + 1,
                "状态": "待执行",
                "动作": "",
                "理由": "",
                "结果": "",
                "错误": "",
                "体力变化": "",
                "位置": "",
                "金币": "",
                "体力": "",
            }
        )

    result = entry.get("result", {})
    state_after = entry.get("state_after", {})
    success = bool(_mapping_get(result, "success"))
    chain[action_index - 1] = {
        "序号": action_index,
        "状态": "完成" if success else "失败，已触发重规划",
        "动作": _decision_label(entry.get("decision")),
        "理由": _mapping_get(entry.get("decision"), "reason"),
        "结果": _mapping_get(result, "observation"),
        "错误": _mapping_get(result, "error_code") or "",
        "体力变化": _state_change(result, "energy"),
        "位置": _mapping_get(state_after, "location"),
        "金币": _mapping_get(state_after, "gold"),
        "体力": _mapping_get(state_after, "energy"),
    }
    episode["current_action_chain"] = chain


def _decision_label(decision: object) -> str:
    if not isinstance(decision, dict):
        return ""
    tool = str(decision.get("tool", ""))
    args = decision.get("args", {})
    if not isinstance(args, dict) or not args:
        return f"{tool}()"
    args_text = ", ".join(f"{key}={value}" for key, value in args.items())
    return f"{tool}({args_text})"


def _episode_finished(episode: dict[str, Any]) -> bool:
    game = episode["game"]
    return bool(game.state.done or episode.get("stopped"))


def _render_episode(
    episode: dict[str, Any],
    status_box: Any,
    world_box: Any,
    action_chain_box: Any,
    trace_box: Any,
    *,
    running: bool,
    render_trace: bool = True,
) -> None:
    game = episode["game"]
    observation = game.observe()
    status = {
        "task_id": episode["task"]["task_id"],
        "done": observation["done"],
        "success": observation["success"],
        "stopped": episode["stopped"],
        "steps": observation["step"],
        "total_actions": episode["total_actions"],
        "invalid_actions": episode["invalid_actions"],
        "replan_count": episode["replan_count"],
        "current_day": observation["day"],
        "running": running,
    }
    with status_box.container():
        _render_status(status)
    with world_box.container():
        _render_world(observation, episode)
    with action_chain_box.container():
        _render_action_chain(episode, running=running)
    if render_trace:
        with trace_box.container():
            _render_trace(episode)
    else:
        trace_box.empty()


def _render_status(status: dict[str, object]) -> None:
    import streamlit as st

    cols = st.columns(8)
    cols[0].metric("任务", str(status["task_id"]))
    cols[1].metric("模型", "LLM")
    cols[2].metric("当前日", f"{status['current_day']} / 14")
    cols[3].metric("步数", int(status["steps"]))
    cols[4].metric("动作", int(status["total_actions"]))
    cols[5].metric("重规划", int(status["replan_count"]))
    cols[6].metric("无效", int(status["invalid_actions"]))
    cols[7].metric("状态", "规划执行中" if status["running"] else "等待")
    if status["running"]:
        st.info(f"Agent 正在规划并执行 Day {status['current_day']}。")
    if status["success"]:
        st.success("任务已完成。")
    elif status["done"]:
        st.error("周期结束，任务未完成。")
    elif status["stopped"]:
        st.warning("Agent 已停止。")


def _render_world(observation: dict[str, object], episode: dict[str, Any]) -> None:
    import streamlit as st

    left, middle = st.columns([2, 3])
    with left:
        st.write("世界状态")
        state_cols = st.columns(2)
        state_cols[0].metric("Day", observation["day"])
        state_cols[0].metric("HP", observation["hp"])
        state_cols[1].metric("Energy", observation["energy"])
        state_cols[0].metric("Gold", observation["gold"])
        state_cols[1].metric("Location", observation["location"])
        st.json(
            {
                "weather_today": observation["weather_today"],
                "weather_tomorrow": observation["weather_tomorrow"],
                "event_today": observation["event_today"],
                "mine_level": observation["mine_level"],
                "pending_enemy": observation["pending_enemy"],
                "inventory": observation["inventory"],
                "equipment": observation["equipment"],
                "completed_quests": observation["completed_quests"],
            }
        )
    with middle:
        st.write("任务")
        st.info(str(observation["goal"]["description"]))


def _render_action_chain(episode: dict[str, Any], *, running: bool) -> None:
    import streamlit as st

    plan = episode.get("current_day_plan") or episode.get("last_day_plan")
    chain = episode.get("current_action_chain", [])
    if not chain and isinstance(episode.get("last_day_result"), dict):
        chain = _chain_rows_from_trace(episode.get("last_day_result", {}))

    st.write("当前动作链")
    if not isinstance(plan, dict):
        st.info("还没有当天动作链。点击“执行一天”后，LLM 会先生成当天动作序列。")
        return

    final_actions = str(plan.get("final_day_actions", "")).strip()
    if final_actions:
        st.info(final_actions)
    meta_cols = st.columns(3)
    meta_cols[0].metric("本日目标", str(plan.get("day_objective", ""))[:32])
    meta_cols[1].metric("计划动作", len(plan.get("actions", [])) if isinstance(plan.get("actions"), list) else 0)
    meta_cols[2].metric("状态", "执行中" if running else "已同步")
    reasoning = str(plan.get("reasoning", "")).strip()
    if reasoning:
        st.caption(reasoning)
    if chain:
        st.dataframe(chain, use_container_width=True, hide_index=True)
    else:
        st.info("LLM 已生成计划，等待执行动作。")


def _chain_rows_from_trace(day_result: dict[str, object]) -> list[dict[str, object]]:
    trace_entries = day_result.get("trace_entries", [])
    if not isinstance(trace_entries, list):
        return []
    rows = []
    for index, entry in enumerate(trace_entries, start=1):
        if not isinstance(entry, dict):
            continue
        result = entry.get("result", {})
        state_after = entry.get("state_after", {})
        success = bool(_mapping_get(result, "success"))
        rows.append(
            {
                "序号": index,
                "状态": "完成" if success else "失败，已触发重规划",
                "动作": _decision_label(entry.get("decision")),
                "理由": _mapping_get(entry.get("decision"), "reason"),
                "结果": _mapping_get(result, "observation"),
                "错误": _mapping_get(result, "error_code") or "",
                "体力变化": _state_change(result, "energy"),
                "位置": _mapping_get(state_after, "location"),
                "金币": _mapping_get(state_after, "gold"),
                "体力": _mapping_get(state_after, "energy"),
            }
        )
    return rows


def _render_trace(episode: dict[str, Any]) -> None:
    import streamlit as st

    trace = episode["trace"]
    if not trace:
        st.info("还没有执行动作。")
        return
    if len(trace) == 1:
        index = 0
    else:
        current = int(st.session_state.get(TRACE_SLIDER_KEY, len(trace)))
        if current < 1 or current > len(trace):
            st.session_state[TRACE_SLIDER_KEY] = len(trace)
        index = st.slider(
            "轨迹步骤",
            1,
            len(trace),
            len(trace),
            key=TRACE_SLIDER_KEY,
        ) - 1
    st.caption(f"当前查看第 {index + 1} 步 / 共 {len(trace)} 步，最新已执行到第 {len(trace)} 步。")
    st.json(trace[index])


def _task_id(task_index: int) -> str:
    return f"TASK_{int(task_index) + 1}"


def _task_label(option: object, task_texts: list[str]) -> str:
    if option == "__all__":
        return "全部任务"
    index = int(option)
    return f"任务 {index + 1}: {task_texts[index]}"


def _selected_task(task_texts: list[str], option: object) -> dict[str, Any]:
    if option == "__all__":
        return make_all_text_tasks(task_texts)
    index = int(option)
    return make_text_task(task_texts[index], _task_id(index))


def _next_seed() -> int:
    import streamlit as st

    seed = int(st.session_state.get(SEED_COUNTER_KEY, 0)) + 1
    st.session_state[SEED_COUNTER_KEY] = seed
    return seed
