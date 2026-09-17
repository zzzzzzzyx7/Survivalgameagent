"""Fishing Route skill."""

from __future__ import annotations

from app.agents.action_policy import Decision, fish, move
from app.skills.recovery import decide_recovery
from app.skills.types import SkillContext, attach_skill, inspect_or_stop, mapping

SKILL_NAME = "Fishing Route"


def decide_fishing_route(
    observation: dict[str, object],
    target_item: str = "big_fish",
    quantity: int = 1,
    context: SkillContext | None = None,
) -> Decision:
    context = context or SkillContext()
    inventory = mapping(observation.get("inventory"))
    location = str(observation.get("location", "farm"))
    item = target_item.strip().lower().replace(" ", "_")

    if int(inventory.get(item, 0)) >= quantity:
        return inspect_or_stop("inventory", f"Already have enough {item}.", context, SKILL_NAME)
    if str(observation.get("weather_today", "sunny")) == "storm":
        return inspect_or_stop("weather", "River is closed during a storm.", context, SKILL_NAME)
    if int(observation.get("energy", 100)) < 8:
        decision = decide_recovery(observation, context)
        decision["skill"] = SKILL_NAME
        return decision
    if location != "river":
        return attach_skill(move("river", f"Move to River to catch {item}."), SKILL_NAME)
    return attach_skill(fish(f"Fish for {item} at the River."), SKILL_NAME)
