"""Item names and item metadata for HarvestAgent."""

CROPS = {"turnip", "potato", "tomato", "pumpkin"}
SEEDS = {"turnip_seed", "potato_seed", "tomato_seed", "pumpkin_seed"}
RAW_MATERIALS = {"wood", "berry", "herb", "wild_flower", "stone", "copper", "iron", "crystal"}
FISH = {"small_fish", "big_fish", "trash"}
CONSUMABLES = {"berry", "bread", "cooked_fish", "potion"}
EQUIPMENT = {"wooden_sword", "iron_sword", "basic_pickaxe", "iron_pickaxe"}
KEY_ITEMS = {"ancient_key", "guardian_gem"}
FARM_UPGRADES = {"sprinkler"}

ALL_ITEMS = CROPS | SEEDS | RAW_MATERIALS | FISH | CONSUMABLES | EQUIPMENT | KEY_ITEMS

BUY_PRICES = {
    "turnip_seed": 20,
    "potato_seed": 35,
    "tomato_seed": 60,
    "pumpkin_seed": 100,
    "bread": 30,
    "potion": 60,
    "copper": 50,
    "iron": 100,
    "ancient_key": 500,
}

SELL_PRICES = {
    "turnip": 45,
    "potato": 90,
    "tomato": 80,
    "pumpkin": 260,
    "wood": 10,
    "berry": 8,
    "wild_flower": 20,
    "copper": 35,
    "iron": 70,
    "small_fish": 20,
    "big_fish": 50,
}

HP_ITEMS = {
    "berry": 5,
    "bread": 15,
    "cooked_fish": 25,
    "potion": 40,
}
