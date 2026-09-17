"""Game state and action result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_DAY = 14


@dataclass
class FarmPlot:
    plot_id: int
    crop: str | None = None
    growth: int = 0
    watered: bool = False
    sprinkler: bool = False
    diseased: bool = False

    @property
    def empty(self) -> bool:
        return self.crop is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "crop": self.crop,
            "growth": self.growth,
            "watered": self.watered,
            "sprinkler": self.sprinkler,
            "diseased": self.diseased,
        }


def default_world_state() -> dict[str, Any]:
    return {
        "mine_progress": {1: 0, 2: 0},
        "mine_level": 1,
        "pending_enemy": None,
        "defeated": {},
        "harvested": {},
        "event_today": None,
        "merchant_discount": None,
    }


def default_goal() -> dict[str, Any]:
    return {
        "goal_id": "G05",
        "description": "Get Ancient Key and Iron Sword, then defeat the Mine Guardian by Day 14.",
        "deadline_day": 14,
        "success_condition": "g05_defeat_guardian",
    }


@dataclass
class GameState:
    day: int = 1
    step: int = 0
    hp: int = 100
    energy: int = 100
    gold: int = 500
    location: str = "farm"
    weather_today: str = "sunny"
    weather_tomorrow: str = "sunny"
    inventory: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, bool] = field(default_factory=dict)
    farm: list[FarmPlot] = field(
        default_factory=lambda: [FarmPlot(i) for i in range(1, 10)]
    )
    available_quests: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_quests: dict[str, dict[str, Any]] = field(default_factory=dict)
    completed_quests: set[str] = field(default_factory=set)
    world_state: dict[str, Any] = field(default_factory=default_world_state)
    goal: dict[str, Any] = field(default_factory=default_goal)
    done: bool = False
    success: bool = False


@dataclass(frozen=True)
class ActionResult:
    success: bool
    action: str
    observation: str
    step: int
    state_changes: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "success": self.success,
            "action": self.action,
            "observation": self.observation,
            "state_changes": self.state_changes,
            "events": self.events,
            "step": self.step,
        }
        if self.error_code is not None:
            payload["error_code"] = self.error_code
        return payload
