"""Episodic memory data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpisodeLesson:
    episode_id: str
    goal: str
    outcome: str
    lesson: str
    tags: list[str]
