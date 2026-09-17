"""Combat Preparation skill."""

from __future__ import annotations

from app.agents.action_policy import Decision, craft, fight, forage, mine, move, rest, trade
from app.skills.recovery import decide_recovery
from app.skills.resource_acquisition import decide_resource_acquisition
from app.skills.types import SkillContext, attach_skill, mapping

SKILL_NAME = "Combat Preparation"


def decide_combat_preparation(
    observation: dict[str, object],
    context: SkillContext | None = None,
) -> Decision:
    context = context or SkillContext()
    inventory = mapping(observation.get("inventory"))
    equipment = mapping(observation.get("equipment"))
    world = mapping(observation.get("world_state"))
    location = str(observation.get("location", "farm"))
    mine_level = int(observation.get("mine_level", world.get("mine_level", 1)))
    pending_enemy = observation.get("pending_enemy", world.get("pending_enemy"))
    weather = str(observation.get("weather_today", "sunny"))
    event_today = observation.get("event_today")

    if int(inventory.get("guardian_gem", 0)) > 0:
        return attach_skill(
            {"tool": "stop", "args": {}, "reason": "Guardian has already been defeated."},
            SKILL_NAME,
        )
    if int(observation.get("energy", 100)) < 15 or int(observation.get("hp", 100)) <= 60:
        decision = decide_recovery(observation, context)
        decision["skill"] = SKILL_NAME
        return decision
    if int(inventory.get("ancient_key", 0)) == 0:
        decision = decide_resource_acquisition(observation, "ancient_key", context=context)
        decision["skill"] = SKILL_NAME
        return decision
    if not equipment.get("iron_sword"):
        if int(inventory.get("wood", 0)) < 3:
            decision = decide_resource_acquisition(observation, "wood", 3, context)
            decision["skill"] = SKILL_NAME
            return decision
        if int(inventory.get("iron", 0)) < 2 or mine_level < 3:
            if weather == "storm" or event_today == "mine_collapse":
                return _fallback_money_action(observation, "Mine is closed, gather sellable resources.")
            if location != "mine":
                return attach_skill(move("mine", "Mine until enough Iron and mine depth are reached."), SKILL_NAME)
            if int(observation.get("energy", 100)) < 15:
                return attach_skill(rest("Recover Energy before more mining."), SKILL_NAME)
            if pending_enemy is not None:
                return attach_skill(fight("escape", "Avoid side combat while preparing."), SKILL_NAME)
            return attach_skill(mine("Mine for Iron and deeper access."), SKILL_NAME)
        if location != "farm":
            return attach_skill(move("farm", "Move to Farm to craft Iron Sword."), SKILL_NAME)
        return attach_skill(craft("iron_sword", "Craft Iron Sword before combat."), SKILL_NAME)
    if weather == "storm" or event_today == "mine_collapse":
        return _fallback_money_action(observation, "Mine is closed before the Guardian fight.")
    if location != "mine":
        return attach_skill(move("mine", "Move to Mine for Guardian route."), SKILL_NAME)
    if pending_enemy == "guardian":
        return attach_skill(fight("fight", "Fight Guardian after preparation."), SKILL_NAME)
    if int(observation.get("energy", 100)) < 15:
        return attach_skill(rest("Recover Energy before searching for Guardian."), SKILL_NAME)
    if pending_enemy is not None:
        return attach_skill(fight("escape", "Escape side encounter while preparing."), SKILL_NAME)
    return attach_skill(mine("Search for Guardian in Mine."), SKILL_NAME)


def _fallback_money_action(observation: dict[str, object], reason: str) -> Decision:
    inventory = mapping(observation.get("inventory"))
    location = str(observation.get("location", "farm"))
    if int(inventory.get("wild_flower", 0)) > 0:
        if location != "town":
            return attach_skill(move("town", reason), SKILL_NAME)
        return attach_skill(trade("sell", "wild_flower", int(inventory["wild_flower"]), reason), SKILL_NAME)
    if location != "forest":
        return attach_skill(move("forest", reason), SKILL_NAME)
    return attach_skill(forage("wild_flower", reason), SKILL_NAME)
