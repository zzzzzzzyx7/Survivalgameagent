"""LLM-backed tool decision agent."""

from __future__ import annotations

import json

from app.agents.action_policy import Decision
from app.config import settings
from app.environment.energy import ACTION_ENERGY_COSTS
from app.models.llm import ChatModel, get_llm
from app.skills import FIRST_STAGE_SKILLS
from app.tools import MVP_TOOLS

ALLOWED_TOOLS = {*MVP_TOOLS, "stop"}
MAX_DAY_PLAN_ACTIONS = 8

TOOL_ARGUMENTS = {
    "move": {"location": "farm | town | forest | mine | river | guild"},
    "trade": {"action": "buy | sell", "item": "item name", "quantity": "positive integer"},
    "accept_quest": {"quest_id": "Q_WOOD_8 | Q_POTATO_3 | Q_GOBLIN_2 | Q_BIG_FISH_2"},
    "submit_quest": {"quest_id": "Q_WOOD_8 | Q_POTATO_3 | Q_GOBLIN_2 | Q_BIG_FISH_2"},
    "forage": {"resource": "wood | berry | herb | wild_flower"},
    "craft": {"item": "wooden_sword | iron_sword | potion | sprinkler | iron_pickaxe"},
    "rest": {},
    "water": {"plot": "all or plot id"},
    "harvest": {"plot": "all or plot id"},
    "plant": {
        "crop": "turnip | potato | tomato | pumpkin",
        "plot": "optional plot id or all",
        "quantity": "optional positive integer; use when planting multiple plots",
    },
    "mine": {},
    "fish": {},
    "fight": {"action": "fight | escape | use_potion"},
    "inspect": {"target": "state | farm | shop | recipes | weather | quests | goal"},
    "stop": {},
}


