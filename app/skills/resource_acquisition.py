"""Resource Acquisition skill."""

from __future__ import annotations

from app.agents.action_policy import Decision, craft, forage, mine, move, stop, trade
from app.skills.fishing_route import decide_fishing_route
from app.skills.types import SkillContext, attach_skill, inspect_or_stop

SKILL_NAME = "Resource Acquisition"


def decide_resource_acquisition(
    observation: dict[str, object],
    resource: str,
    quantity: int = 1,
    context: SkillContext | None = None,
) -> Decision:
    context = context or SkillContext()
    inventory = observation.get("inventory", {})
    inventory = inventory if isinstance(inventory, dict) else {}
    location = str(observation.get("location", "farm"))
    resource_name = resource.strip().lower().replace(" ", "_")

    if resource_name == "iron_sword":
        equipment = observation.get("equipment", {})
        equipment = equipment if isinstance(equipment, dict) else {}
        if equipment.get("iron_sword"):
            return attach_skill(stop("Iron Sword is already equipped."), SKILL_NAME)
        if int(inventory.get("iron", 0)) < 2:
            return decide_resource_acquisition(observation, "iron", 2, context)
        if int(inventory.get("wood", 0)) < 3:
            return decide_resource_acquisition(observation, "wood", 3, context)
        if location != "farm":
            return attach_skill(move("farm", "Move to Farm to craft Iron Sword."), SKILL_NAME)
        return attach_skill(craft("iron_sword", "Craft Iron Sword."), SKILL_NAME)

    if int(inventory.get(resource_name, 0)) >= quantity:
        return inspect_or_stop("inventory", f"Already have enough {resource_name}.", context, SKILL_NAME)

    if resource_name in {"wood", "berry", "herb", "wild_flower"}:
        if location != "forest":
            return attach_skill(move("forest", f"Move to Forest to acquire {resource_name}."), SKILL_NAME)
        return attach_skill(forage(resource_name, f"Forage {resource_name} in Forest."), SKILL_NAME)

    if resource_name in {"small_fish", "big_fish"}:
        decision = decide_fishing_route(observation, resource_name, quantity, context)
        decision["skill"] = SKILL_NAME
        return decision

    if resource_name == "iron" and int(observation.get("gold", 500)) >= 100:
        if location != "town":
            return attach_skill(move("town", "Move to Town to buy Iron."), SKILL_NAME)
        return attach_skill(trade("buy", "iron", quantity, "Buy Iron."), SKILL_NAME)

    if resource_name in {"stone", "copper", "iron", "crystal"}:
        if location != "mine":
            return attach_skill(move("mine", f"Move to Mine to acquire {resource_name}."), SKILL_NAME)
        return attach_skill(mine(f"Mine for {resource_name}."), SKILL_NAME)

    if resource_name == "ancient_key":
        if location != "town":
            return attach_skill(move("town", "Move to Town to buy Ancient Key."), SKILL_NAME)
        return attach_skill(trade("buy", "ancient_key", 1, "Buy Ancient Key."), SKILL_NAME)

    return inspect_or_stop("state", f"No resource acquisition route for {resource_name}.", context, SKILL_NAME)
