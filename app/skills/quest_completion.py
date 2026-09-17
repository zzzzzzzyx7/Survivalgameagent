"""Quest Completion skill."""

from __future__ import annotations

from app.agents.action_policy import (
    Decision,
    accept_quest,
    fight,
    mine,
    move,
    stop,
    submit_quest,
)
from app.skills.farming_cycle import decide_farming_cycle
from app.skills.fishing_route import decide_fishing_route
from app.skills.recovery import decide_recovery
from app.skills.resource_acquisition import decide_resource_acquisition
from app.skills.types import SkillContext, attach_skill, inspect_or_stop, mapping

SKILL_NAME = "Quest Completion"

QUEST_ALIASES = {
    "wood": "Q_WOOD_8",
    "q_wood_8": "Q_WOOD_8",
    "potato": "Q_POTATO_3",
    "q_potato_3": "Q_POTATO_3",
    "goblin": "Q_GOBLIN_2",
    "q_goblin_2": "Q_GOBLIN_2",
    "big_fish": "Q_BIG_FISH_2",
    "big fish": "Q_BIG_FISH_2",
    "q_big_fish_2": "Q_BIG_FISH_2",
}


def decide_quest_completion(
    observation: dict[str, object],
    quest_id: str | None = None,
    context: SkillContext | None = None,
) -> Decision:
    context = context or SkillContext()
    location = str(observation.get("location", "farm"))
    completed = observation.get("completed_quests", [])
    completed_quests = completed if isinstance(completed, list) else []
    available_quests = mapping(observation.get("available_quests"))
    active_quests = mapping(observation.get("active_quests"))
    target_quest = _select_quest(quest_id, available_quests, active_quests)

    if target_quest is None:
        return inspect_or_stop("quests", "No matching quest is available.", context, SKILL_NAME)
    if target_quest in completed_quests:
        return attach_skill(stop(f"Quest {target_quest} is already completed."), SKILL_NAME)
    if target_quest not in active_quests:
        if location != "guild":
            return attach_skill(move("guild", f"Move to Guild to accept {target_quest}."), SKILL_NAME)
        return attach_skill(accept_quest(target_quest, f"Accept quest {target_quest}."), SKILL_NAME)

    quest = mapping(active_quests[target_quest])
    missing = _missing_requirements(observation, quest)
    if missing:
        return _satisfy_missing_requirement(observation, missing, context)
    if location != "guild":
        return attach_skill(move("guild", f"Move to Guild to submit {target_quest}."), SKILL_NAME)
    return attach_skill(submit_quest(target_quest, f"Submit quest {target_quest}."), SKILL_NAME)


def infer_quest_id(goal: str) -> str | None:
    normalized = goal.lower().replace("-", "_")
    for key, quest_id in QUEST_ALIASES.items():
        if key in normalized:
            return quest_id
    if "ancient key" in normalized and "quest" in normalized:
        return "Q_BIG_FISH_2"
    return None


def _select_quest(
    quest_id: str | None,
    available_quests: dict[str, object],
    active_quests: dict[str, object],
) -> str | None:
    if quest_id:
        normalized = quest_id.strip().upper()
        if normalized in available_quests or normalized in active_quests:
            return normalized
        return QUEST_ALIASES.get(quest_id.strip().lower().replace(" ", "_"), normalized)
    if active_quests:
        return str(next(iter(active_quests)))
    if available_quests:
        return str(next(iter(available_quests)))
    return None


def _missing_requirements(
    observation: dict[str, object],
    quest: dict[str, object],
) -> dict[str, dict[str, int]]:
    inventory = mapping(observation.get("inventory"))
    defeated = mapping(observation.get("defeated"))
    world_state = mapping(observation.get("world_state"))
    defeated_counter = mapping(world_state.get("defeated")) or defeated
    requirements = mapping(quest.get("requirements"))
    missing: dict[str, dict[str, int]] = {}

    item_requirements = mapping(requirements.get("items"))
    missing_items = {
        str(item): int(quantity) - int(inventory.get(str(item), 0))
        for item, quantity in item_requirements.items()
        if int(inventory.get(str(item), 0)) < int(quantity)
    }
    if missing_items:
        missing["items"] = missing_items

    defeated_requirements = mapping(requirements.get("defeated"))
    missing_defeated = {
        str(enemy): int(quantity) - int(defeated_counter.get(str(enemy), 0))
        for enemy, quantity in defeated_requirements.items()
        if int(defeated_counter.get(str(enemy), 0)) < int(quantity)
    }
    if missing_defeated:
        missing["defeated"] = missing_defeated
    return missing


def _satisfy_missing_requirement(
    observation: dict[str, object],
    missing: dict[str, dict[str, int]],
    context: SkillContext,
) -> Decision:
    item_missing = missing.get("items", {})
    if item_missing:
        item, quantity = next(iter(item_missing.items()))
        if item == "potato":
            decision = decide_farming_cycle(observation, "potato", quantity, context)
        elif item == "big_fish":
            decision = decide_fishing_route(observation, "big_fish", quantity, context)
        else:
            decision = decide_resource_acquisition(observation, item, quantity, context)
        decision["skill"] = SKILL_NAME
        return decision

    defeated_missing = missing.get("defeated", {})
    if defeated_missing:
        enemy = next(iter(defeated_missing))
        return _satisfy_defeated_requirement(observation, enemy, context)
    return attach_skill(stop("Quest requirements are already satisfied."), SKILL_NAME)


def _satisfy_defeated_requirement(
    observation: dict[str, object],
    enemy: str,
    context: SkillContext,
) -> Decision:
    if enemy != "goblin":
        return inspect_or_stop(
            "quests",
            f"No combat route for defeated requirement: {enemy}.",
            context,
            SKILL_NAME,
        )

    location = str(observation.get("location", "farm"))
    weather = str(observation.get("weather_today", "sunny"))
    event_today = observation.get("event_today")
    pending_enemy = observation.get("pending_enemy")
    mine_level = int(observation.get("mine_level", 1))

    if int(observation.get("energy", 100)) < 15 or int(observation.get("hp", 100)) <= 45:
        decision = decide_recovery(observation, context)
        decision["skill"] = SKILL_NAME
        return decision
    if weather == "storm" or event_today == "mine_collapse":
        return inspect_or_stop("weather", "Mine is closed for the goblin quest.", context, SKILL_NAME)
    if location != "mine":
        return attach_skill(move("mine", "Move to Mine to find Goblin."), SKILL_NAME)
    if pending_enemy == "goblin":
        return attach_skill(fight("fight", "Defeat Goblin for quest progress."), SKILL_NAME)
    if pending_enemy is not None:
        return attach_skill(fight("escape", "Escape non-quest enemy encounter."), SKILL_NAME)
    if mine_level < 2:
        return attach_skill(mine("Mine until Goblins can appear on Level 2."), SKILL_NAME)
    return attach_skill(mine("Search Mine Level 2+ for Goblin encounter."), SKILL_NAME)
