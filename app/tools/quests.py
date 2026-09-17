"""Guild quest tool wrappers."""

from app.environment import ActionResult, SurvivalGame


def accept_quest(game: SurvivalGame, quest_id: str) -> ActionResult:
    return game.accept_quest(quest_id)


def submit_quest(game: SurvivalGame, quest_id: str) -> ActionResult:
    return game.submit_quest(quest_id)
