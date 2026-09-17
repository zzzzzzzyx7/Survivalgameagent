"""Episode and benchmark runner interface."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.agents import (
    DirectAgent,
    LLMDecisionAgent,
    PlannerAgent,
    PlannerReplanningAgent,
    ReActAgent,
)
from app.agents.action_policy import (
    Decision,
    craft,
    decide_gold_goal,
    decide_potato_goal,
    forage,
    move,
    trade,
)
from app.agents.reflection import reflect_episode
from app.config import settings
from app.environment import GameState, SurvivalGame
from app.environment.state import ActionResult
from app.memory.episodic_memory import EpisodeLesson
from app.memory.memory_store import MemoryStore

TASK_DIR = Path(__file__).parent / "tasks"
DEFAULT_AGENT_TYPES = ("direct", "react", "planner", "planner_replanning")
DEFAULT_TASK_IDS = ("G01", "G02", "G03", "G04", "G05")
EPISODE_DEADLINE_DAY = 14


def load_task(task_id: str) -> dict[str, Any]:
    normalized = task_id.strip().upper()
    for task_file in TASK_DIR.glob("*.json"):
        task = json.loads(task_file.read_text(encoding="utf-8"))
        if task["task_id"].upper() == normalized:
            return task
    raise ValueError(f"Unknown task_id: {task_id}")


def make_text_task(goal: str, task_id: str = "CUSTOM") -> dict[str, Any]:
    return {
        "task_id": task_id,
        "goal": goal.strip(),
        "max_day": EPISODE_DEADLINE_DAY,
        "success_condition": infer_success_condition(goal),
        "deadline_instruction": (
            "Complete this task before the 14-day episode ends. "
            "Do not require the user task text to include a deadline."
        ),
    }


def make_all_text_tasks(goals: list[str] | tuple[str, ...]) -> dict[str, Any]:
    cleaned_goals = [goal.strip() for goal in goals if goal.strip()]
    goal_text = "\n".join(
        f"{index}. {goal}" for index, goal in enumerate(cleaned_goals, start=1)
    )
    conditions = [infer_success_condition(goal) for goal in cleaned_goals]
    return {
        "task_id": "ALL_TASKS",
        "goal": f"完成以下所有任务：\n{goal_text}",
        "max_day": EPISODE_DEADLINE_DAY,
        "success_condition": "all:" + ";".join(conditions),
        "deadline_instruction": (
            "Complete every listed task before the 14-day episode ends. "
            "Plan across all subtasks instead of optimizing for only one item."
        ),
        "subtasks": cleaned_goals,
    }


def infer_success_condition(goal: str) -> str:
    normalized = goal.lower().replace(" ", "")
    if "guardian" in normalized or "守卫" in normalized:
        return "g05_defeat_guardian"
    if "ancientkey" in normalized or "ancient_key" in normalized or "钥匙" in normalized:
        return "g04_ancient_key_by_day_12"
    if "potato" in normalized or "土豆" in normalized or "马铃薯" in normalized:
        return "g03_harvest_3_potato_by_day_10"
    if "ironsword" in normalized or "iron_sword" in normalized or "铁剑" in normalized:
        return "g02_iron_sword_by_day_8"
    if "900gold" in normalized or "900金币" in normalized or "900金" in normalized:
        return "g01_900_gold_by_day_7"
    return "g05_defeat_guardian"


def make_game(task: dict[str, Any], seed: int) -> SurvivalGame:
    initial = dict(task.get("initial_state", {}))
    goal = {
        "goal_id": task["task_id"],
        "description": task["goal"],
        "deadline_day": task["max_day"],
        "success_condition": task["success_condition"],
    }
    state = GameState(goal=goal)
    for key, value in initial.items():
        if hasattr(state, key):
            setattr(state, key, value)
    return SurvivalGame(initial_state=state, seed=seed)


def make_agent(agent_type: str, memories: list[str] | None = None) -> object | None:
    return _make_agent(agent_type, memories=memories)


def run_game_step(
    agent_type: str,
    agent: object | None,
    task: dict[str, Any],
    game: SurvivalGame,
) -> dict[str, object]:
    state_before = game.observe()
    decision_started = time.perf_counter()
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    try:
        decision = _decide(agent_type, agent, task, state_before, game)
    except Exception as exc:  # noqa: BLE001 - isolate agent/LLM failures per step.
        decision_latency_ms = (time.perf_counter() - decision_started) * 1000
        message = f"Agent decision failed: {type(exc).__name__}: {exc}"
        result = _agent_error_result(game, "decide", message)
        trace_entry = {
            "step": result.step,
            "action": result.action,
            "decision": _agent_error_decision(message),
            "result": result.to_dict(),
            "state_before": state_before,
            "state_after": game.observe(),
            "decision_latency_ms": decision_latency_ms,
        }
        return {
            "stopped": False,
            "invalid": True,
            "decision": trace_entry["decision"],
            "result": result,
            "trace_entry": trace_entry,
            "token_usage": token_usage,
            "decision_latency_ms": decision_latency_ms,
        }

    decision_latency_ms = (time.perf_counter() - decision_started) * 1000
    if decision is None or decision["tool"] == "stop":
        return {
            "stopped": True,
            "invalid": False,
            "decision": decision or {"tool": "stop", "args": {}, "reason": "Agent stopped."},
            "result": None,
            "trace_entry": None,
            "token_usage": token_usage,
            "decision_latency_ms": decision_latency_ms,
        }

    _add_token_usage(token_usage, decision)
    result = _execute_decision(game, decision)
    state_after = game.observe()
    _notify_agent_result(agent, result.to_dict(), state_after)
    trace_entry = {
        "step": result.step,
        "action": result.action,
        "decision": decision,
        "result": result.to_dict(),
        "state_before": state_before,
        "state_after": state_after,
        "decision_latency_ms": decision_latency_ms,
    }
    return {
        "stopped": False,
        "invalid": not result.success,
        "decision": decision,
        "result": result,
        "trace_entry": trace_entry,
        "token_usage": token_usage,
        "decision_latency_ms": decision_latency_ms,
    }


def run_game_day(
    agent_type: str,
    agent: object | None,
    task: dict[str, Any],
    game: SurvivalGame,
    *,
    max_actions: int = 12,
    max_replans: int = 2,
    on_plan: Callable[[dict[str, object]], None] | None = None,
    on_trace_entry: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, object]:
    day_start = int(game.state.day)
    plans: list[dict[str, object]] = []
    trace_entries: list[dict[str, Any]] = []
    executed_steps: list[dict[str, object]] = []
    invalid_actions = 0
    total_actions = 0
    replan_count = 0
    total_decision_latency_ms = 0.0
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    recovery_context: dict[str, object] | None = None
    stopped = False

    while (
        not game.state.done
        and int(game.state.day) == day_start
        and total_actions < max_actions
    ):
        state_at_plan = game.observe()
        plan_started = time.perf_counter()
        try:
            plan = _plan_day(agent_type, agent, task, game, state_at_plan, recovery_context)
        except Exception as exc:  # noqa: BLE001 - isolate LLM planning failures.
            decision_latency_ms = (time.perf_counter() - plan_started) * 1000
            total_decision_latency_ms += decision_latency_ms
            message = f"Agent day plan failed: {type(exc).__name__}: {exc}"
            result = _agent_error_result(game, "plan_day", message)
            trace_entries.append(
                {
                    "step": result.step,
                    "day": day_start,
                    "action": result.action,
                    "decision": _agent_error_decision(message),
                    "result": result.to_dict(),
                    "state_before": state_at_plan,
                    "state_after": game.observe(),
                    "decision_latency_ms": decision_latency_ms,
                    "day_plan": None,
                }
            )
            if on_trace_entry is not None:
                on_trace_entry(trace_entries[-1])
            invalid_actions += 1
            total_actions += 1
            break

        decision_latency_ms = (time.perf_counter() - plan_started) * 1000
        total_decision_latency_ms += decision_latency_ms
        _add_plan_token_usage(token_usage, plan)
        plan_index = len(plans) + 1
        plans.append(plan)
        if on_plan is not None:
            on_plan(plan)

        actions = plan.get("actions", [])
        if not isinstance(actions, list) or not actions:
            stopped = True
            break

        needs_replan = False
        for action_index, decision in enumerate(actions, start=1):
            if game.state.done or int(game.state.day) != day_start or total_actions >= max_actions:
                break
            if not isinstance(decision, dict):
                continue
            if decision.get("tool") == "stop":
                stopped = True
                break

            state_before = game.observe()
            result = _execute_decision(game, decision)
            state_after = game.observe()
            _notify_agent_result(agent, result.to_dict(), state_after)

            total_actions += 1
            if not result.success:
                invalid_actions += 1

            trace_entry = {
                "step": result.step,
                "day": day_start,
                "day_plan_index": plan_index,
                "day_action_index": action_index,
                "action": result.action,
                "decision": decision,
                "result": result.to_dict(),
                "state_before": state_before,
                "state_after": state_after,
                "decision_latency_ms": decision_latency_ms if action_index == 1 else 0.0,
                "day_plan": _visible_day_plan(plan),
            }
            trace_entries.append(trace_entry)
            executed_steps.append(_executed_step_summary(trace_entry))
            if on_trace_entry is not None:
                on_trace_entry(trace_entry)

            if not result.success:
                replan_count += 1
                if replan_count > max_replans:
                    stopped = True
                    break
                recovery_context = {
                    "day": day_start,
                    "executed_steps": executed_steps,
                    "failed_action": decision,
                    "error": result.to_dict(),
                    "current_state": state_after,
                    "previous_plan": _visible_day_plan(plan),
                    "instruction": (
                        "Continue from the current state. Keep successful prior "
                        "steps; revise only the remaining actions for this day."
                    ),
                }
                needs_replan = True
                break

        if stopped or game.state.done or int(game.state.day) != day_start:
            break
        if needs_replan:
            continue
        break

    return {
        "stopped": stopped,
        "invalid": invalid_actions > 0,
        "plans": plans,
        "last_plan": plans[-1] if plans else None,
        "trace_entries": trace_entries,
        "total_actions": total_actions,
        "invalid_actions": invalid_actions,
        "replan_count": replan_count,
        "token_usage": token_usage,
        "decision_latency_ms": total_decision_latency_ms,
        "day": day_start,
    }


def run_episode(
    agent_type: str,
    task_id: str,
    seed: int,
    log_dir: str | Path | None = None,
    memory_path: str | Path | None = None,
    max_steps: int | None = None,
) -> dict[str, object]:
    task = load_task(task_id)
    return run_episode_for_task(
        agent_type,
        task,
        seed,
        log_dir=log_dir,
        memory_path=memory_path,
        max_steps=max_steps,
    )


def run_episode_for_task(
    agent_type: str,
    task: dict[str, Any],
    seed: int,
    log_dir: str | Path | None = None,
    memory_path: str | Path | None = None,
    max_steps: int | None = None,
) -> dict[str, object]:
    game = make_game(task, seed)
    memory_store = MemoryStore(memory_path) if memory_path is not None else None
    retrieved_lessons = (
        memory_store.retrieve(_agent_goal(task), limit=settings.retrieved_memories)
        if memory_store is not None
        else []
    )
    memories = [lesson.lesson for lesson in retrieved_lessons]
    agent = make_agent(agent_type, memories=memories)
    trace: list[dict[str, Any]] = []
    invalid_actions = 0
    total_actions = 0
    total_decision_latency_ms = 0.0
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    episode_step_limit = max_steps or settings.max_episode_steps
    if agent_type.strip().lower() == "llm":
        while not game.state.done and total_actions < episode_step_limit:
            day_result = run_game_day(
                agent_type,
                agent,
                task,
                game,
                max_actions=episode_step_limit - total_actions,
            )
            trace.extend(day_result["trace_entries"])
            total_actions += int(day_result["total_actions"])
            invalid_actions += int(day_result["invalid_actions"])
            total_decision_latency_ms += float(day_result["decision_latency_ms"])
            _merge_token_usage(token_usage, day_result["token_usage"])
            if day_result["stopped"] or not day_result["trace_entries"]:
                break
    while (
        agent_type.strip().lower() != "llm"
        and not game.state.done
        and total_actions < episode_step_limit
    ):
        state_before = game.observe()
        decision_started = time.perf_counter()
        try:
            decision = _decide(agent_type, agent, task, state_before, game)
        except Exception as exc:  # noqa: BLE001 - isolate agent/LLM failures per episode.
            decision_latency_ms = (time.perf_counter() - decision_started) * 1000
            total_decision_latency_ms += decision_latency_ms
            message = f"Agent decision failed: {type(exc).__name__}: {exc}"
            result = _agent_error_result(game, "decide", message)
            total_actions += 1
            invalid_actions += 1
            trace.append(
                {
                    "step": result.step,
                    "action": result.action,
                    "decision": _agent_error_decision(message),
                    "result": result.to_dict(),
                    "state_before": state_before,
                    "state_after": game.observe(),
                    "decision_latency_ms": decision_latency_ms,
                }
            )
            break
        decision_latency_ms = (time.perf_counter() - decision_started) * 1000
        total_decision_latency_ms += decision_latency_ms
        if decision is None or decision["tool"] == "stop":
            break
        _add_token_usage(token_usage, decision)

        result = _execute_decision(game, decision)
        state_after = game.observe()
        _notify_agent_result(agent, result.to_dict(), state_after)
        total_actions += 1
        if not result.success:
            invalid_actions += 1
        trace.append(
            {
                "step": result.step,
                "action": result.action,
                "decision": decision,
                "result": result.to_dict(),
                "state_before": state_before,
                "state_after": state_after,
                "decision_latency_ms": decision_latency_ms,
            }
        )

    final_state = game.observe()
    reflection = reflect_episode(trace, _agent_goal(task), bool(game.state.success))
    estimated_cost_usd = _estimate_cost(token_usage)
    episode = {
        "agent_type": agent_type.strip().lower(),
        "task_id": task["task_id"],
        "seed": seed,
        "success": game.state.success,
        "done": game.state.done,
        "steps": game.state.step,
        "max_steps": episode_step_limit,
        "total_actions": total_actions,
        "invalid_actions": invalid_actions,
        "token_usage": token_usage,
        "decision_latency_ms": total_decision_latency_ms,
        "average_decision_latency_ms": (
            total_decision_latency_ms / total_actions if total_actions else 0.0
        ),
        "estimated_cost_usd": estimated_cost_usd,
        "final_state": final_state,
        "retrieved_memories": [lesson.__dict__ for lesson in retrieved_lessons],
        "reflection": reflection,
        "trace": trace,
    }
    if memory_store is not None:
        _store_reflection(memory_store, episode, reflection)
        episode["memory_path"] = str(memory_store.path)
    if log_dir is not None:
        episode["log_path"] = str(save_episode_log(episode, log_dir))
    return episode


def run_benchmark(
    agent_types: list[str] | tuple[str, ...] = DEFAULT_AGENT_TYPES,
    task_ids: list[str] | tuple[str, ...] = DEFAULT_TASK_IDS,
    seeds: list[int] | tuple[int, ...] = (1, 2, 3),
    log_dir: str | Path | None = None,
    memory_path: str | Path | None = None,
    max_steps: int | None = None,
) -> list[dict[str, object]]:
    episodes = []
    for agent_type in agent_types:
        for task_id in task_ids:
            for seed in seeds:
                episodes.append(
                    run_episode(
                        agent_type,
                        task_id,
                        seed,
                        log_dir=log_dir,
                        memory_path=memory_path,
                        max_steps=max_steps,
                    )
                )
    return episodes


def run_benchmark_tasks(
    agent_types: list[str] | tuple[str, ...],
    tasks: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    seeds: list[int] | tuple[int, ...] = (1, 2, 3),
    log_dir: str | Path | None = None,
    memory_path: str | Path | None = None,
    max_steps: int | None = None,
) -> list[dict[str, object]]:
    episodes = []
    for agent_type in agent_types:
        for task in tasks:
            for seed in seeds:
                episodes.append(
                    run_episode_for_task(
                        agent_type,
                        task,
                        seed,
                        log_dir=log_dir,
                        memory_path=memory_path,
                        max_steps=max_steps,
                    )
                )
    return episodes


def save_episode_log(episode: dict[str, object], log_dir: str | Path = "logs") -> Path:
    output_dir = Path(log_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (
        f"{episode['agent_type']}_{episode['task_id']}_seed_{episode['seed']}.json"
    )
    path.write_text(json.dumps(episode, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _make_agent(agent_type: str, memories: list[str] | None = None) -> object | None:
    normalized = agent_type.strip().lower()
    if normalized == "direct":
        return DirectAgent()
    if normalized == "react":
        return ReActAgent()
    if normalized == "llm":
        return LLMDecisionAgent(memories=memories)
    if normalized == "planner":
        return PlannerAgent(memories=memories)
    if normalized == "planner_replanning":
        return PlannerReplanningAgent(memories=memories)
    if normalized == "scripted":
        return None
    raise ValueError(f"Unknown agent_type: {agent_type}")


def _decide(
    agent_type: str,
    agent: object | None,
    task: dict[str, Any],
    observation: dict[str, object],
    game: SurvivalGame,
) -> Decision | None:
    normalized = agent_type.strip().lower()
    goal = _agent_goal(task)
    if normalized == "scripted":
        return _scripted_action(task["task_id"], game)
    if isinstance(agent, PlannerAgent):
        return agent.run_step(observation, goal)
    if isinstance(agent, (DirectAgent, LLMDecisionAgent, ReActAgent)):
        return agent.decide(observation, goal)
    raise ValueError(f"Unsupported agent_type: {agent_type}")


def _plan_day(
    agent_type: str,
    agent: object | None,
    task: dict[str, Any],
    game: SurvivalGame,
    observation: dict[str, object],
    recovery_context: dict[str, object] | None,
) -> dict[str, object]:
    normalized = agent_type.strip().lower()
    if normalized != "llm":
        decision = _decide(agent_type, agent, task, observation, game)
        return {
            "day_objective": "Single-step compatibility plan.",
            "reasoning": "Wrapped a one-step agent decision as a day plan.",
            "actions": [] if decision is None else [decision],
            "final_day_actions": "今日行动：执行兼容单步动作。",
        }
    planner = getattr(agent, "plan_day", None)
    if not callable(planner):
        raise TypeError("LLM agent does not support day planning.")
    return planner(observation, _agent_goal(task), recovery_context=recovery_context)


def _agent_goal(task: dict[str, Any]) -> str:
    goal = str(task["goal"])
    instruction = str(task.get("deadline_instruction", "")).strip()
    if not instruction:
        return goal
    return f"{goal}\n\nInternal deadline: {instruction}"


def _execute_decision(game: SurvivalGame, decision: Decision) -> ActionResult:
    tool = str(decision["tool"])
    args = decision.get("args", {})
    if not isinstance(args, dict):
        return game.invalid_action(
            tool,
            "INVALID_TOOL_ARGS",
            f"Decision args must be a mapping: {decision}",
        )

    try:
        if tool == "move":
            return game.move(str(args["location"]))
        if tool == "trade":
            return game.trade(str(args["action"]), str(args["item"]), int(args["quantity"]))
        if tool == "accept_quest":
            return game.accept_quest(str(args["quest_id"]))
        if tool == "submit_quest":
            return game.submit_quest(str(args["quest_id"]))
        if tool == "forage":
            return game.forage(str(args["resource"]))
        if tool == "fish":
            return game.fish()
        if tool == "craft":
            return game.craft(str(args["item"]))
        if tool == "rest":
            return game.rest()
        if tool == "use_item":
            return game.use_item(str(args["item"]))
        if tool == "water":
            return game.water(args.get("plot", "all"))
        if tool == "harvest":
            return game.harvest(args.get("plot", "all"))
        if tool == "plant":
            return game.plant(str(args["crop"]), args.get("plot"), args.get("quantity"))
        if tool == "mine":
            return game.mine()
        if tool == "fight":
            return game.fight(str(args.get("action", "fight")))
        if tool == "inspect":
            return game.inspect(str(args.get("target", "state")))
    except (KeyError, TypeError, ValueError) as exc:
        return game.invalid_action(
            tool,
            "INVALID_TOOL_ARGS",
            f"Invalid arguments for {tool}: {exc}",
        )
    return game.invalid_action(tool, "UNKNOWN_TOOL", f"Unknown tool in decision: {tool}")


def _agent_error_result(
    game: SurvivalGame,
    action: str,
    observation: str,
) -> ActionResult:
    return ActionResult(
        success=False,
        action=action,
        observation=observation,
        step=game.state.step,
        state_changes={},
        events=[],
        error_code="AGENT_DECISION_ERROR",
    )


def _agent_error_decision(message: str) -> Decision:
    return {"tool": "error", "args": {}, "reason": message}


def _notify_agent_result(
    agent: object | None,
    result: dict[str, object],
    observation: dict[str, object],
) -> None:
    observer = getattr(agent, "observe_result", None)
    if callable(observer):
        observer(result, observation)


def _add_token_usage(token_usage: dict[str, int], decision: Decision) -> None:
    usage = decision.get("llm_usage", {})
    if not isinstance(usage, dict):
        return
    for key in token_usage:
        token_usage[key] += int(usage.get(key, 0) or 0)


def _add_plan_token_usage(token_usage: dict[str, int], plan: dict[str, object]) -> None:
    usage = plan.get("llm_usage", {})
    if not isinstance(usage, dict):
        return
    for key in token_usage:
        token_usage[key] += int(usage.get(key, 0) or 0)


def _merge_token_usage(token_usage: dict[str, int], incoming: object) -> None:
    if not isinstance(incoming, dict):
        return
    for key in token_usage:
        token_usage[key] += int(incoming.get(key, 0) or 0)


def _visible_day_plan(plan: dict[str, object]) -> dict[str, object]:
    return {
        "day_objective": plan.get("day_objective"),
        "reasoning": plan.get("reasoning"),
        "actions": plan.get("actions", []),
        "final_day_actions": plan.get("final_day_actions"),
    }


def _executed_step_summary(trace_entry: dict[str, Any]) -> dict[str, object]:
    return {
        "step": trace_entry.get("step"),
        "action_index": trace_entry.get("day_action_index"),
        "decision": trace_entry.get("decision"),
        "result": trace_entry.get("result"),
        "state_after": trace_entry.get("state_after"),
    }


def _estimate_cost(token_usage: dict[str, int]) -> float:
    input_cost = token_usage["input_tokens"] / 1_000_000 * settings.llm_input_cost_per_1m
    output_cost = token_usage["output_tokens"] / 1_000_000 * settings.llm_output_cost_per_1m
    return round(input_cost + output_cost, 8)


def _store_reflection(
    memory_store: MemoryStore,
    episode: dict[str, object],
    reflection: dict[str, object],
) -> None:
    lessons = reflection.get("lessons", [])
    if not isinstance(lessons, list):
        return
    tags = reflection.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    episode_id = (
        f"{episode['agent_type']}_{episode['task_id']}_seed_{episode['seed']}"
    )
    for index, lesson in enumerate(lessons, start=1):
        memory_store.add(
            EpisodeLesson(
                episode_id=f"{episode_id}_lesson_{index}",
                goal=str(reflection.get("goal", "")),
                outcome="success" if episode.get("success") else "failed",
                lesson=str(lesson),
                tags=[str(tag) for tag in tags],
            )
        )


def _scripted_action(
    task_id: str,
    game: SurvivalGame,
) -> Decision | None:
    normalized = task_id.upper()
    if normalized == "G01":
        return decide_gold_goal(game.observe())
    if normalized == "G02":
        return _scripted_g02(game)
    if normalized == "G03":
        return decide_potato_goal(game.observe())
    if normalized == "G04":
        return _scripted_g04(game)
    if normalized == "G05":
        return _scripted_g05(game)
    raise ValueError(f"No scripted policy for task_id: {task_id}")


def _scripted_g02(game: SurvivalGame) -> Decision | None:
    if game.state.inventory.get("iron", 0) < 2 and not game.state.equipment.get("iron_sword"):
        if game.state.location != "town":
            return move("town", "Buy Iron for the Iron Sword.")
        return trade(
            "buy",
            "iron",
            2 - game.state.inventory.get("iron", 0),
            "Buy missing Iron for the Iron Sword.",
        )
    if game.state.inventory.get("wood", 0) < 3:
        if game.state.location != "forest":
            return move("forest", "Collect Wood for the Iron Sword.")
        return forage("wood", "Collect Wood for the Iron Sword.")
    if game.state.location != "farm":
        return move("farm", "Craft the Iron Sword at the farm.")
    return craft("iron_sword", "Craft the Iron Sword.")


def _scripted_g04(game: SurvivalGame) -> Decision | None:
    if game.state.inventory.get("ancient_key", 0) > 0:
        return None
    if game.state.location != "town":
        return move("town", "Buy the Ancient Key.")
    return trade("buy", "ancient_key", 1, "Buy the Ancient Key.")


def _scripted_g05(game: SurvivalGame) -> Decision | None:
    if game.state.inventory.get("ancient_key", 0) == 0:
        if game.state.location != "town":
            return move("town", "Buy the Ancient Key for the Guardian path.")
        return trade("buy", "ancient_key", 1, "Buy the Ancient Key.")
    if game.state.inventory.get("wood", 0) < 3 and not game.state.equipment.get("iron_sword"):
        if game.state.location != "forest":
            return move("forest", "Collect Wood for the Iron Sword.")
        return forage("wood", "Collect Wood for the Iron Sword.")
    if (
        game.state.inventory.get("iron", 0) < 2
        or game.state.world_state["mine_level"] < 3
    ) and not game.state.equipment.get("iron_sword"):
        if game.state.location != "mine":
            return move("mine", "Mine until enough Iron and mine level 3 are reached.")
        if game.state.energy < 15:
            return {"tool": "rest", "args": {}, "reason": "Recover Energy before more mining."}
        if game.state.world_state["pending_enemy"] is not None:
            return {"tool": "fight", "args": {"action": "escape"}, "reason": "Avoid side combat."}
        return {"tool": "mine", "args": {}, "reason": "Mine for Iron and deeper access."}
    if not game.state.equipment.get("iron_sword"):
        if game.state.location != "farm":
            return move("farm", "Craft the Iron Sword before fighting Guardian.")
        return craft("iron_sword", "Craft the Iron Sword.")
    if game.state.location != "mine":
        return move("mine", "Return to Mine for Guardian encounter.")
    if game.state.world_state["pending_enemy"] == "guardian":
        return {"tool": "fight", "args": {"action": "fight"}, "reason": "Defeat the Guardian."}
    return {"tool": "mine", "args": {}, "reason": "Mine until the Guardian appears."}
