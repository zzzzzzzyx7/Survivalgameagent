"""Episode reflection helpers."""

from __future__ import annotations

from typing import Any

from evaluation.failure_analysis import categorize_failure


def reflect_episode(trace: list[dict[str, object]], goal: str, success: bool) -> dict[str, object]:
    episode = {
        "success": success,
        "trace": trace,
        "invalid_actions": sum(
            1
            for step in trace
            if _mapping(step.get("result")).get("success") is False
        ),
        "final_state": _mapping(trace[-1].get("state_after")) if trace else {},
    }
    failure_reason = "success" if success else categorize_failure(episode)
    lessons = _success_lessons(goal) if success else _failure_lessons(failure_reason)
    return {
        "goal": goal,
        "success": success,
        "failure_reason": failure_reason,
        "lessons": lessons,
        "tags": sorted({failure_reason, *_terms(goal)}),
    }


def _success_lessons(goal: str) -> list[str]:
    if "guardian" in goal.lower():
        return ["Prepare Ancient Key and Iron Sword before searching for the Guardian."]
    if "iron sword" in goal.lower():
        return ["Buy or mine Iron, gather Wood, then craft at Farm or Town."]
    if "potato" in goal.lower():
        return ["Plant Potato early enough to water it for five growth days."]
    return ["The selected plan completed the goal."]


def _failure_lessons(failure_reason: str) -> list[str]:
    lessons = {
        "failure_to_replan": "When a location is closed, switch to an alternative resource route.",
        "resource_mismanagement": "Check Energy, Gold, and required materials before committing.",
        "premature_goal_attempt": "Do not attempt final encounters before key prerequisites are ready.",
        "combat_failure": "Improve HP, equipment, or consumables before combat.",
        "looping": "Detect repeated actions and choose a different tool.",
        "planning_error": "Create a concrete subgoal plan before acting.",
    }
    return [lessons.get(failure_reason, "Inspect the final state and choose a safer plan.")]


def _terms(text: str) -> set[str]:
    return {
        term.strip(".,:;!?()[]{}").lower()
        for term in text.split()
        if term.strip(".,:;!?()[]{}")
    }


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

