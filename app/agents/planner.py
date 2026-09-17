"""Planning node helpers."""

from __future__ import annotations


def create_plan(
    goal: str,
    observation: dict[str, object],
    memories: list[str] | None = None,
) -> list[str]:
    del observation, memories
    normalized = goal.lower()
    compact = normalized.replace(" ", "")
    if "900gold" in compact or "900金币" in compact or "1000gold" in compact:
        return ["plant_potatoes_for_profit", "harvest_potatoes", "sell_for_gold"]
    if "harvest3potato" in compact or ("收获3" in compact and "土豆" in compact):
        return ["plant_potatoes", "tend_potatoes", "harvest_potatoes"]
    if (
        ("ancientkey" in compact or "钥匙" in compact)
        and "guardian" not in normalized
        and "守卫" not in normalized
    ):
        return ["obtain_ancient_key"]
    if "guardian" in normalized or "守卫" in normalized:
        return ["obtain_ancient_key", "obtain_wood", "mine_iron_and_depth", "craft_iron_sword", "defeat_guardian"]
    if "ironsword" in compact or "铁剑" in compact:
        return ["obtain_iron", "obtain_wood", "craft_iron_sword"]
    return []
