import json
from pathlib import Path

from app.environment import GameState, SurvivalGame
from app.environment.rewards import success_condition_met
from evaluation.runner import run_episode

TASK_DIR = Path("evaluation/tasks")


def make_game(goal: dict[str, object], seed: int = 2) -> SurvivalGame:
    state = GameState(weather_today="sunny", weather_tomorrow="sunny", goal=goal)
    return SurvivalGame(initial_state=state, seed=seed)


def assert_success(result) -> None:
    assert result.success, result.to_dict()


def test_benchmark_task_success_conditions_are_registered() -> None:
    for task_file in TASK_DIR.glob("*.json"):
        task = json.loads(task_file.read_text(encoding="utf-8"))
        condition = task["success_condition"]

        assert not success_condition_met(GameState(), condition), task_file.name


def test_benchmark_task_success_conditions_can_be_met() -> None:
    cases = {
        "g01_900_gold_by_day_7": lambda state: setattr(state, "gold", 900),
        "g02_iron_sword_by_day_8": lambda state: state.equipment.update(
            {"iron_sword": True}
        ),
        "g03_harvest_3_potato_by_day_10": lambda state: state.world_state[
            "harvested"
        ].update({"potato": 3}),
        "g04_ancient_key_by_day_12": lambda state: state.inventory.update(
            {"ancient_key": 1}
        ),
        "g05_defeat_guardian": lambda state: (
            state.inventory.update({"ancient_key": 1, "guardian_gem": 1}),
            state.equipment.update({"iron_sword": True}),
        ),
    }

    for condition, arrange in cases.items():
        state = GameState(goal={"deadline_day": 14, "success_condition": condition})
        arrange(state)

        assert success_condition_met(state, condition), condition


def test_g01_to_g05_tasks_use_full_fourteen_day_episode() -> None:
    for task_id in ("G01", "G02", "G03", "G04", "G05"):
        task = json.loads(next(TASK_DIR.glob(f"{task_id}_*.json")).read_text(encoding="utf-8"))

        assert task["max_day"] == 14


def test_g01_to_g04_success_conditions_do_not_have_early_day_cutoffs() -> None:
    cases = {
        "g01_900_gold_by_day_7": lambda state: setattr(state, "gold", 900),
        "g02_iron_sword_by_day_8": lambda state: state.equipment.update(
            {"iron_sword": True}
        ),
        "g03_harvest_3_potato_by_day_10": lambda state: state.world_state[
            "harvested"
        ].update({"potato": 3}),
        "g04_ancient_key_by_day_12": lambda state: state.inventory.update(
            {"ancient_key": 1}
        ),
    }

    for condition, arrange in cases.items():
        state = GameState(goal={"deadline_day": 14, "success_condition": condition})
        state.day = 13
        arrange(state)

        assert success_condition_met(state, condition), condition


def test_all_success_condition_requires_every_subtask() -> None:
    state = GameState(
        goal={
            "deadline_day": 14,
            "success_condition": "all:g01_900_gold_by_day_7;g02_iron_sword_by_day_8",
        }
    )
    state.gold = 900

    assert not success_condition_met(state, state.goal["success_condition"])

    state.equipment["iron_sword"] = True

    assert success_condition_met(state, state.goal["success_condition"])


def test_storm_and_mine_collapse_close_mine() -> None:
    storm_game = SurvivalGame(initial_state=GameState(weather_today="storm"))

    result = storm_game.move("mine")

    assert not result.success
    assert result.error_code == "LOCATION_CLOSED"

    collapse_state = GameState(weather_today="sunny")
    collapse_state.world_state["event_today"] = "mine_collapse"
    collapse_game = SurvivalGame(initial_state=collapse_state)

    result = collapse_game.move("mine")

    assert not result.success
    assert result.error_code == "LOCATION_CLOSED"


def test_move_rejects_unknown_location_and_same_location() -> None:
    game = make_game({"deadline_day": 14, "success_condition": "g05_defeat_guardian"})

    unknown = game.move("moon")
    same_place = game.move("farm")

    assert not unknown.success
    assert unknown.error_code == "INVALID_LOCATION"
    assert not same_place.success
    assert same_place.error_code == "ALREADY_THERE"


def test_trade_rejects_wrong_location_unknown_item_and_insufficient_gold() -> None:
    game = make_game({"deadline_day": 14, "success_condition": "g05_defeat_guardian"})

    wrong_location = game.trade("buy", "iron", 1)
    assert not wrong_location.success
    assert wrong_location.error_code == "WRONG_LOCATION"

    assert_success(game.move("town"))
    unknown_item = game.trade("buy", "dragon_egg", 1)
    assert not unknown_item.success
    assert unknown_item.error_code == "ITEM_NOT_FOR_SALE"

    game.state.gold = 0
    insufficient_gold = game.trade("buy", "iron", 1)
    assert not insufficient_gold.success
    assert insufficient_gold.error_code == "NOT_ENOUGH_GOLD"


def test_craft_rejects_missing_resources_and_creates_equipment() -> None:
    game = make_game({"deadline_day": 14, "success_condition": "g05_defeat_guardian"})

    missing = game.craft("iron_sword")
    assert not missing.success
    assert missing.error_code == "INSUFFICIENT_RESOURCES"

    game.state.inventory.update({"wood": 3, "iron": 2})
    crafted = game.craft("iron_sword")

    assert crafted.success
    assert game.state.equipment["iron_sword"]
    assert "iron_sword" not in game.state.inventory


def test_scripted_runner_records_trace_and_metrics_for_g02() -> None:
    episode = run_episode("scripted", "G02", seed=2)

    assert episode["success"]
    assert episode["done"]
    assert episode["invalid_actions"] == 0
    assert episode["total_actions"] == len(episode["trace"])
    assert episode["steps"] >= episode["total_actions"]
    assert episode["trace"][0]["action"] == "move"
    assert episode["final_state"]["equipment"]["iron_sword"]
