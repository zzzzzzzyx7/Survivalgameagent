"""Failure categorization helpers."""

from __future__ import annotations

from typing import Any

FAILURE_CATEGORIES = {
    "planning_error",
    "invalid_action",
    "state_understanding_error",
    "resource_mismanagement",
    "looping",
    "premature_goal_attempt",
    "failure_to_replan",
    "combat_failure",
    "deadline_missed",
    "other",
}


def categorize_failure(episode: dict[str, object]) -> str:
    if episode.get("success"):
        return "success"

    trace = episode.get("trace", [])
    if not isinstance(trace, list) or not trace:
        return "planning_error"

    invalid_actions = int(episode.get("invalid_actions", 0))
    if invalid_actions:
        return _categorize_invalid_trace(trace)

    final_state = _mapping(episode.get("final_state"))
    if _looping(trace):
        return "looping"
    if final_state.get("done") and _deadline_reached(final_state):
        return "deadline_missed"
    if final_state.get("pending_enemy") is not None:
        return "combat_failure"
    if int(final_state.get("energy", 100)) <= 0 or int(final_state.get("gold", 0)) < 0:
        return "resource_mismanagement"
    return "other"


def _categorize_invalid_trace(trace: list[object]) -> str:
    error_codes = []
    for item in trace:
        step = _mapping(item)
        result = _mapping(step.get("result"))
        if result.get("success") is False:
            error_codes.append(str(result.get("error_code")))
    if "LOCATION_CLOSED" in error_codes:
        return "failure_to_replan"
    if "NO_ANCIENT_KEY" in error_codes:
        return "premature_goal_attempt"
    if "NOT_ENOUGH_ENERGY" in error_codes or "INSUFFICIENT_RESOURCES" in error_codes:
        return "resource_mismanagement"
    return "invalid_action"


def _looping(trace: list[object]) -> bool:
    actions = [
        _mapping(step).get("action")
        for step in trace[-6:]
        if isinstance(step, dict)
    ]
    return len(actions) >= 6 and len(set(actions)) == 1


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _deadline_reached(final_state: dict[str, Any]) -> bool:
    goal = _mapping(final_state.get("goal"))
    deadline = int(goal.get("deadline_day", 0) or 0)
    return bool(deadline) and int(final_state.get("day", 0) or 0) >= deadline
