"""Shared skill types and helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.action_policy import Decision, inspect, stop
from app.config import settings


@dataclass(frozen=True)
class SkillContext:
    allow_inspect: bool = settings.skills_allow_inspect


def attach_skill(decision: Decision, skill: str) -> Decision:
    decision["skill"] = skill
    return decision


def inspect_or_stop(target: str, reason: str, context: SkillContext, skill: str) -> Decision:
    if context.allow_inspect:
        return attach_skill(inspect(target, reason), skill)
    return attach_skill(stop(f"Skill inspect is disabled: {reason}"), skill)


def mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
