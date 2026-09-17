"""Structured tool wrappers for agent use."""

from app.tools.combat import fight
from app.tools.crafting import craft
from app.tools.farming import harvest, plant, water
from app.tools.fishing import fish
from app.tools.gathering import forage
from app.tools.inspection import inspect
from app.tools.items import use_item
from app.tools.mining import mine
from app.tools.movement import move
from app.tools.quests import accept_quest, submit_quest
from app.tools.resting import rest
from app.tools.trading import trade

MVP_TOOLS = (
    "move",
    "plant",
    "water",
    "harvest",
    "forage",
    "mine",
    "fish",
    "craft",
    "trade",
    "accept_quest",
    "submit_quest",
    "use_item",
    "fight",
    "inspect",
    "rest",
)

__all__ = [
    "MVP_TOOLS",
    "accept_quest",
    "craft",
    "fight",
    "fish",
    "forage",
    "harvest",
    "inspect",
    "mine",
    "move",
    "plant",
    "rest",
    "submit_quest",
    "trade",
    "use_item",
    "water",
]
