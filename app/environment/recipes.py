"""Crafting recipes owned by the deterministic environment."""

from __future__ import annotations

from dataclasses import dataclass

from app.environment.energy import ACTION_ENERGY_COSTS


@dataclass(frozen=True)
class Recipe:
    item: str
    ingredients: dict[str, int]
    energy_cost: int = ACTION_ENERGY_COSTS["craft"]
    gold_cost: int = 0
    required_locations: set[str] | None = None
    output_kind: str = "inventory"


CRAFT_LOCATIONS = {"farm", "town"}

RECIPES = {
    "wooden_sword": Recipe(
        item="wooden_sword",
        ingredients={"wood": 5},
        required_locations=CRAFT_LOCATIONS,
        output_kind="equipment",
    ),
    "iron_sword": Recipe(
        item="iron_sword",
        ingredients={"wood": 3, "iron": 2},
        required_locations=CRAFT_LOCATIONS,
        output_kind="equipment",
    ),
    "potion": Recipe(
        item="potion",
        ingredients={"herb": 2, "berry": 1},
        required_locations=CRAFT_LOCATIONS,
    ),
    "sprinkler": Recipe(
        item="sprinkler",
        ingredients={"copper": 2, "iron": 1},
        required_locations={"farm"},
        output_kind="farm_upgrade",
    ),
    "iron_pickaxe": Recipe(
        item="iron_pickaxe",
        ingredients={"iron": 3},
        gold_cost=150,
        required_locations={"town"},
        output_kind="equipment",
    ),
}
