"""Trading tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def trade(game: SurvivalGame, action: str, item: str, quantity: int) -> ActionResult:
    return game.trade(action, item, quantity)
