"""Farm action tool wrappers."""

from app.environment.game import SurvivalGame
from app.environment.state import ActionResult


def plant(game: SurvivalGame, crop: str, plot: int | None = None) -> ActionResult:
    return game.plant(crop, plot)


def water(game: SurvivalGame, plot: int | str = "all") -> ActionResult:
    return game.water(plot)


def harvest(game: SurvivalGame, plot: int | str = "all") -> ActionResult:
    return game.harvest(plot)
