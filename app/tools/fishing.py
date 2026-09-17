"""Fishing tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def fish(game: SurvivalGame) -> ActionResult:
    return game.fish()
