"""Evaluation metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from evaluation.failure_analysis import categorize_failure


def success_rate(episodes: list[dict[str, object]]) -> float:
    if not episodes:
        return 0.0
    return sum(1 for episode in episodes if episode.get("success")) / len(episodes)


def invalid_action_rate(episodes: list[dict[str, object]]) -> float:
    invalid = sum(int(episode.get("invalid_actions", 0)) for episode in episodes)
    total = sum(int(episode.get("total_actions", 0)) for episode in episodes)
    return invalid / total if total else 0.0


def average_steps(episodes: list[dict[str, object]], successes_only: bool = True) -> float:
    selected = [
        episode
        for episode in episodes
        if not successes_only or bool(episode.get("success"))
    ]
    if not selected:
        return 0.0
    return sum(int(episode.get("steps", 0)) for episode in selected) / len(selected)


def failure_counts(episodes: list[dict[str, object]]) -> dict[str, int]:
    counter = Counter(
        categorize_failure(episode)
        for episode in episodes
        if not bool(episode.get("success"))
    )
    return dict(counter)


def total_token_usage(episodes: list[dict[str, object]]) -> dict[str, int]:
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for episode in episodes:
        episode_usage = episode.get("token_usage", {})
        if not isinstance(episode_usage, dict):
            continue
        for key in usage:
            usage[key] += int(episode_usage.get(key, 0) or 0)
    return usage


def estimated_cost(episodes: list[dict[str, object]]) -> float:
    return round(sum(float(episode.get("estimated_cost_usd", 0.0)) for episode in episodes), 8)


def average_decision_latency_ms(episodes: list[dict[str, object]]) -> float:
    actions = sum(int(episode.get("total_actions", 0)) for episode in episodes)
    if not actions:
        return 0.0
    total_latency = sum(float(episode.get("decision_latency_ms", 0.0)) for episode in episodes)
    return total_latency / actions


def summarize_episodes(episodes: list[dict[str, object]]) -> dict[str, Any]:
    token_usage = total_token_usage(episodes)
    return {
        "episodes": len(episodes),
        "success_rate": success_rate(episodes),
        "average_steps": average_steps(episodes),
        "invalid_action_rate": invalid_action_rate(episodes),
        "average_decision_latency_ms": average_decision_latency_ms(episodes),
        "token_usage": token_usage,
        "average_tokens_per_episode": token_usage["total_tokens"] / len(episodes)
        if episodes
        else 0.0,
        "estimated_cost_usd": estimated_cost(episodes),
        "failure_counts": failure_counts(episodes),
    }


def group_summary(episodes: list[dict[str, object]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for episode in episodes:
        key = (str(episode.get("agent_type")), str(episode.get("task_id")))
        groups.setdefault(key, []).append(episode)

    rows = []
    for (agent_type, task_id), group in sorted(groups.items()):
        summary = summarize_episodes(group)
        summary.update({"agent_type": agent_type, "task_id": task_id})
        rows.append(summary)
    return rows
