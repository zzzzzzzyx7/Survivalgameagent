"""Location definitions for the HarvestAgent world."""

from app.environment.energy import ACTION_ENERGY_COSTS

LOCATIONS = {"farm", "town", "forest", "mine", "river", "guild"}

DEFAULT_MOVE_COST = {"energy": ACTION_ENERGY_COSTS["move"]}
MINE_MOVE_COST = {"energy": ACTION_ENERGY_COSTS["move_to_or_from_mine"]}

MOVE_COSTS = {
    (origin, destination): (
        MINE_MOVE_COST.copy()
        if "mine" in {origin, destination}
        else DEFAULT_MOVE_COST.copy()
    )
    for origin in LOCATIONS
    for destination in LOCATIONS
    if origin != destination
}

FOREST_TABLE = {
    "wood": {
        "min_quantity": 1,
        "max_quantity": 3,
        "energy": ACTION_ENERGY_COSTS["forage"],
    },
    "berry": {
        "min_quantity": 1,
        "max_quantity": 2,
        "energy": ACTION_ENERGY_COSTS["forage"],
    },
    "herb": {
        "min_quantity": 1,
        "max_quantity": 1,
        "energy": ACTION_ENERGY_COSTS["forage"],
    },
    "wild_flower": {
        "min_quantity": 1,
        "max_quantity": 1,
        "energy": ACTION_ENERGY_COSTS["forage"],
    },
}
