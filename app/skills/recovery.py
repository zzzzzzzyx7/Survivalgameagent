"""Recovery skill."""

from __future__ import annotations

from app.agents.action_policy import Decision, rest
from app.skills.types import SkillContext, attach_skill, mapping

SKILL_NAME = "Recovery"


def decide_recovery(
    observation: dict[str, object],
    context: SkillContext | None = None,
) -> Decision:
    del context
    inventory = mapping(observation.get("inventory"))
    hp = int(observation.get("hp", 100))
    energy = int(observation.get("energy", 100))

    if hp <= 60 and int(inventory.get("potion", 0)) > 0:
        return attach_skill(
            {"tool": "use_item", "args": {"item": "potion"}, "reason": "Recover HP with Potion."},
            SKILL_NAME,
        )
    if energy <= 30:
        return attach_skill(rest("Recover Energy by resting."), SKILL_NAME)
    return attach_skill(rest("Rest to prepare for the next action."), SKILL_NAME)
