"""ReAct-style skill-to-tool agent."""

from app.agents.action_policy import Decision
from app.skills import decide_goal_with_skills


class ReActAgent:
    agent_type = "react"

    def decide(self, observation: dict[str, object], goal: str) -> Decision:
        decision = decide_goal_with_skills(observation, goal)
        decision["thought"] = self._reason_about_state(observation, decision)
        return decision

    def _reason_about_state(
        self,
        observation: dict[str, object],
        decision: Decision,
    ) -> str:
        inventory = observation.get("inventory", {})
        equipment = observation.get("equipment", {})
        location = observation.get("location", "unknown")
        return (
            f"At {location}, inventory={inventory}, equipment={equipment}. "
            f"Next tool should be {decision['tool']} because {decision['reason']}"
        )
