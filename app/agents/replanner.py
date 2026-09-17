"""Replanning node helpers."""

from __future__ import annotations

from typing import Any

REPLAN_ERROR_CODES = {
    "LOCATION_CLOSED",
    "INSUFFICIENT_RESOURCES",
    "NOT_ENOUGH_ENERGY",
    "ENEMY_BLOCKING",
}


def should_replan(agent_state: dict[str, object]) -> bool:
    last_result = _mapping(agent_state.get("last_result"))
    game_state = _mapping(agent_state.get("game_state"))
    current_subgoal = str(agent_state.get("current_subgoal", ""))

    if last_result and not bool(last_result.get("success", True)):
        return str(last_result.get("error_code")) in REPLAN_ERROR_CODES
    if game_state.get("weather_today") == "storm" and _depends_on_closed_locations(current_subgoal):
        return True
    if game_state.get("event_today") == "mine_collapse" and _depends_on_mine(current_subgoal):
        return True
    return game_state.get("pending_enemy") is not None and _depends_on_mine(current_subgoal)


def revise_plan(agent_state: dict[str, object]) -> list[str]:
    plan = list(agent_state.get("current_plan", []))
    game_state = _mapping(agent_state.get("game_state"))
    current_subgoal = str(agent_state.get("current_subgoal", ""))

    if game_state.get("weather_today") == "storm" or game_state.get("event_today") == "mine_collapse":
        return _insert_before(plan, current_subgoal, "fallback_resource_route")
    if game_state.get("pending_enemy") is not None:
        return _insert_before(plan, current_subgoal, "resolve_enemy")
    return plan


def _insert_before(plan: list[str], current_subgoal: str, new_subgoal: str) -> list[str]:
    if new_subgoal in plan:
        return plan
    if current_subgoal in plan:
        index = plan.index(current_subgoal)
        return plan[:index] + [new_subgoal] + plan[index:]
    return [new_subgoal, *plan]


def _depends_on_closed_locations(subgoal: str) -> bool:
    return _depends_on_mine(subgoal) or "fish" in subgoal or "river" in subgoal


def _depends_on_mine(subgoal: str) -> bool:
    return "mine" in subgoal or "guardian" in subgoal or "combat" in subgoal


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
