"""Skill router for high-level goal handling."""

from __future__ import annotations

from app.agents.action_policy import Decision, craft, move, stop
from app.skills.combat_preparation import decide_combat_preparation
from app.skills.farming_cycle import decide_farming_cycle
from app.skills.fishing_route import decide_fishing_route
from app.skills.money_making import decide_money_making
from app.skills.quest_completion import decide_quest_completion, infer_quest_id
from app.skills.resource_acquisition import decide_resource_acquisition
from app.skills.types import SkillContext, attach_skill, mapping

FIRST_STAGE_SKILLS = (
    "Resource Acquisition",
    "Farming Cycle",
    "Fishing Route",
    "Money Making",
    "Combat Preparation",
    "Recovery",
    "Quest Completion",
)


def decide_goal_with_skills(
    observation: dict[str, object],
    goal: str,
    context: SkillContext | None = None,
) -> Decision:
    context = context or SkillContext()
    normalized_goal = goal.lower()
    compact_goal = normalized_goal.replace(" ", "")
    quest_id = infer_quest_id(goal)

    if "quest" in normalized_goal or quest_id is not None:
        return decide_quest_completion(observation, quest_id, context)
    if "900gold" in compact_goal or "900金币" in compact_goal or "1000gold" in compact_goal:
        target_gold = 1000 if "1000gold" in compact_goal else 900
        return decide_money_making(observation, target_gold=target_gold, context=context)
    if "harvest3potato" in compact_goal or (
        "收获3" in compact_goal and "土豆" in compact_goal
    ):
        return decide_farming_cycle(observation, "potato", target_quantity=3, context=context)
    if "fish" in normalized_goal or "big_fish" in normalized_goal or "big fish" in normalized_goal:
        return decide_fishing_route(observation, "big_fish", quantity=2, context=context)
    if (
        ("ancientkey" in compact_goal or "钥匙" in compact_goal)
        and "guardian" not in normalized_goal
        and "守卫" not in normalized_goal
    ):
        return decide_resource_acquisition(observation, "ancient_key", context=context)
    if "guardian" in normalized_goal or "守卫" in normalized_goal:
        return decide_combat_preparation(observation, context=context)
    if "ironsword" in compact_goal or "铁剑" in compact_goal:
        return _decide_iron_sword(observation, context)
    return attach_skill(stop(f"No skill route is available for goal: {goal}"), "Skill Router")


def _decide_iron_sword(observation: dict[str, object], context: SkillContext) -> Decision:
    inventory = mapping(observation.get("inventory"))
    equipment = mapping(observation.get("equipment"))
    location = str(observation.get("location", "farm"))

    if equipment.get("iron_sword"):
        return attach_skill(stop("Iron Sword is already equipped."), "Resource Acquisition")
    if int(inventory.get("iron", 0)) < 2:
        return decide_resource_acquisition(observation, "iron", 2, context)
    if int(inventory.get("wood", 0)) < 3:
        return decide_resource_acquisition(observation, "wood", 3, context)
    if location != "farm":
        return attach_skill(move("farm", "Move to Farm to craft Iron Sword."), "Resource Acquisition")
    return attach_skill(craft("iron_sword", "Craft Iron Sword from acquired resources."), "Resource Acquisition")
