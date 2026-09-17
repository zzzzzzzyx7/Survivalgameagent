"""Combat definitions and deterministic combat helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnemySpec:
    enemy: str
    hp: int
    damage: int
    reward_gold: int = 0
    reward_items: dict[str, int] | None = None


ENEMIES = {
    "slime": EnemySpec("slime", hp=20, damage=5, reward_gold=10),
    "goblin": EnemySpec("goblin", hp=40, damage=12, reward_gold=25),
    "guardian": EnemySpec(
        "guardian",
        hp=75,
        damage=18,
        reward_items={"guardian_gem": 1},
    ),
}

WEAPON_DAMAGE = {
    "none": 5,
    "wooden_sword": 15,
    "iron_sword": 30,
}
