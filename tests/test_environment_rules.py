from app.environment import GameState, SurvivalGame
from app.environment.energy import ACTION_ENERGY_COSTS
from app.environment.events import EVENT_TYPES
from app.environment.locations import LOCATIONS, MOVE_COSTS
from app.environment.rewards import success_condition_met


def make_clear_weather_game() -> SurvivalGame:
    state = GameState(weather_today="sunny", weather_tomorrow="sunny")
    return SurvivalGame(initial_state=state, seed=1)


def test_buy_plant_water_harvest_and_sell_potato() -> None:
    game = make_clear_weather_game()

    assert game.move("town").success
    assert game.trade("buy", "potato_seed", 1).success
    assert game.move("farm").success
    assert game.plant("potato", 1).success

    for _ in range(5):
        if not game.state.farm[0].watered:
            assert game.water(1).success
        game.rest()

    assert game.harvest(1).success
    assert game.state.inventory["potato"] == 1
    assert game.move("town").success
    assert game.trade("sell", "potato", 1).success
    assert game.state.gold == 555


def test_bulk_plant_and_water_consume_energy_per_plot() -> None:
    game = make_clear_weather_game()
    game.state.inventory["potato_seed"] = 9

    planted = game.plant("potato")

    assert planted.success
    assert planted.state_changes["potato_seed"] == "-9"
    assert planted.state_changes["energy"] == "-45"
    assert game.state.energy == 55
    assert sum(1 for plot in game.state.farm if plot.crop == "potato") == 9

    watered = game.water("all")

    assert watered.success
    assert watered.state_changes["energy"] == "-27"
    assert game.state.energy == 28


def test_invalid_action_consumes_step_but_not_energy() -> None:
    game = make_clear_weather_game()
    before_energy = game.state.energy
    before_step = game.state.step

    result = game.plant("turnip")

    assert not result.success
    assert result.error_code == "NO_SEED"
    assert game.state.energy == before_energy
    assert game.state.step == before_step + 1
    assert result.state_changes == {}


def test_observation_has_no_clock_time() -> None:
    game = make_clear_weather_game()

    assert "time" not in game.observe()


def test_consumables_restore_hp_not_energy() -> None:
    game = make_clear_weather_game()
    game.state.hp = 70
    game.state.energy = 50
    game.state.inventory["berry"] = 1

    result = game.use_item("berry")

    assert result.success
    assert game.state.hp == 75
    assert game.state.energy == 50 - ACTION_ENERGY_COSTS["use_item"]
    assert "energy" in result.state_changes


def test_rest_is_the_only_energy_recovery_path() -> None:
    game = make_clear_weather_game()
    game.state.energy = 25

    result = game.rest()

    assert result.success
    assert game.state.day == 2
    assert game.state.energy == 100


def test_forage_has_no_daily_count_limit() -> None:
    game = make_clear_weather_game()
    game.state.location = "forest"

    results = [game.forage("wood") for _ in range(10)]

    assert all(result.success for result in results)
    assert results[-1].state_changes["energy"] == "-10"
    assert game.state.day == 2
    assert game.state.location == "farm"
    assert game.state.inventory["wood"] >= 10


def test_movement_table_is_frozen_for_all_directed_location_pairs() -> None:
    expected_route_count = len(LOCATIONS) * (len(LOCATIONS) - 1)

    assert len(MOVE_COSTS) == expected_route_count
    assert MOVE_COSTS[("farm", "town")] == {"energy": ACTION_ENERGY_COSTS["move"]}
    assert MOVE_COSTS[("farm", "mine")] == {
        "energy": ACTION_ENERGY_COSTS["move_to_or_from_mine"]
    }
    assert MOVE_COSTS[("mine", "guild")] == {
        "energy": ACTION_ENERGY_COSTS["move_to_or_from_mine"]
    }


def test_storm_is_weather_only_not_daily_event() -> None:
    assert "storm" not in EVENT_TYPES


def test_fishing_and_big_fish_quest_can_award_key() -> None:
    game = make_clear_weather_game()
    game.state.inventory["big_fish"] = 2

    assert game.move("guild").success
    assert game.accept_quest("Q_BIG_FISH_2").success
    assert game.submit_quest("Q_BIG_FISH_2").success

    assert game.state.inventory["ancient_key"] == 1
    assert "Q_BIG_FISH_2" in game.state.completed_quests


def test_observation_exposes_defeated_counter_for_quest_progress() -> None:
    game = make_clear_weather_game()
    game.state.world_state["defeated"]["goblin"] = 1

    assert game.observe()["defeated"] == {"goblin": 1}


def test_expired_quest_cannot_be_accepted() -> None:
    game = make_clear_weather_game()
    game.state.day = 6

    assert game.move("guild").success
    result = game.accept_quest("Q_WOOD_8")

    assert not result.success
    assert result.error_code == "QUEST_EXPIRED"


def test_guardian_requires_mine_level_and_can_be_defeated() -> None:
    game = make_clear_weather_game()
    game.state.location = "mine"
    game.state.world_state["mine_level"] = 3
    game.state.inventory["ancient_key"] = 1
    game.state.equipment["iron_sword"] = True
    game.state.world_state["pending_enemy"] = "guardian"

    result = game.fight("fight")

    assert result.success
    assert game.state.inventory["guardian_gem"] == 1


def test_guardian_requires_ancient_key() -> None:
    game = make_clear_weather_game()
    game.state.location = "mine"
    game.state.world_state["pending_enemy"] = "guardian"

    result = game.fight("fight")

    assert not result.success
    assert result.error_code == "NO_ANCIENT_KEY"


def test_sprinkler_auto_waters_one_plot() -> None:
    game = make_clear_weather_game()
    game.state.inventory.update({"copper": 2, "iron": 1, "turnip_seed": 1})

    assert game.craft("sprinkler").success
    assert game.plant("turnip", 1).success
    game.rest()

    assert game.state.farm[0].sprinkler
    assert game.state.farm[0].watered


def test_pickaxe_reduces_mining_energy_cost() -> None:
    game = make_clear_weather_game()
    game.state.location = "town"
    game.state.inventory["iron"] = 3
    game.state.gold = 500

    assert game.craft("iron_pickaxe").success
    game.state.location = "mine"
    before = game.state.energy
    assert game.mine().success

    assert before - game.state.energy == ACTION_ENERGY_COSTS["mine_with_iron_pickaxe"]


def test_goal_g05_success_condition() -> None:
    game = make_clear_weather_game()
    game.state.inventory["ancient_key"] = 1
    game.state.inventory["guardian_gem"] = 1
    game.state.equipment["iron_sword"] = True

    assert success_condition_met(game.state, "g05_defeat_guardian")
