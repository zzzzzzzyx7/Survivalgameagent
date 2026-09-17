"""Simple JSON-backed memory store."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.config import settings
from app.memory.episodic_memory import EpisodeLesson


class MemoryStore:
    def __init__(
        self,
        path: str | Path = "data/memory.json",
        max_memories: int = settings.max_memories,
    ) -> None:
        self.path = Path(path)
        self.max_memories = max_memories

    def add(self, lesson: EpisodeLesson) -> None:
        lessons = self._load()
        lessons.append(lesson)
        lessons = lessons[-self.max_memories :]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in lessons]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def retrieve(self, goal: str, limit: int = 3) -> list[EpisodeLesson]:
        query_terms = _terms(goal)
        scored = []
        for lesson in self._load():
            haystack = _terms(" ".join([lesson.goal, lesson.lesson, *lesson.tags]))
            score = len(query_terms & haystack)
            scored.append((score, lesson))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [lesson for score, lesson in scored[:limit] if score > 0]

    def _load(self) -> list[EpisodeLesson]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [EpisodeLesson(**item) for item in payload]


def _terms(text: str) -> set[str]:
    return {
        term.strip(".,:;!?()[]{}").lower()
        for term in text.split()
        if term.strip(".,:;!?()[]{}")
    }

