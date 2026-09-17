"""Baseline direct skill-to-tool agent."""

from app.agents.action_policy import Decision
from app.skills import decide_goal_with_skills


class DirectAgent:
    agent_type = "direct"

    def decide(self, observation: dict[str, object], goal: str) -> Decision:
        return decide_goal_with_skills(observation, goal)
