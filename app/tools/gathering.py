"""Gathering tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def forage(game: SurvivalGame, resource: str) -> ActionResult:
    return game.forage(resource)
