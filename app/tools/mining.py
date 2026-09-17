"""Mining tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def mine(game: SurvivalGame) -> ActionResult:
    return game.mine()
