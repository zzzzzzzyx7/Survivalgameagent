"""Rest tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def rest(game: SurvivalGame) -> ActionResult:
    return game.rest()
