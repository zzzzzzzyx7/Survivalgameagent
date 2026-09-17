"""Main deterministic game environment facade."""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

from app.environment.combat import ENEMIES, WEAPON_DAMAGE
from app.environment.crops import CROPS
from app.environment.energy import ACTION_ENERGY_COSTS
from app.environment.events import (
    DAILY_EVENT_CHANCE,
    DISCOUNT_MULTIPLIER,
    EVENT_TYPES,
    MERCHANT_DISCOUNT_ITEMS,
)
from app.environment.items import BUY_PRICES, HP_ITEMS, SELL_PRICES
from app.environment.locations import FOREST_TABLE, LOCATIONS, MOVE_COSTS
from app.environment.quests import QUESTS
from app.environment.recipes import RECIPES
from app.environment.rewards import success_condition_met
from app.environment.state import MAX_DAY, ActionResult, FarmPlot, GameState
from app.environment.weather import (
    WEATHER_WEIGHTS,
    is_auto_water_weather,
    is_mine_closed,
    is_river_closed,
)


class SurvivalGame:
    """Owns the true HarvestAgent world state and exposes rule-checked actions."""

    def __init__(self, initial_state: GameState | None = None, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.seed = seed
        self.state = initial_state or GameState()
        self._ensure_state_defaults()
        if initial_state is None:
            self.state.weather_today = self._roll_weather()
            self.state.weather_tomorrow = self._roll_weather()
            self.state.available_quests = deepcopy(QUESTS)
            self._roll_daily_event()
        self._apply_auto_water()
        self._check_goal()

    def observe(self) -> dict[str, object]:
        return {
            "day": self.state.day,
            "step": self.state.step,
            "hp": self.state.hp,
            "energy": self.state.energy,
            "gold": self.state.gold,
            "location": self.state.location,
            "weather_today": self.state.weather_today,
            "weather_tomorrow": self.state.weather_tomorrow,
            "event_today": self.state.world_state["event_today"],
            "merchant_discount": self.state.world_state["merchant_discount"],
            "inventory": self._visible_inventory(),
            "equipment": dict(self.state.equipment),
            "farm": self._visible_farm(),
            "mine_level": self.state.world_state["mine_level"],
            "pending_enemy": self.state.world_state["pending_enemy"],
            "defeated": dict(self.state.world_state["defeated"]),
            "available_quests": deepcopy(self.state.available_quests),
            "active_quests": deepcopy(self.state.active_quests),
            "completed_quests": sorted(self.state.completed_quests),
            "goal": dict(self.state.goal),
            "done": self.state.done,
            "success": self.state.success,
            "energy_costs": dict(ACTION_ENERGY_COSTS),
        }

    def move(self, location: str) -> ActionResult:
        target = self._normalize(location)
        if target not in LOCATIONS:
            return self._fail("move", "INVALID_LOCATION", f"Unknown location: {location}.")
        if target == self.state.location:
            return self._fail("move", "ALREADY_THERE", f"You are already at {target}.")
        if target == "mine" and self._mine_is_closed():
            return self._fail("move", "LOCATION_CLOSED", "The mine is closed today.")
        if target == "river" and is_river_closed(self.state.weather_today):
            return self._fail("move", "LOCATION_CLOSED", "The river is closed during a storm.")

        cost = MOVE_COSTS.get((self.state.location, target))
        if cost is None:
            return self._fail(
                "move",
                "NO_ROUTE",
                f"No route from {self.state.location} to {target}.",
            )
        if not self._has_energy(cost["energy"]):
            return self._fail("move", "NOT_ENOUGH_ENERGY", "Not enough Energy to move.")

        previous = self.state.location
        self.state.location = target
        self._advance(cost["energy"])
        return self._ok(
            "move",
            f"Moved from {previous} to {target}.",
            {
                "location": f"{previous}->{target}",
                "energy": f"-{cost['energy']}",
            },
        )

    def plant(
        self,
        crop: str,
        plot: int | str | None = None,
        quantity: int | None = None,
    ) -> ActionResult:
        crop_name = self._normalize(crop)
        if self.state.location != "farm":
            return self._fail("plant", "WRONG_LOCATION", "You can only plant crops at the farm.")
        if crop_name not in CROPS:
            return self._fail("plant", "UNKNOWN_CROP", f"Unknown crop: {crop}.")

        seed_item = CROPS[crop_name].seed_item
        seed_count = self.state.inventory.get(seed_item, 0)
        if seed_count <= 0:
            return self._fail("plant", "NO_SEED", f"You do not have {seed_item}.")

        plots = self._plant_target_plots(plot, quantity, seed_count)
        if not plots:
            return self._fail("plant", "NO_EMPTY_PLOT", "No empty plot is available.")
        occupied = [farm_plot for farm_plot in plots if not farm_plot.empty]
        if occupied:
            farm_plot = occupied[0]
            return self._fail(
                "plant",
                "PLOT_OCCUPIED",
                f"Plot {farm_plot.plot_id} is already occupied.",
            )

        energy_cost = ACTION_ENERGY_COSTS["plant"] * len(plots)
        if not self._has_energy(energy_cost):
            return self._fail("plant", "NOT_ENOUGH_ENERGY", "Not enough Energy to plant.")

        for farm_plot in plots:
            self._remove_item(seed_item, 1)
            farm_plot.crop = crop_name
            farm_plot.growth = 0
            farm_plot.watered = self._weather_waters() or farm_plot.sprinkler
            farm_plot.diseased = False

        self._advance(energy_cost)
        plot_ids = ", ".join(str(farm_plot.plot_id) for farm_plot in plots)
        return self._ok(
            "plant",
            f"Planted {crop_name} in plot(s): {plot_ids}.",
            {seed_item: f"-{len(plots)}", "energy": f"-{energy_cost}"},
        )

    def water(self, plot: int | str = "all") -> ActionResult:
        if self.state.location != "farm":
            return self._fail("water", "WRONG_LOCATION", "You can only water crops at the farm.")
        if self._weather_waters():
            return self._fail(
                "water",
                "ALREADY_WATERED_BY_WEATHER",
                "Weather has already watered the farm.",
            )

        plots = self._target_plots(plot, include_watered=False)
        if not plots:
            return self._fail("water", "NO_VALID_PLOT", "No planted dry plot can be watered.")

        energy_cost = ACTION_ENERGY_COSTS["water_per_plot"] * len(plots)
        if not self._has_energy(energy_cost):
            return self._fail("water", "NOT_ENOUGH_ENERGY", "Not enough Energy to water.")

        for farm_plot in plots:
            farm_plot.watered = True
        self._advance(energy_cost)
        plot_ids = ", ".join(str(farm_plot.plot_id) for farm_plot in plots)
        return self._ok(
            "water",
            f"Watered plot(s): {plot_ids}.",
            {"energy": f"-{energy_cost}"},
        )

    def harvest(self, plot: int | str = "all") -> ActionResult:
        if self.state.location != "farm":
            return self._fail(
                "harvest",
                "WRONG_LOCATION",
                "You can only harvest crops at the farm.",
            )

        plots = [
            farm_plot
            for farm_plot in self._target_plots(plot, include_watered=True)
            if self._is_mature(farm_plot)
        ]
        if not plots:
            return self._fail("harvest", "NOT_READY", "No selected crop is ready to harvest.")

        energy_cost = ACTION_ENERGY_COSTS["harvest_per_plot"] * len(plots)
        if not self._has_energy(energy_cost):
            return self._fail("harvest", "NOT_ENOUGH_ENERGY", "Not enough Energy to harvest.")

        harvested: dict[str, int] = {}
        for farm_plot in plots:
            if farm_plot.crop is None:
                continue
            crop_name = farm_plot.crop
            spec = CROPS[crop_name]
            harvested[crop_name] = harvested.get(crop_name, 0) + 1
            self._add_item(crop_name, 1)
            self._record_counter("harvested", crop_name, 1)
            if spec.regrow_days is None:
                farm_plot.crop = None
                farm_plot.growth = 0
                farm_plot.watered = False
            else:
                farm_plot.growth = spec.growth_days - spec.regrow_days
                farm_plot.watered = self._weather_waters() or farm_plot.sprinkler

        self._advance(energy_cost)
        changes = {crop: f"+{quantity}" for crop, quantity in harvested.items()}
        changes.update({"energy": f"-{energy_cost}"})
        return self._ok("harvest", f"Harvested {self._format_items(harvested)}.", changes)

    def forage(self, resource: str) -> ActionResult:
        item = self._normalize(resource)
        if self.state.location != "forest":
            return self._fail("forage", "WRONG_LOCATION", "You can only forage in the forest.")
        if item not in FOREST_TABLE:
            return self._fail(
                "forage",
                "UNKNOWN_RESOURCE",
                f"The forest does not provide {resource}.",
        )

        rule = FOREST_TABLE[item]
        if not self._has_energy(rule["energy"]):
            return self._fail("forage", "NOT_ENOUGH_ENERGY", "Not enough Energy to forage.")

        quantity = self.rng.randint(rule["min_quantity"], rule["max_quantity"])
        self._add_item(item, quantity)
        self._advance(rule["energy"])
        return self._ok(
            "forage",
            f"Foraged {quantity} {item}.",
            {
                item: f"+{quantity}",
                "energy": f"-{rule['energy']}",
            },
        )

    def mine(self) -> ActionResult:
        if self.state.location != "mine":
            return self._fail("mine", "WRONG_LOCATION", "You can only mine inside the mine.")
        if self._mine_is_closed():
            return self._fail("mine", "LOCATION_CLOSED", "The mine is closed today.")
        if self.state.world_state["pending_enemy"] is not None:
            return self._fail(
                "mine",
                "ENEMY_BLOCKING",
                "You must resolve the pending enemy encounter before mining.",
            )

        energy_cost = (
            ACTION_ENERGY_COSTS["mine_with_iron_pickaxe"]
            if self.state.equipment.get("iron_pickaxe")
            else ACTION_ENERGY_COSTS["mine"]
        )
        if not self._has_energy(energy_cost):
            return self._fail("mine", "NOT_ENOUGH_ENERGY", "Not enough Energy to mine.")

        mine_level = self.state.world_state["mine_level"]
        drops = self._mine_drops(mine_level)
        for item, quantity in drops.items():
            self._add_item(item, quantity)

        self._advance_mine_progress(mine_level)
        encounter = self._maybe_create_mine_encounter(mine_level)
        self._advance(energy_cost)

        changes = {item: f"+{quantity}" for item, quantity in drops.items()}
        changes.update({"energy": f"-{energy_cost}"})
        observation = f"Mined {self._format_items(drops)}."
        if encounter is not None:
            observation += f" Encountered {encounter}."
        return self._ok("mine", observation, changes)

    def fish(self) -> ActionResult:
        if self.state.location != "river":
            return self._fail("fish", "WRONG_LOCATION", "You can only fish at the river.")
        if is_river_closed(self.state.weather_today):
            return self._fail("fish", "LOCATION_CLOSED", "The river is closed during a storm.")
        energy_cost = ACTION_ENERGY_COSTS["fish"]
        if not self._has_energy(energy_cost):
            return self._fail("fish", "NOT_ENOUGH_ENERGY", "Not enough Energy to fish.")

        roll = self.rng.random()
        if roll < 0.60:
            item = "small_fish"
        elif roll < 0.85:
            item = "big_fish"
        else:
            item = "trash"
        self._add_item(item, 1)
        self._advance(energy_cost)
        return self._ok(
            "fish",
            f"Caught {item}.",
            {item: "+1", "energy": f"-{energy_cost}"},
        )

    def craft(self, item: str) -> ActionResult:
        item_name = self._normalize(item)
        if item_name not in RECIPES:
            return self._fail("craft", "UNKNOWN_RECIPE", f"No recipe for {item}.")

        recipe = RECIPES[item_name]
        if (
            recipe.required_locations is not None
            and self.state.location not in recipe.required_locations
        ):
            return self._fail(
                "craft",
                "WRONG_LOCATION",
                f"{item_name} cannot be crafted at {self.state.location}.",
            )
        if not self._has_energy(recipe.energy_cost):
            return self._fail("craft", "NOT_ENOUGH_ENERGY", "Not enough Energy to craft.")
        if self.state.gold < recipe.gold_cost:
            return self._fail("craft", "NOT_ENOUGH_GOLD", "Not enough Gold to craft.")

        missing = self._missing_items(recipe.ingredients)
        if missing:
            return self._fail(
                "craft",
                "INSUFFICIENT_RESOURCES",
                f"Missing {self._format_items(missing)}.",
            )

        for ingredient, quantity in recipe.ingredients.items():
            self._remove_item(ingredient, quantity)
        self.state.gold -= recipe.gold_cost
        self._apply_craft_output(recipe.item, recipe.output_kind)
        self._advance(recipe.energy_cost)

        changes = {
            ingredient: f"-{quantity}"
            for ingredient, quantity in recipe.ingredients.items()
        }
        changes.update({"energy": f"-{recipe.energy_cost}"})
        if recipe.gold_cost:
            changes["gold"] = f"-{recipe.gold_cost}"
        return self._ok("craft", f"Crafted {item_name}.", changes)

    def trade(self, action: str, item: str, quantity: int) -> ActionResult:
        trade_action = self._normalize(action)
        item_name = self._normalize(item)
        if self.state.location != "town":
            return self._fail("trade", "WRONG_LOCATION", "You can only trade in town.")
        if quantity <= 0:
            return self._fail("trade", "INVALID_QUANTITY", "Quantity must be positive.")
        if trade_action == "buy":
            return self._buy(item_name, quantity)
        if trade_action == "sell":
            return self._sell(item_name, quantity)
        return self._fail("trade", "INVALID_TRADE_ACTION", f"Unknown trade action: {action}.")

    def accept_quest(self, quest_id: str) -> ActionResult:
        normalized = quest_id.strip().upper()
        if self.state.location != "guild":
            return self._fail(
                "accept_quest",
                "WRONG_LOCATION",
                "You can only accept quests at Guild.",
            )
        if normalized in self.state.active_quests or normalized in self.state.completed_quests:
            return self._fail("accept_quest", "QUEST_UNAVAILABLE", "Quest is not available.")
        if normalized not in self.state.available_quests:
            return self._fail("accept_quest", "UNKNOWN_QUEST", f"Unknown quest: {quest_id}.")
        if self.state.day > self.state.available_quests[normalized]["deadline_day"]:
            return self._fail("accept_quest", "QUEST_EXPIRED", "Quest deadline has passed.")

        energy_cost = ACTION_ENERGY_COSTS["accept_quest"]
        if not self._has_energy(energy_cost):
            return self._fail(
                "accept_quest",
                "NOT_ENOUGH_ENERGY",
                "Not enough Energy to accept quest.",
            )
        self.state.active_quests[normalized] = self.state.available_quests.pop(normalized)
        self._advance(energy_cost)
        return self._ok(
            "accept_quest",
            f"Accepted quest {normalized}.",
            {"energy": f"-{energy_cost}"},
        )

    def submit_quest(self, quest_id: str) -> ActionResult:
        normalized = quest_id.strip().upper()
        if self.state.location != "guild":
            return self._fail(
                "submit_quest",
                "WRONG_LOCATION",
                "You can only submit quests at Guild.",
            )
        if normalized not in self.state.active_quests:
            return self._fail("submit_quest", "QUEST_NOT_ACTIVE", "Quest is not active.")

        quest = self.state.active_quests[normalized]
        if self.state.day > quest["deadline_day"]:
            return self._fail("submit_quest", "QUEST_EXPIRED", "Quest deadline has passed.")
        missing = self._missing_quest_requirements(quest)
        if missing:
            return self._fail(
                "submit_quest",
                "QUEST_REQUIREMENTS_MISSING",
                f"Missing {missing}.",
            )

        energy_cost = ACTION_ENERGY_COSTS["submit_quest"]
        if not self._has_energy(energy_cost):
            return self._fail(
                "submit_quest",
                "NOT_ENOUGH_ENERGY",
                "Not enough Energy to submit quest.",
            )
        for item, quantity in quest["requirements"].get("items", {}).items():
            self._remove_item(item, quantity)
        self._apply_rewards(quest["rewards"])
        self.state.completed_quests.add(normalized)
        self.state.active_quests.pop(normalized)
        self._advance(energy_cost)
        return self._ok(
            "submit_quest",
            f"Submitted quest {normalized}.",
            {"energy": f"-{energy_cost}"},
        )

    def fight(self, action: str = "fight") -> ActionResult:
        combat_action = self._normalize(action)
        enemy_name = self.state.world_state["pending_enemy"]
        if self.state.location != "mine":
            return self._fail("fight", "WRONG_LOCATION", "Combat only happens in the mine.")
        if enemy_name is None:
            return self._fail("fight", "NO_ENEMY", "There is no pending enemy encounter.")
        if enemy_name == "guardian" and self.state.inventory.get("ancient_key", 0) <= 0:
            return self._fail("fight", "NO_ANCIENT_KEY", "The Guardian requires Ancient Key.")
        if combat_action == "escape":
            energy_cost = ACTION_ENERGY_COSTS["escape"]
            if not self._has_energy(energy_cost):
                return self._fail("fight", "NOT_ENOUGH_ENERGY", "Not enough Energy to escape.")
            self.state.world_state["pending_enemy"] = None
            self._advance(energy_cost)
            return self._ok(
                "fight",
                f"Escaped from {enemy_name}.",
                {"energy": f"-{energy_cost}"},
            )
        if combat_action == "use_potion":
            return self.use_item("potion")
        if combat_action != "fight":
            return self._fail("fight", "INVALID_COMBAT_ACTION", f"Unknown combat action: {action}.")
        energy_cost = ACTION_ENERGY_COSTS["fight"]
        if not self._has_energy(energy_cost):
            return self._fail("fight", "NOT_ENOUGH_ENERGY", "Not enough Energy to fight.")

        enemy = ENEMIES[enemy_name]
        weapon = self._best_weapon()
        rounds = max(1, (enemy.hp + WEAPON_DAMAGE[weapon] - 1) // WEAPON_DAMAGE[weapon])
        hp_loss = rounds * enemy.damage
        self.state.hp -= hp_loss
        self._advance(energy_cost)

        if self.state.hp <= 0:
            self._apply_knockout()
            return self._ok(
                "fight",
                f"Lost to {enemy_name}. Returned to farm and lost 10 percent Gold.",
                {"hp": str(self.state.hp), "gold": "-10%", "energy": f"-{energy_cost}"},
            )

        self.state.world_state["pending_enemy"] = None
        self._record_counter("defeated", enemy_name, 1)
        if enemy.reward_gold:
            self.state.gold += enemy.reward_gold
        for item, quantity in (enemy.reward_items or {}).items():
            self._add_item(item, quantity)
        changes = {"hp": f"-{hp_loss}", "energy": f"-{energy_cost}"}
        if enemy.reward_gold:
            changes["gold"] = f"+{enemy.reward_gold}"
        if enemy.reward_items:
            changes.update(
                {item: f"+{quantity}" for item, quantity in enemy.reward_items.items()}
            )
        return self._ok("fight", f"Defeated {enemy_name}.", changes)

    def rest(self) -> ActionResult:
        previous_day = self.state.day
        self._increment_step()
        self._end_day(reason="rest")
        return self._result(
            True,
            "rest",
            f"Rested. Day {previous_day} ended.",
            {"day": f"{previous_day}->{self.state.day}", "energy": str(self.state.energy)},
        )

    def use_item(self, item: str) -> ActionResult:
        item_name = self._normalize(item)
        if self.state.inventory.get(item_name, 0) <= 0:
            return self._fail("use_item", "NO_ITEM", f"You do not have {item_name}.")
        if item_name not in HP_ITEMS:
            return self._fail("use_item", "ITEM_NOT_USABLE", f"{item_name} cannot be used.")

        energy_cost = ACTION_ENERGY_COSTS["use_item"]
        if not self._has_energy(energy_cost):
            return self._fail("use_item", "NOT_ENOUGH_ENERGY", "Not enough Energy to use item.")

        changes = {item_name: "-1"}
        self._remove_item(item_name, 1)
        before = self.state.hp
        self.state.hp = min(100, self.state.hp + HP_ITEMS[item_name])
        changes["hp"] = f"+{self.state.hp - before}"
        changes["energy"] = f"-{energy_cost}"
        self._advance(energy_cost)
        return self._ok("use_item", f"Used {item_name}.", changes)

    def inspect(self, target: str) -> ActionResult:
        normalized = self._normalize(target)
        lookup: dict[str, Any] = {
            "state": self.observe(),
            "farm": self._visible_farm(),
            "shop": {"buy_prices": self._current_buy_prices(), "sell_prices": SELL_PRICES},
            "recipes": {name: recipe.ingredients for name, recipe in RECIPES.items()},
            "weather": {
                "today": self.state.weather_today,
                "tomorrow": self.state.weather_tomorrow,
            },
            "quests": {
                "available": self.state.available_quests,
                "active": self.state.active_quests,
                "completed": sorted(self.state.completed_quests),
            },
            "goal": dict(self.state.goal),
        }
        return self._result(True, "inspect", str(lookup.get(normalized, "unknown")), {})

    def invalid_action(self, action: str, code: str, observation: str) -> ActionResult:
        return self._fail(action, code, observation)

    def _buy(self, item: str, quantity: int) -> ActionResult:
        prices = self._current_buy_prices()
        if item not in prices:
            return self._fail("trade", "ITEM_NOT_FOR_SALE", f"{item} is not sold in town.")
        total = prices[item] * quantity
        if self.state.gold < total:
            return self._fail("trade", "NOT_ENOUGH_GOLD", f"{item} x{quantity} costs {total} Gold.")
        energy_cost = ACTION_ENERGY_COSTS["trade"]
        if not self._has_energy(energy_cost):
            return self._fail("trade", "NOT_ENOUGH_ENERGY", "Not enough Energy to trade.")
        self.state.gold -= total
        self._add_item(item, quantity)
        self._advance(energy_cost)
        return self._ok(
            "trade",
            f"Bought {quantity} {item} for {total} Gold.",
            {item: f"+{quantity}", "gold": f"-{total}", "energy": f"-{energy_cost}"},
        )

    def _sell(self, item: str, quantity: int) -> ActionResult:
        if item not in SELL_PRICES:
            return self._fail("trade", "ITEM_NOT_SELLABLE", f"{item} cannot be sold.")
        if self.state.inventory.get(item, 0) < quantity:
            return self._fail("trade", "INSUFFICIENT_ITEMS", f"You do not have {quantity} {item}.")
        energy_cost = ACTION_ENERGY_COSTS["trade"]
        if not self._has_energy(energy_cost):
            return self._fail("trade", "NOT_ENOUGH_ENERGY", "Not enough Energy to trade.")
        total = SELL_PRICES[item] * quantity
        self._remove_item(item, quantity)
        self.state.gold += total
        self._advance(energy_cost)
        return self._ok(
            "trade",
            f"Sold {quantity} {item} for {total} Gold.",
            {item: f"-{quantity}", "gold": f"+{total}", "energy": f"-{energy_cost}"},
        )

    def _advance(self, energy: int) -> None:
        self._increment_step()
        self.state.energy -= energy
        if self._check_goal():
            return
        if self.state.energy <= 0:
            self._end_day(reason="exhausted")

    def _end_day(self, reason: str) -> None:
        del reason
        self._settle_crops()

        if self.state.day >= min(self.state.goal.get("deadline_day", MAX_DAY), MAX_DAY):
            self.state.done = True
            self.state.success = self._goal_met()
            return

        self.state.day += 1
        self.state.location = "farm"
        self.state.world_state["pending_enemy"] = None

        self.state.energy = 100
        self._reset_daily_farm_flags()
        self.state.weather_today = self.state.weather_tomorrow
        self.state.weather_tomorrow = self._roll_weather()
        self._roll_daily_event()
        self._apply_auto_water()
        self._check_goal()

    def _settle_crops(self) -> None:
        for plot in self.state.farm:
            if plot.crop is None or plot.diseased:
                continue
            if plot.watered or self._weather_waters():
                spec = CROPS[plot.crop]
                plot.growth = min(spec.growth_days, plot.growth + 1)

    def _roll_daily_event(self) -> None:
        self.state.world_state["event_today"] = None
        self.state.world_state["merchant_discount"] = None
        for plot in self.state.farm:
            plot.diseased = False
        if self.rng.random() > DAILY_EVENT_CHANCE:
            return

        event_type = self.rng.choice(sorted(EVENT_TYPES))
        self.state.world_state["event_today"] = event_type
        if event_type == "merchant":
            item = self.rng.choice(MERCHANT_DISCOUNT_ITEMS)
            self.state.world_state["merchant_discount"] = {
                "item": item,
                "multiplier": DISCOUNT_MULTIPLIER,
            }
        elif event_type == "crop_disease":
            planted = [plot for plot in self.state.farm if plot.crop is not None]
            if planted:
                self.rng.choice(planted).diseased = True

    def _apply_auto_water(self) -> None:
        if not self._weather_waters():
            return
        for plot in self.state.farm:
            if not plot.empty:
                plot.watered = True

    def _reset_daily_farm_flags(self) -> None:
        for plot in self.state.farm:
            plot.watered = plot.sprinkler
            plot.diseased = False

    def _weather_waters(self) -> bool:
        return is_auto_water_weather(self.state.weather_today)

    def _mine_is_closed(self) -> bool:
        return is_mine_closed(
            self.state.weather_today,
            self.state.world_state["event_today"],
        )

    def _current_buy_prices(self) -> dict[str, int]:
        prices = dict(BUY_PRICES)
        discount = self.state.world_state["merchant_discount"]
        if discount is not None:
            item = discount["item"]
            prices[item] = int(prices[item] * discount["multiplier"])
        return prices

    def _mine_drops(self, mine_level: int) -> dict[str, int]:
        rich = self.state.world_state["event_today"] == "rich_ore"
        multiplier = 2 if rich else 1
        if mine_level <= 1:
            drops = {"stone": self.rng.randint(1, 3), "copper": self.rng.randint(0, 1)}
        elif mine_level == 2:
            drops = {"copper": self.rng.randint(1, 2), "iron": self.rng.randint(0, 2)}
        else:
            drops = {"iron": self.rng.randint(1, 3), "crystal": self.rng.randint(0, 1)}
        return {item: quantity * multiplier for item, quantity in drops.items() if quantity > 0}

    def _advance_mine_progress(self, mine_level: int) -> None:
        if mine_level >= 3:
            return
        progress = self.state.world_state["mine_progress"]
        progress[mine_level] = progress.get(mine_level, 0) + 1
        if mine_level == 1 and progress[1] >= 3:
            self.state.world_state["mine_level"] = 2
        elif mine_level == 2 and progress[2] >= 5:
            self.state.world_state["mine_level"] = 3

    def _maybe_create_mine_encounter(self, mine_level: int) -> str | None:
        encounter = None
        if mine_level == 2 and self.rng.random() < 0.25:
            encounter = "goblin"
        elif mine_level >= 3 and not self.state.inventory.get("guardian_gem"):
            if self.state.inventory.get("ancient_key", 0) > 0:
                encounter = "guardian"
            elif self.rng.random() < 0.20:
                encounter = "goblin"
        self.state.world_state["pending_enemy"] = encounter
        return encounter

    def _apply_craft_output(self, item: str, output_kind: str) -> None:
        if output_kind == "equipment":
            self.state.equipment[item] = True
        elif output_kind == "farm_upgrade":
            sprinkler_plot = self._select_plot_without_sprinkler()
            if sprinkler_plot is not None:
                sprinkler_plot.sprinkler = True
                if not sprinkler_plot.empty:
                    sprinkler_plot.watered = True
            self._add_item(item, 1)
        else:
            self._add_item(item, 1)

    def _select_plot_without_sprinkler(self) -> FarmPlot | None:
        for plot in self.state.farm:
            if not plot.sprinkler:
                return plot
        return None

    def _apply_rewards(self, rewards: dict[str, Any]) -> None:
        if rewards.get("gold"):
            self.state.gold += int(rewards["gold"])
        for item, quantity in rewards.get("items", {}).items():
            self._add_item(item, quantity)

    def _missing_quest_requirements(self, quest: dict[str, Any]) -> dict[str, Any]:
        missing: dict[str, Any] = {}
        items = self._missing_items(quest["requirements"].get("items", {}))
        if items:
            missing["items"] = items
        defeated = {}
        for enemy, required in quest["requirements"].get("defeated", {}).items():
            current = self.state.world_state["defeated"].get(enemy, 0)
            if current < required:
                defeated[enemy] = required - current
        if defeated:
            missing["defeated"] = defeated
        return missing

    def _apply_knockout(self) -> None:
        self.state.hp = 100
        self.state.gold = int(self.state.gold * 0.9)
        self.state.location = "farm"
        self.state.world_state["pending_enemy"] = None
        self._end_day(reason="knockout")

    def _best_weapon(self) -> str:
        if self.state.equipment.get("iron_sword"):
            return "iron_sword"
        if self.state.equipment.get("wooden_sword"):
            return "wooden_sword"
        return "none"

    def _goal_met(self) -> bool:
        return success_condition_met(self.state, self.state.goal["success_condition"])

    def _check_goal(self) -> bool:
        if self._goal_met():
            self.state.done = True
            self.state.success = True
            return True
        return False

    def _ok(self, action: str, observation: str, changes: dict[str, str]) -> ActionResult:
        self._check_goal()
        return self._result(True, action, observation, changes)

    def _fail(self, action: str, code: str, observation: str) -> ActionResult:
        self._increment_step()
        return self._result(False, action, observation, {}, code)

    def _result(
        self,
        success: bool,
        action: str,
        observation: str,
        changes: dict[str, str],
        error_code: str | None = None,
    ) -> ActionResult:
        return ActionResult(
            success=success,
            action=action,
            observation=observation,
            step=self.state.step,
            state_changes=changes,
            events=self._visible_events(),
            error_code=error_code,
        )

    def _visible_events(self) -> list[dict[str, Any]]:
        event_type = self.state.world_state["event_today"]
        if event_type is None:
            return []
        return [{"type": event_type, "details": self.state.world_state["merchant_discount"]}]

    def _increment_step(self) -> None:
        self.state.step += 1

    def _has_energy(self, energy: int) -> bool:
        return self.state.energy >= energy

    def _roll_weather(self) -> str:
        value = self.rng.random()
        cumulative = 0.0
        for weather, weight in WEATHER_WEIGHTS:
            cumulative += weight
            if value <= cumulative:
                return weather
        return "sunny"

    def _visible_inventory(self) -> dict[str, int]:
        return {item: quantity for item, quantity in self.state.inventory.items() if quantity > 0}

    def _visible_farm(self) -> list[dict[str, Any]]:
        rows = []
        for plot in self.state.farm:
            payload = plot.to_dict()
            if plot.crop is not None:
                payload["growth_required"] = CROPS[plot.crop].growth_days
                payload["ready"] = self._is_mature(plot)
            rows.append(payload)
        return rows

    def _target_plots(self, plot: int | str, include_watered: bool = False) -> list[FarmPlot]:
        if plot == "all":
            return [
                farm_plot
                for farm_plot in self.state.farm
                if not farm_plot.empty and (include_watered or not farm_plot.watered)
            ]
        try:
            plot_id = int(plot)
        except (TypeError, ValueError):
            return []
        selected = self._select_plot(plot_id, require_crop=True)
        if selected is None:
            return []
        if selected.watered and not include_watered:
            return []
        return [selected]

    def _plant_target_plots(
        self,
        plot: int | str | None,
        quantity: int | None,
        seed_count: int,
    ) -> list[FarmPlot]:
        empty_plots = [farm_plot for farm_plot in self.state.farm if farm_plot.empty]
        normalized_plot = plot.strip().lower() if isinstance(plot, str) else plot
        if normalized_plot in (None, "all"):
            requested = len(empty_plots) if quantity is None else int(quantity)
            target_count = min(requested, seed_count, len(empty_plots))
            return empty_plots[:target_count]
        selected = self._select_plot(normalized_plot, require_crop=False)
        return [] if selected is None else [selected]

    def _select_plot(self, plot: int | str | None, require_crop: bool) -> FarmPlot | None:
        if plot is None:
            candidates = [farm_plot for farm_plot in self.state.farm if farm_plot.empty]
            return candidates[0] if candidates else None
        try:
            plot_id = int(plot)
        except (TypeError, ValueError):
            return None
        for farm_plot in self.state.farm:
            if farm_plot.plot_id == plot_id:
                if require_crop and farm_plot.crop is None:
                    return None
                return farm_plot
        return None

    def _is_mature(self, plot: FarmPlot) -> bool:
        return plot.crop is not None and plot.growth >= CROPS[plot.crop].growth_days

    def _missing_items(self, requirements: dict[str, int]) -> dict[str, int]:
        missing = {}
        for item, required in requirements.items():
            available = self.state.inventory.get(item, 0)
            if available < required:
                missing[item] = required - available
        return missing

    def _add_item(self, item: str, quantity: int) -> None:
        self.state.inventory[item] = self.state.inventory.get(item, 0) + quantity

    def _remove_item(self, item: str, quantity: int) -> None:
        current = self.state.inventory.get(item, 0)
        remaining = current - quantity
        if remaining > 0:
            self.state.inventory[item] = remaining
        else:
            self.state.inventory.pop(item, None)

    def _record_counter(self, bucket: str, key: str, amount: int) -> None:
        data = self.state.world_state[bucket]
        data[key] = data.get(key, 0) + amount

    def _format_items(self, items: dict[str, int]) -> str:
        return ", ".join(f"{quantity} {item}" for item, quantity in items.items())

    def _normalize(self, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    def _ensure_state_defaults(self) -> None:
        self.state.equipment.setdefault("basic_pickaxe", True)
        if not self.state.available_quests and not self.state.active_quests:
            self.state.available_quests = deepcopy(QUESTS)
