"""Inspection tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def inspect(game: SurvivalGame, target: str) -> ActionResult:
    return game.inspect(target)
