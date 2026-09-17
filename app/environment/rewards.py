"""Task success checks for benchmark goals."""

from __future__ import annotations

from app.environment.state import GameState


def has_item(state: GameState, item: str, quantity: int = 1) -> bool:
    if state.inventory.get(item, 0) >= quantity:
        return True
    return quantity == 1 and state.equipment.get(item, False)


def success_condition_met(state: GameState, condition: str) -> bool:
    within_episode = state.day <= state.goal.get("deadline_day", 14)
    if condition.startswith("all:"):
        conditions = [item for item in condition.removeprefix("all:").split(";") if item]
        return bool(conditions) and all(success_condition_met(state, item) for item in conditions)
    if condition == "g01_900_gold_by_day_7":
        return within_episode and state.gold >= 900
    if condition == "g02_iron_sword_by_day_8":
        return within_episode and state.equipment.get("iron_sword", False)
    if condition == "g03_harvest_3_potato_by_day_10":
        harvested = state.world_state.get("harvested", {})
        return within_episode and harvested.get("potato", 0) >= 3
    if condition == "g04_ancient_key_by_day_12":
        return within_episode and has_item(state, "ancient_key")
    if condition == "g05_defeat_guardian":
        return (
            within_episode
            and has_item(state, "ancient_key")
            and state.equipment.get("iron_sword", False)
            and has_item(state, "guardian_gem")
        )
    return False
