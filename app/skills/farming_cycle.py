"""Farming Cycle skill."""

from __future__ import annotations

from app.agents.action_policy import Decision, harvest, move, plant, rest, stop, trade, water
from app.skills.types import SkillContext, attach_skill

SKILL_NAME = "Farming Cycle"


def decide_farming_cycle(
    observation: dict[str, object],
    crop: str = "potato",
    target_quantity: int = 3,
    context: SkillContext | None = None,
) -> Decision:
    del context
    inventory = observation.get("inventory", {})
    inventory = inventory if isinstance(inventory, dict) else {}
    location = str(observation.get("location", "farm"))
    farm = observation.get("farm", [])
    farm = farm if isinstance(farm, list) else []
    crop_name = crop.strip().lower().replace(" ", "_")
    seed_item = f"{crop_name}_seed"
    planted = _planted_count(farm, crop_name)
    seeds = int(inventory.get(seed_item, 0))
    harvested = int(inventory.get(crop_name, 0))

    if harvested >= target_quantity:
        return attach_skill(stop("Crop target is already harvested."), SKILL_NAME)
    if planted + seeds + harvested < target_quantity:
        if location != "town":
            return attach_skill(move("town", f"Move to Town to buy {seed_item}."), SKILL_NAME)
        needed = target_quantity - planted - seeds - harvested
        return attach_skill(trade("buy", seed_item, needed, f"Buy {seed_item}."), SKILL_NAME)
    if planted < target_quantity:
        if location != "farm":
            return attach_skill(move("farm", f"Move to Farm to plant {crop_name}."), SKILL_NAME)
        return attach_skill(plant(crop_name, _first_empty_plot(farm), f"Plant {crop_name}."), SKILL_NAME)
    if not _all_crops_ready(farm, crop_name):
        if location != "farm":
            return attach_skill(move("farm", f"Move to Farm to tend {crop_name}."), SKILL_NAME)
        if _has_dry_crop(farm):
            return attach_skill(water(f"Water {crop_name} crops."), SKILL_NAME)
        return attach_skill(rest(f"Advance growth for {crop_name} crops."), SKILL_NAME)
    if location != "farm":
        return attach_skill(move("farm", f"Move to Farm to harvest {crop_name}."), SKILL_NAME)
    return attach_skill(harvest(f"Harvest mature {crop_name} crops."), SKILL_NAME)


def _planted_count(farm: list[object], crop: str) -> int:
    return sum(1 for plot in farm if isinstance(plot, dict) and plot.get("crop") == crop)


def _first_empty_plot(farm: list[object]) -> int:
    for plot in farm:
        if isinstance(plot, dict) and plot.get("crop") is None:
            return int(plot["plot_id"])
    return 1


def _has_dry_crop(farm: list[object]) -> bool:
    return any(
        isinstance(plot, dict) and plot.get("crop") is not None and not plot.get("watered")
        for plot in farm
    )


def _all_crops_ready(farm: list[object], crop: str) -> bool:
    crops = [plot for plot in farm if isinstance(plot, dict) and plot.get("crop") == crop]
    return bool(crops) and all(bool(plot.get("ready")) for plot in crops)
