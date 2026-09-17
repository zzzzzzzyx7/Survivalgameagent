from app.agents import DirectAgent
from app.environment import ActionResult, GameState, SurvivalGame
from app.skills import FIRST_STAGE_SKILLS, SkillContext
from app.skills.fishing_route import decide_fishing_route
from app.skills.quest_completion import decide_quest_completion
from app.skills.resource_acquisition import decide_resource_acquisition
from app.tools import MVP_TOOLS
from evaluation.metrics import invalid_action_rate, success_rate
from evaluation.runner import _execute_decision


def test_environment_exports_core_types() -> None:
    game = SurvivalGame()

    assert isinstance(game.state, GameState)
    assert isinstance(game.inspect("state"), ActionResult)


def test_metrics_empty_inputs() -> None:
    assert success_rate([]) == 0.0
    assert invalid_action_rate([]) == 0.0


def test_mvp_tool_registry_is_fixed_to_fifteen_tools() -> None:
    assert MVP_TOOLS == (
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


def test_first_stage_skill_registry_is_fixed_to_seven_skills() -> None:
    assert FIRST_STAGE_SKILLS == (
        "Resource Acquisition",
        "Farming Cycle",
        "Fishing Route",
        "Money Making",
        "Combat Preparation",
        "Recovery",
        "Quest Completion",
    )


def test_skill_inspect_switch_controls_inspect_decisions() -> None:
    observation = {"inventory": {"big_fish": 2}}

    allowed = decide_fishing_route(observation, context=SkillContext(allow_inspect=True))
    blocked = decide_fishing_route(observation, context=SkillContext(allow_inspect=False))

    assert allowed["tool"] == "inspect"
    assert blocked["tool"] == "stop"


def test_fishing_route_makes_fish_tool_necessary() -> None:
    decision = decide_fishing_route(
        {"location": "river", "inventory": {}, "energy": 100, "weather_today": "sunny"},
        target_item="big_fish",
        quantity=2,
    )

    assert decision["tool"] == "fish"
    assert decision["skill"] == "Fishing Route"


def test_resource_acquisition_can_delegate_to_fishing_route() -> None:
    decision = decide_resource_acquisition(
        {"location": "farm", "inventory": {}, "energy": 100, "weather_today": "sunny"},
        "big_fish",
        2,
    )

    assert decision["tool"] == "move"
    assert decision["args"] == {"location": "river"}
    assert decision["skill"] == "Resource Acquisition"


def test_quest_completion_accepts_and_submits_big_fish_quest() -> None:
    game = SurvivalGame(initial_state=GameState(weather_today="sunny", weather_tomorrow="sunny"))
    agent = DirectAgent()

    decision = agent.decide(game.observe(), "Complete Q_BIG_FISH_2 quest.")
    assert decision["tool"] == "move"
    assert decision["args"] == {"location": "guild"}
    assert decision["skill"] == "Quest Completion"
    assert _execute_decision(game, decision).success

    decision = agent.decide(game.observe(), "Complete Q_BIG_FISH_2 quest.")
    assert decision["tool"] == "accept_quest"
    assert decision["args"] == {"quest_id": "Q_BIG_FISH_2"}
    assert _execute_decision(game, decision).success

    decision = decide_quest_completion(game.observe(), "Q_BIG_FISH_2")
    assert decision["tool"] == "move"
    assert decision["args"] == {"location": "river"}

    game.state.inventory["big_fish"] = 2
    decision = agent.decide(game.observe(), "Complete Q_BIG_FISH_2 quest.")
    assert decision["tool"] == "submit_quest"
    assert _execute_decision(game, decision).success
    assert game.state.inventory["ancient_key"] == 1


def test_quest_completion_routes_goblin_defeat_requirement() -> None:
    decision = decide_quest_completion(
        {
            "location": "mine",
            "inventory": {},
            "energy": 100,
            "hp": 100,
            "weather_today": "sunny",
            "event_today": None,
            "mine_level": 2,
            "pending_enemy": "goblin",
            "active_quests": {
                "Q_GOBLIN_2": {
                    "requirements": {"defeated": {"goblin": 2}},
                    "deadline_day": 14,
                }
            },
            "completed_quests": [],
            "defeated": {"goblin": 1},
        },
        "Q_GOBLIN_2",
    )

    assert decision["tool"] == "fight"
    assert decision["args"] == {"action": "fight"}
    assert decision["skill"] == "Quest Completion"
