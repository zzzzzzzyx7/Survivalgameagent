"""Combat tool wrapper."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def fight(game: SurvivalGame, action: str = "fight") -> ActionResult:
    return game.fight(action)
