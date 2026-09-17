"""Shared agent state for graph-style planning agents."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    goal: str
    game_state: dict[str, Any]
    current_plan: list[str]
    completed_subgoals: list[str]
    current_subgoal: str
    tool_history: list[dict[str, Any]]
    observations: list[str]
    memories: list[str]
    reflections: list[str]
    last_result: dict[str, Any]
    decision: dict[str, Any]
    enable_replanning: bool
    step_count: int
    replan_count: int
    status: Literal["running", "success", "failed"]
