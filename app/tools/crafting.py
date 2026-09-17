"""Crafting tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def craft(game: SurvivalGame, item: str) -> ActionResult:
    return game.craft(item)
