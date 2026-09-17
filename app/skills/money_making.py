"""Money Making skill."""

from __future__ import annotations

from app.agents.action_policy import Decision, forage, move, stop, trade
from app.skills.farming_cycle import decide_farming_cycle
from app.skills.types import SkillContext, attach_skill

SKILL_NAME = "Money Making"


def decide_money_making(
    observation: dict[str, object],
    target_gold: int = 900,
    context: SkillContext | None = None,
) -> Decision:
    context = context or SkillContext()
    inventory = observation.get("inventory", {})
    inventory = inventory if isinstance(inventory, dict) else {}
    location = str(observation.get("location", "farm"))
    gold = int(observation.get("gold", 0))

    if gold >= target_gold:
        return attach_skill(stop("Gold target is already satisfied."), SKILL_NAME)
    if int(inventory.get("potato", 0)) > 0:
        if location != "town":
            return attach_skill(move("town", "Move to Town to sell Potato."), SKILL_NAME)
        return attach_skill(trade("sell", "potato", int(inventory["potato"]), "Sell Potato."), SKILL_NAME)
    if int(inventory.get("wild_flower", 0)) > 0:
        if location != "town":
            return attach_skill(move("town", "Move to Town to sell Wild Flower."), SKILL_NAME)
        return attach_skill(
            trade("sell", "wild_flower", int(inventory["wild_flower"]), "Sell Wild Flower."),
            SKILL_NAME,
        )
    if gold >= target_gold - 40:
        if location != "forest":
            return attach_skill(move("forest", "Move to Forest for quick sellable forage."), SKILL_NAME)
        return attach_skill(forage("wild_flower", "Forage Wild Flower to finish gold goal."), SKILL_NAME)

    decision = decide_farming_cycle(observation, "potato", target_quantity=9, context=context)
    decision["skill"] = SKILL_NAME
    return decision