class LLMDecisionAgent:
    agent_type = "llm"

    def __init__(
        self,
        llm: ChatModel | None = None,
        *,
        memories: list[str] | None = None,
    ) -> None:
        self.llm = llm or get_llm()
        self.memories = memories or []
        self.history: list[dict[str, object]] = []

    def decide(self, observation: dict[str, object], goal: str) -> Decision:
        response = self.llm.complete_with_metrics(self._prompt(observation, goal))
        decision = _parse_decision(response.text)
        decision["source"] = "llm"
        decision["model"] = response.model_name
        decision["llm_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens,
            "latency_ms": response.latency_ms,
        }
        return decision

    def plan_day(
        self,
        observation: dict[str, object],
        goal: str,
        *,
        recovery_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        response = self.llm.complete_with_metrics(
            self._day_prompt(observation, goal, recovery_context=recovery_context)
        )
        plan = _parse_day_plan(response.text)
        plan["source"] = "llm"
        plan["model"] = response.model_name
        plan["llm_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens,
            "latency_ms": response.latency_ms,
        }
        return plan

    def observe_result(
        self,
        result: dict[str, object],
        observation: dict[str, object],
    ) -> None:
        self.history.append(
            {
                "result": result,
                "state": {
                    "day": observation.get("day"),
                    "step": observation.get("step"),
                    "location": observation.get("location"),
                    "gold": observation.get("gold"),
                    "inventory": observation.get("inventory"),
                    "equipment": observation.get("equipment"),
                    "success": observation.get("success"),
                },
            }
        )
        self.history = self.history[-5:]

    def _prompt(self, observation: dict[str, object], goal: str) -> str:
        payload = {
            "goal": goal,
            "observation": observation,
            "recent_history": self.history,
            "memories": self.memories,
            "available_skills": list(FIRST_STAGE_SKILLS),
            "skills_allow_inspect": settings.skills_allow_inspect,
            "allowed_tools": sorted(MVP_TOOLS),
            "control_decisions": ["stop"],
            "tool_arguments": TOOL_ARGUMENTS,
            "world_hints": [
                "Ancient Key can be bought in town.",
                "Iron Sword requires iron and wood, then craft at farm or town.",
                "Potato economy requires buying seeds, planting, watering, harvesting, then selling in town.",
                "Fishing requires moving to river, then calling fish with no arguments.",
                "Guild quests require moving to guild, accepting a quest, satisfying requirements, then submitting it.",
                "Guardian preparation requires Ancient Key, Iron Sword, mine depth, and combat.",
                "Every frontend text task uses an internal 14-day episode deadline even if the user text omits it.",
            ],
            "response_schema": {
                "tool": "one allowed tool name",
                "args": "object with tool arguments",
                "reason": "short reason",
            },
        }
        return (
            "You are an autonomous game agent. Choose exactly one tool call. "
            "Do not repeat the same inspect call if recent_history already contains its result. "
            "Prefer taking a goal-directed action once enough information is available. "
            "Return only valid JSON, with no markdown fences or prose.\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    def _day_prompt(
        self,
        observation: dict[str, object],
        goal: str,
        *,
        recovery_context: dict[str, object] | None = None,
    ) -> str:
        payload = {
            "goal": goal,
            "observation": observation,
            "recent_history": self.history,
            "memories": self.memories,
            "recovery_context": recovery_context,
            "available_skills": list(FIRST_STAGE_SKILLS),
            "skills_allow_inspect": settings.skills_allow_inspect,
            "allowed_tools": sorted(MVP_TOOLS),
            "control_decisions": ["stop"],
            "tool_arguments": TOOL_ARGUMENTS,
            "day_planning_rules": [
                "Plan only from the current in-game state, not from the start of the episode.",
                "Treat the current day as the planning horizon unless rest or energy depletion ends the day.",
                "There is no clock time and no per-day time limit.",
                "Energy is the only budget that limits how many actions can be done in one day.",
                "Consider day, energy, hp, gold, location, weather, event, inventory, equipment, farm growth, quests, and pending enemy.",
                "Each successful action consumes Energy according to energy_costs; do not plan actions that obviously exceed current Energy.",
                "plant consumes plant Energy once per planted plot. Use quantity or plot=all when planting multiple plots.",
                "water(plot=all) consumes water_per_plot Energy once per dry planted plot.",
                "harvest(plot=all) consumes harvest_per_plot Energy once per mature selected plot.",
                "Food and consumables never restore Energy. Only rest starts the next day with full Energy.",
                "Use consumables only to restore HP.",
                "Put rest as the final action when useful work for the day is finished or Energy is too low.",
                "If recovery_context is present, preserve successful previous steps and revise only the remaining actions.",
                "Do not repeat a failed action from recovery_context unless the new state has changed enough to make it legal.",
                "Use inspect only when the current observation is insufficient for a concrete action.",
                f"Return no more than {MAX_DAY_PLAN_ACTIONS} executable actions.",
            ],
            "energy_costs": ACTION_ENERGY_COSTS,
            "world_hints": [
                "Ancient Key can be bought in town.",
                "Iron Sword requires iron and wood, then craft at farm or town.",
                "Potato economy requires buying seeds, planting, watering, harvesting, then selling in town.",
                "Fishing requires moving to river, then calling fish with no arguments.",
                "Guild quests require moving to guild, accepting a quest, satisfying requirements, then submitting it.",
                "Guardian preparation requires Ancient Key, Iron Sword, mine depth, and combat.",
                "Storm closes Mine and River but waters farm crops.",
                "Every frontend text task uses an internal 14-day episode deadline even if the user text omits it.",
            ],
            "response_schema": {
                "day_objective": "short objective for the current day",
                "reasoning": "brief explanation of Energy/resource tradeoffs",
                "actions": [
                    {
                        "tool": "one allowed tool name or stop",
                        "args": "object with tool arguments",
                        "reason": "short reason for this action",
                    }
                ],
                "final_day_actions": (
                    "A concise final paragraph in Chinese listing today's actions "
                    "in execution order."
                ),
            },
        }
        return (
            "你是一个自主游戏 Agent。你现在必须为“当前游戏日”制定一个动作序列，"
            "而不是只选择一个动作。游戏没有日内时间限制，只有 Energy 预算限制当天行动数量。"
            "你需要综合考虑当前天数、体力、生命、金币、"
            "地点、天气、随机事件、背包、装备、农田、任务和剩余 14 天周期。"
            "如果输入中包含 recovery_context，说明当天已有部分步骤执行成功，但某一步失败；"
            "你必须基于当前状态重新规划当天剩余动作。"
            "只返回有效 JSON，不要使用 markdown，不要输出 JSON 外的说明。\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )


def _parse_decision(text: str) -> Decision:
    payload = json.loads(_strip_code_fence(text))
    if not isinstance(payload, dict):
        raise TypeError("LLM decision must be a JSON object.")
    tool = str(payload.get("tool", "")).strip().lower()
    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Unsupported LLM tool: {tool}")
    args = payload.get("args", {})
    if not isinstance(args, dict):
        raise TypeError("LLM decision args must be a JSON object.")
    reason = str(payload.get("reason", "Selected by LLM."))
    return {"tool": tool, "args": args, "reason": reason}


def _parse_day_plan(text: str) -> dict[str, object]:
    payload = json.loads(_strip_code_fence(text))
    if not isinstance(payload, dict):
        raise TypeError("LLM day plan must be a JSON object.")
    raw_actions = payload.get("actions", [])
    if not isinstance(raw_actions, list):
        raise TypeError("LLM day plan actions must be a JSON array.")

    actions = [_normalize_decision(item) for item in raw_actions[:MAX_DAY_PLAN_ACTIONS]]
    return {
        "day_objective": str(payload.get("day_objective", "Execute useful work today.")),
        "reasoning": str(payload.get("reasoning", "")),
        "actions": actions,
        "final_day_actions": str(payload.get("final_day_actions", _format_actions(actions))),
    }


def _normalize_decision(value: object) -> Decision:
    if not isinstance(value, dict):
        raise TypeError("Each planned action must be a JSON object.")
    tool = str(value.get("tool", "")).strip().lower()
    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Unsupported LLM tool: {tool}")
    args = value.get("args", {})
    if not isinstance(args, dict):
        raise TypeError("LLM planned action args must be a JSON object.")
    reason = str(value.get("reason", "Selected by LLM."))
    return {"tool": tool, "args": args, "reason": reason}


def _format_actions(actions: list[Decision]) -> str:
    if not actions:
        return "今日行动：无可执行动作。"
    chunks = [
        f"{index}. {action['tool']}({json.dumps(action.get('args', {}), ensure_ascii=False)})"
        for index, action in enumerate(actions, start=1)
    ]
    return "今日行动：" + "；".join(chunks)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
