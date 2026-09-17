"""Guild quest definitions."""

QUESTS = {
    "Q_WOOD_8": {
        "quest_id": "Q_WOOD_8",
        "description": "Deliver Wood x8 before Day 5.",
        "deadline_day": 5,
        "requirements": {"items": {"wood": 8}},
        "rewards": {"gold": 150},
    },
    "Q_POTATO_3": {
        "quest_id": "Q_POTATO_3",
        "description": "Deliver Potato x3 before Day 8.",
        "deadline_day": 8,
        "requirements": {"items": {"potato": 3}},
        "rewards": {"gold": 250},
    },
    "Q_GOBLIN_2": {
        "quest_id": "Q_GOBLIN_2",
        "description": "Defeat Goblin x2.",
        "deadline_day": 14,
        "requirements": {"defeated": {"goblin": 2}},
        "rewards": {"items": {"iron": 2}},
    },
    "Q_BIG_FISH_2": {
        "quest_id": "Q_BIG_FISH_2",
        "description": "Deliver Big Fish x2 for an Ancient Key.",
        "deadline_day": 14,
        "requirements": {"items": {"big_fish": 2}},
        "rewards": {"items": {"ancient_key": 1}},
    },
}
