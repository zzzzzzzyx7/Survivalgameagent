"""Item use tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def use_item(game: SurvivalGame, item: str) -> ActionResult:
    return game.use_item(item)
