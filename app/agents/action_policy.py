"""Shared deterministic decision builders and scripted route helpers."""

from __future__ import annotations

from typing import Any

Decision = dict[str, Any]


def stop(reason: str) -> Decision:
    return {"tool": "stop", "args": {}, "reason": reason}


def move(location: str, reason: str) -> Decision:
    return {"tool": "move", "args": {"location": location}, "reason": reason}


def trade(action: str, item: str, quantity: int, reason: str) -> Decision:
    return {
        "tool": "trade",
        "args": {"action": action, "item": item, "quantity": max(1, quantity)},
        "reason": reason,
    }


def accept_quest(quest_id: str, reason: str) -> Decision:
    return {"tool": "accept_quest", "args": {"quest_id": quest_id}, "reason": reason}


def submit_quest(quest_id: str, reason: str) -> Decision:
    return {"tool": "submit_quest", "args": {"quest_id": quest_id}, "reason": reason}


def forage(resource: str, reason: str) -> Decision:
    return {"tool": "forage", "args": {"resource": resource}, "reason": reason}


def craft(item: str, reason: str) -> Decision:
    return {"tool": "craft", "args": {"item": item}, "reason": reason}


def plant(crop: str, plot: int, reason: str) -> Decision:
    return {"tool": "plant", "args": {"crop": crop, "plot": plot}, "reason": reason}


def water(reason: str) -> Decision:
    return {"tool": "water", "args": {"plot": "all"}, "reason": reason}


def harvest(reason: str) -> Decision:
    return {"tool": "harvest", "args": {"plot": "all"}, "reason": reason}


def rest(reason: str) -> Decision:
    return {"tool": "rest", "args": {}, "reason": reason}


def mine(reason: str) -> Decision:
    return {"tool": "mine", "args": {}, "reason": reason}


def fish(reason: str) -> Decision:
    return {"tool": "fish", "args": {}, "reason": reason}


def fight(action: str, reason: str) -> Decision:
    return {"tool": "fight", "args": {"action": action}, "reason": reason}


def inspect(target: str, reason: str) -> Decision:
    return {"tool": "inspect", "args": {"target": target}, "reason": reason}


def decide_potato_goal(observation: dict[str, object], target_potato: int = 3) -> Decision:
    inventory = _mapping(observation.get("inventory"))
    location = str(observation.get("location", "farm"))
    farm = _farm(observation)
    planted_potatoes = _planted_count(farm, "potato")
    potato_seeds = int(inventory.get("potato_seed", 0))

    if int(inventory.get("potato", 0)) >= target_potato:
        return stop("Potato harvest target is already satisfied.")
    if planted_potatoes + potato_seeds + int(inventory.get("potato", 0)) < target_potato:
        if location != "town":
            return move("town", "Buy Potato Seeds for the harvest goal.")
        needed = target_potato - planted_potatoes - potato_seeds - int(inventory.get("potato", 0))
        return trade("buy", "potato_seed", needed, "Buy enough Potato Seeds.")
    if planted_potatoes < target_potato:
        if location != "farm":
            return move("farm", "Plant Potato crops at the farm.")
        return plant("potato", _first_empty_plot(farm), "Plant Potato crops.")
    if not _all_crops_ready(farm, "potato"):
        if location != "farm":
            return move("farm", "Tend Potato crops.")
        if _has_dry_crop(farm):
            return water("Water Potato crops.")
        return rest("Advance to the next crop growth day.")
    if location != "farm":
        return move("farm", "Harvest Potato crops.")
    return harvest("Harvest mature Potato crops.")


def decide_gold_goal(
    observation: dict[str, object],
    target_gold: int = 1000,
    crop_count: int = 9,
) -> Decision:
    inventory = _mapping(observation.get("inventory"))
    location = str(observation.get("location", "farm"))
    gold = int(observation.get("gold", 0))
    farm = _farm(observation)
    planted = _planted_count(farm, "potato")
    seeds = int(inventory.get("potato_seed", 0))

    if gold >= target_gold:
        return stop("Gold target is already satisfied.")
    if int(inventory.get("potato", 0)) > 0:
        if location != "town":
            return move("town", "Sell harvested Potato.")
        return trade("sell", "potato", int(inventory["potato"]), "Sell harvested Potato.")
    if gold >= target_gold - 40:
        if int(inventory.get("wild_flower", 0)) > 0:
            if location != "town":
                return move("town", "Sell Wild Flowers to finish the target.")
            return trade("sell", "wild_flower", int(inventory["wild_flower"]), "Sell Wild Flowers.")
        if location != "forest":
            return move("forest", "Forage a Wild Flower to finish the gold target.")
        return forage("wild_flower", "Forage a Wild Flower to finish the gold target.")
    if int(inventory.get("wild_flower", 0)) > 0:
        if location != "town":
            return move("town", "Sell Wild Flowers to finish the target.")
        return trade("sell", "wild_flower", int(inventory["wild_flower"]), "Sell Wild Flowers.")
    if planted + seeds < crop_count:
        if location != "town":
            return move("town", "Buy Potato Seeds for the gold route.")
        return trade("buy", "potato_seed", crop_count - planted - seeds, "Buy Potato Seeds.")
    if planted < crop_count:
        if location != "farm":
            return move("farm", "Plant Potato crops for profit.")
        return plant("potato", _first_empty_plot(farm), "Plant Potato crops for profit.")
    if not _all_crops_ready(farm, "potato"):
        if location != "farm":
            return move("farm", "Tend profitable Potato crops.")
        if _has_dry_crop(farm):
            return water("Water profitable Potato crops.")
        return rest("Advance crop growth.")
    if location != "farm":
        return move("farm", "Harvest profitable Potato crops.")
    return harvest("Harvest Potato crops for sale.")


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _farm(observation: dict[str, object]) -> list[dict[str, Any]]:
    farm = observation.get("farm", [])
    return farm if isinstance(farm, list) else []


def _planted_count(farm: list[dict[str, Any]], crop: str) -> int:
    return sum(1 for plot in farm if plot.get("crop") == crop)


def _first_empty_plot(farm: list[dict[str, Any]]) -> int:
    for plot in farm:
        if plot.get("crop") is None:
            return int(plot["plot_id"])
    return 1


def _has_dry_crop(farm: list[dict[str, Any]]) -> bool:
    return any(plot.get("crop") is not None and not plot.get("watered") for plot in farm)


def _all_crops_ready(farm: list[dict[str, Any]], crop: str) -> bool:
    crops = [plot for plot in farm if plot.get("crop") == crop]
    return bool(crops) and all(bool(plot.get("ready")) for plot in crops)
