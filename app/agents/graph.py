"""LangGraph workflow for planner, executor, checker, and replanner nodes."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.action_policy import Decision, stop
from app.agents.planner import create_plan
from app.agents.replanner import revise_plan, should_replan
from app.agents.state import AgentState
from app.skills import (
    decide_combat_preparation,
    decide_farming_cycle,
    decide_money_making,
    decide_resource_acquisition,
)


@lru_cache(maxsize=1)
def build_agent_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("progress_checker", _progress_checker_node)
    workflow.add_node("planner", _planner_node)
    workflow.add_node("replanner", _replanner_node)
    workflow.add_node("executor", _executor_node)

    workflow.set_entry_point("progress_checker")
    workflow.add_conditional_edges(
        "progress_checker",
        _route_after_progress_check,
        {"replan": "replanner", "plan": "planner"},
    )
    workflow.add_edge("replanner", "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", END)
    return workflow.compile()


def run_agent_graph(state: AgentState) -> AgentState:
    return build_agent_graph().invoke(state)


def _progress_checker_node(state: AgentState) -> dict[str, object]:
    if state.get("enable_replanning") and should_replan(state):
        return {"status": "needs_replan"}
    return {"status": "planning"}


def _route_after_progress_check(state: AgentState) -> str:
    return "replan" if state.get("status") == "needs_replan" else "plan"


def _replanner_node(state: AgentState) -> dict[str, object]:
    return {
        "current_plan": revise_plan(state),
        "replan_count": int(state.get("replan_count", 0)) + 1,
        "status": "replanned",
    }


def _planner_node(state: AgentState) -> dict[str, object]:
    current_plan = list(state.get("current_plan", []))
    if not current_plan:
        current_plan = create_plan(
            str(state.get("goal", "")),
            _mapping(state.get("game_state")),
            list(state.get("memories", [])),
        )
    completed = _completed_subgoals(current_plan, _mapping(state.get("game_state")))
    return {"current_plan": current_plan, "completed_subgoals": completed}


def _executor_node(state: AgentState) -> dict[str, object]:
    plan = list(state.get("current_plan", []))
    completed = list(state.get("completed_subgoals", []))
    subgoal = next((item for item in plan if item not in completed), None)
    if subgoal is None:
        decision = stop("Plan is complete.")
    else:
        decision = _execute_subgoal(subgoal, state)
    decision["plan"] = plan
    decision["current_subgoal"] = subgoal
    decision["completed_subgoals"] = completed
    decision["replan_count"] = int(state.get("replan_count", 0))
    decision["memories"] = list(state.get("memories", []))
    return {"current_subgoal": subgoal or "", "decision": decision, "status": "running"}


def _execute_subgoal(subgoal: str, state: AgentState) -> Decision:
    observation = _mapping(state.get("game_state"))
    goal = str(state.get("goal", ""))
    if subgoal in {"plant_potatoes_for_profit", "sell_for_gold"}:
        return decide_money_making(observation)
    if subgoal in {"plant_potatoes", "tend_potatoes", "harvest_potatoes"}:
        return decide_farming_cycle(observation)
    if subgoal == "obtain_ancient_key":
        return decide_resource_acquisition(observation, "ancient_key")
    if subgoal in {"obtain_iron", "obtain_wood", "craft_iron_sword"}:
        if "guardian" in goal.lower():
            return decide_combat_preparation(observation)
        if subgoal == "craft_iron_sword":
            return decide_resource_acquisition(observation, "iron_sword")
        if subgoal == "obtain_iron":
            return decide_resource_acquisition(observation, "iron", 2)
        return decide_resource_acquisition(observation, "wood", 3)
    if subgoal in {"fallback_resource_route", "mine_iron_and_depth", "defeat_guardian"}:
        return decide_combat_preparation(observation)
    if subgoal == "resolve_enemy":
        return decide_combat_preparation(observation)
    return stop(f"Unknown subgoal: {subgoal}")


def _completed_subgoals(plan: list[str], observation: dict[str, object]) -> list[str]:
    inventory = _mapping(observation.get("inventory"))
    equipment = _mapping(observation.get("equipment"))
    checks = {
        "plant_potatoes_for_profit": int(inventory.get("potato", 0)) > 0
        or _planted_count(observation, "potato") >= 9,
        "plant_potatoes": int(inventory.get("potato", 0)) >= 3
        or _planted_count(observation, "potato") >= 3,
        "tend_potatoes": _all_ready(observation, "potato"),
        "harvest_potatoes": int(inventory.get("potato", 0)) >= 3,
        "sell_for_gold": int(observation.get("gold", 0)) >= 900,
        "obtain_ancient_key": int(inventory.get("ancient_key", 0)) > 0,
        "obtain_iron": int(inventory.get("iron", 0)) >= 2
        or bool(equipment.get("iron_sword")),
        "obtain_wood": int(inventory.get("wood", 0)) >= 3
        or bool(equipment.get("iron_sword")),
        "mine_iron_and_depth": (
            int(inventory.get("iron", 0)) >= 2
            and int(observation.get("mine_level", 1)) >= 3
        )
        or bool(equipment.get("iron_sword")),
        "craft_iron_sword": bool(equipment.get("iron_sword")),
        "defeat_guardian": int(inventory.get("guardian_gem", 0)) > 0,
    }
    return [subgoal for subgoal in plan if checks.get(subgoal, False)]


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _farm(observation: dict[str, object]) -> list[dict[str, object]]:
    farm = observation.get("farm", [])
    return farm if isinstance(farm, list) else []


def _planted_count(observation: dict[str, object], crop: str) -> int:
    return sum(1 for plot in _farm(observation) if plot.get("crop") == crop)


def _all_ready(observation: dict[str, object], crop: str) -> bool:
    plots = [plot for plot in _farm(observation) if plot.get("crop") == crop]
    return bool(plots) and all(bool(plot.get("ready")) for plot in plots)
