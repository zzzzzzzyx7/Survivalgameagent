"""Planner-executor agent."""

from app.agents.action_policy import Decision, stop
from app.agents.planner import create_plan
from app.agents.replanner import revise_plan, should_replan
from app.skills import (
    decide_combat_preparation,
    decide_farming_cycle,
    decide_money_making,
    decide_resource_acquisition,
)


class PlannerAgent:
    agent_type = "planner"

    def __init__(
        self,
        *,
        enable_replanning: bool = False,
        memories: list[str] | None = None,
    ) -> None:
        self.enable_replanning = enable_replanning
        self.memories = memories or []
        self.current_plan: list[str] = []
        self.completed_subgoals: list[str] = []
        self.replan_count = 0
        self.current_subgoal: str | None = None
        self.last_result: dict[str, object] | None = None

    def run_step(self, observation: dict[str, object], goal: str) -> Decision:
        if not self.current_plan:
            self.current_plan = create_plan(goal, observation, self.memories)
        if not self.current_plan:
            return stop(f"No planner policy is available for goal: {goal}")

        self._mark_completed(observation)
        subgoal = self._current_subgoal()
        if subgoal is None:
            return stop("Plan is complete.")

        self.current_subgoal = subgoal
        decision = self._execute_subgoal(subgoal, observation, goal)
        decision["plan"] = list(self.current_plan)
        decision["current_subgoal"] = subgoal
        decision["completed_subgoals"] = list(self.completed_subgoals)
        decision["replan_count"] = self.replan_count
        decision["memories"] = list(self.memories)
        return decision

    def observe_result(
        self,
        result: dict[str, object],
        observation: dict[str, object],
    ) -> None:
        agent_state = {
            "game_state": observation,
            "current_plan": self.current_plan,
            "current_subgoal": self.current_subgoal,
            "last_result": result,
        }
        if self.enable_replanning and should_replan(agent_state):
            self.current_plan = revise_plan(agent_state)
            self.replan_count += 1

    def _current_subgoal(self) -> str | None:
        for subgoal in self.current_plan:
            if subgoal not in self.completed_subgoals:
                return subgoal
        return None

    def _mark_completed(self, observation: dict[str, object]) -> None:
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
        for subgoal, completed in checks.items():
            if completed and subgoal in self.current_plan and subgoal not in self.completed_subgoals:
                self.completed_subgoals.append(subgoal)

    def _execute_subgoal(
        self,
        subgoal: str,
        observation: dict[str, object],
        goal: str,
    ) -> Decision:
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


class PlannerReplanningAgent(PlannerAgent):
    agent_type = "planner_replanning"

    def __init__(self, *, memories: list[str] | None = None) -> None:
        super().__init__(enable_replanning=True, memories=memories)

    def run_step(self, observation: dict[str, object], goal: str) -> Decision:
        from app.agents.graph import run_agent_graph

        graph_state = run_agent_graph(
            {
                "goal": goal,
                "game_state": observation,
                "current_plan": list(self.current_plan),
                "completed_subgoals": list(self.completed_subgoals),
                "current_subgoal": self.current_subgoal or "",
                "last_result": self.last_result or {},
                "memories": list(self.memories),
                "replan_count": self.replan_count,
                "enable_replanning": True,
                "status": "running",
            }
        )
        self.current_plan = list(graph_state.get("current_plan", []))
        self.completed_subgoals = list(graph_state.get("completed_subgoals", []))
        self.replan_count = int(graph_state.get("replan_count", 0))
        self.current_subgoal = str(graph_state.get("current_subgoal", "")) or None
        decision = graph_state.get("decision", stop("Graph did not produce a decision."))
        return decision if isinstance(decision, dict) else stop("Invalid graph decision.")

    def observe_result(
        self,
        result: dict[str, object],
        observation: dict[str, object],
    ) -> None:
        del observation
        self.last_result = result


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _farm(observation: dict[str, object]) -> list[dict[str, object]]:
    farm = observation.get("farm", [])
    return farm if isinstance(farm, list) else []


def _planted_count(observation: dict[str, object], crop: str) -> int:
    return sum(1 for plot in _farm(observation) if plot.get("crop") == crop)


def _all_ready(observation: dict[str, object], crop: str) -> bool:
    plots = [plot for plot in _farm(observation) if plot.get("crop") == crop]
    return bool(plots) and all(bool(plot.get("ready")) for plot in plots)
