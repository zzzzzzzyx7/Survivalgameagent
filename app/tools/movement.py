"""Movement tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def move(game: SurvivalGame, location: str) -> ActionResult:
    return game.move(location)
