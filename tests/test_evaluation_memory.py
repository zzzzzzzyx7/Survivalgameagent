from pathlib import Path

from app.agents.llm_agent import LLMDecisionAgent
from app.agents.reflection import reflect_episode
from app.config import settings
from app.memory.episodic_memory import EpisodeLesson
from app.memory.memory_store import MemoryStore
from app.models.llm import LLMResponse, LLMUsage, OpenAIChatModel, get_llm
from evaluation.metrics import group_summary, summarize_episodes
from evaluation.runner import (
    infer_success_condition,
    load_task,
    make_agent,
    make_all_text_tasks,
    make_game,
    make_text_task,
    run_benchmark,
    run_episode,
    run_game_day,
    run_game_step,
)
from frontend.game_view import _chain_rows_from_trace
from frontend.task_inputs import DEFAULT_TASK_TEXTS
from frontend.trace_view import (
    action_chain_rows_from_entries,
    find_episode_logs,
    group_trace_by_day,
)


def test_run_benchmark_groups_agents_tasks_and_seeds(tmp_path: Path) -> None:
    episodes = run_benchmark(
        agent_types=("direct", "planner"),
        task_ids=("G02", "G04"),
        seeds=(1, 2),
        log_dir=tmp_path,
    )

    assert len(episodes) == 8
    assert all(episode["success"] for episode in episodes)
    assert len(list(tmp_path.glob("*.json"))) == 8

    rows = group_summary(episodes)
    assert len(rows) == 4
    assert all(row["success_rate"] == 1.0 for row in rows)


def test_run_episode_respects_max_steps_override() -> None:
    episode = run_episode("direct", "G01", seed=1, max_steps=1)

    assert episode["max_steps"] == 1
    assert episode["total_actions"] == 1
    assert not episode["success"]


def test_run_game_step_advances_live_episode_state() -> None:
    task = load_task("G02")
    game = make_game(task, seed=1)
    agent = make_agent("direct")

    step = run_game_step("direct", agent, task, game)

    assert not step["stopped"]
    assert step["trace_entry"]["decision"]["tool"] == "move"
    assert step["trace_entry"]["state_after"]["step"] == 1
    assert game.state.step == 1


def test_text_task_defaults_and_chinese_goal_inference() -> None:
    assert DEFAULT_TASK_TEXTS == ["拥有至少 900 金币", "制作一把铁剑"]
    assert infer_success_condition(DEFAULT_TASK_TEXTS[0]) == "g01_900_gold_by_day_7"
    assert infer_success_condition(DEFAULT_TASK_TEXTS[1]) == "g02_iron_sword_by_day_8"

    task = make_text_task(DEFAULT_TASK_TEXTS[1], "TASK_2")

    assert task["task_id"] == "TASK_2"
    assert task["goal"] == "制作一把铁剑"
    assert task["max_day"] == 14
    assert "14-day episode" in task["deadline_instruction"]


def test_all_text_tasks_builds_composite_goal() -> None:
    task = make_all_text_tasks(DEFAULT_TASK_TEXTS)

    assert task["task_id"] == "ALL_TASKS"
    assert "完成以下所有任务" in task["goal"]
    assert task["success_condition"] == "all:g01_900_gold_by_day_7;g02_iron_sword_by_day_8"
    assert task["subtasks"] == DEFAULT_TASK_TEXTS


def test_runner_records_agent_decision_errors(monkeypatch) -> None:
    class BrokenAgent:
        def decide(self, observation, goal):
            raise RuntimeError("boom")

    monkeypatch.setattr("evaluation.runner._make_agent", lambda agent_type, memories=None: BrokenAgent())

    episode = run_episode("direct", "G04", seed=1)

    assert not episode["success"]
    assert episode["invalid_actions"] == 1
    assert episode["trace"][0]["result"]["error_code"] == "AGENT_DECISION_ERROR"
    assert episode["steps"] == 0
    assert episode["trace"][0]["state_after"]["step"] == 0


def test_trace_view_finds_nested_episode_logs(tmp_path: Path) -> None:
    nested = tmp_path / "benchmark"
    nested.mkdir()
    episode_log = nested / "direct_G02_seed_1.json"
    episode_log.write_text("{}", encoding="utf-8")

    assert find_episode_logs(tmp_path) == [episode_log]


def test_live_action_chain_displays_energy_delta() -> None:
    rows = _chain_rows_from_trace(
        {
            "trace_entries": [
                {
                    "decision": {
                        "tool": "plant",
                        "args": {"crop": "potato", "quantity": 9},
                        "reason": "种植九块地。",
                    },
                    "result": {
                        "success": True,
                        "observation": "Planted potato in plot(s): 1, 2, 3.",
                        "state_changes": {"energy": "-45"},
                    },
                    "state_after": {"location": "farm", "gold": 185, "energy": 45},
                }
            ]
        }
    )

    assert rows[0]["体力变化"] == "-45"
    assert rows[0]["体力"] == 45


def test_trace_replay_groups_action_tables_by_day() -> None:
    trace = [
        {
            "day": 1,
            "decision": {"tool": "rest", "args": {}, "reason": "结束第一天。"},
            "result": {"success": True, "state_changes": {"energy": "100"}},
            "state_after": {"day": 2, "location": "farm", "gold": 185, "energy": 100},
        },
        {
            "day": 2,
            "decision": {"tool": "water", "args": {"plot": "all"}, "reason": "浇水。"},
            "result": {"success": True, "state_changes": {"energy": "-27"}},
            "state_after": {"day": 2, "location": "farm", "gold": 185, "energy": 73},
        },
    ]

    groups = group_trace_by_day(trace)
    rows = action_chain_rows_from_entries(trace)

    assert [day for day, _entries in groups] == [1, 2]
    assert rows[0]["Day"] == 1
    assert rows[1]["Day"] == 2
    assert rows[1]["体力变化"] == "-27"


def test_episode_summary_includes_core_metrics() -> None:
    episodes = [
        {"success": True, "steps": 4, "invalid_actions": 0, "total_actions": 4, "trace": []},
        {
            "success": False,
            "steps": 5,
            "invalid_actions": 1,
            "total_actions": 5,
            "trace": [],
            "token_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "decision_latency_ms": 18.0,
            "estimated_cost_usd": 0.01,
        },
    ]

    summary = summarize_episodes(episodes)

    assert summary["episodes"] == 2
    assert summary["success_rate"] == 0.5
    assert summary["average_steps"] == 4.0
    assert summary["invalid_action_rate"] == 1 / 9
    assert summary["token_usage"]["total_tokens"] == 15
    assert summary["average_tokens_per_episode"] == 7.5
    assert summary["average_decision_latency_ms"] == 2.0
    assert summary["estimated_cost_usd"] == 0.01


def test_memory_store_persists_and_retrieves_relevant_lessons(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.json", max_memories=3)
    lesson = EpisodeLesson(
        episode_id="episode-1",
        goal="Defeat Guardian",
        outcome="failed",
        lesson="Prepare an Iron Sword before Guardian combat.",
        tags=["guardian", "combat"],
    )

    store.add(lesson)

    assert store.retrieve("Guardian combat")[0] == lesson
    assert store.retrieve("Potato harvest") == []


def test_runner_retrieves_and_stores_episode_memory(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.json"
    store = MemoryStore(memory_path)
    store.add(
        EpisodeLesson(
            episode_id="old-episode",
            goal="Craft Iron Sword",
            outcome="success",
            lesson="Buy or mine Iron, gather Wood, then craft at Farm or Town.",
            tags=["iron", "sword"],
        )
    )

    episode = run_episode("planner", "G02", seed=2, memory_path=memory_path)

    assert episode["retrieved_memories"]
    assert episode["trace"][0]["decision"]["memories"]
    assert episode["reflection"]["lessons"]
    assert len(MemoryStore(memory_path).retrieve("Iron Sword", limit=10)) >= 2


def test_reflection_generates_success_lesson_from_episode() -> None:
    episode = run_episode("direct", "G02", seed=2)

    reflection = reflect_episode(
        episode["trace"],
        "Craft an Iron Sword by the end of the 14-day episode.",
        bool(episode["success"]),
    )

    assert reflection["success"]
    assert reflection["failure_reason"] == "success"
    assert reflection["lessons"]


def test_get_llm_returns_openai_chat_model() -> None:
    model = get_llm("gpt-5-mini")

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "gpt-5-mini"


def test_get_llm_defaults_to_deepseek_flash() -> None:
    model = get_llm()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "deepseek-v4-flash"
    assert model.base_url == "https://api.deepseek.com"
    assert model.timeout_seconds == settings.llm_timeout_seconds
    assert model.max_retries == settings.llm_max_retries


def test_llm_agent_parses_structured_tool_decision() -> None:
    agent = LLMDecisionAgent(FakeChatModel())

    decision = agent.decide({"location": "farm"}, "Craft an Iron Sword.")

    assert decision["tool"] == "move"
    assert decision["args"] == {"location": "town"}
    assert decision["model"] == "fake-model"
    assert decision["llm_usage"]["total_tokens"] == 5


def test_llm_agent_parses_day_plan() -> None:
    agent = LLMDecisionAgent(FakeDayPlanModel())

    plan = agent.plan_day({"location": "farm", "day": 1}, "Craft an Iron Sword.")

    assert plan["day_objective"] == "Collect sword materials."
    assert plan["actions"][0]["tool"] == "move"
    assert plan["actions"][0]["args"] == {"location": "town"}
    assert "今日行动" in plan["final_day_actions"]


def test_run_game_day_replans_after_midday_action_error() -> None:
    task = make_text_task("制作一把铁剑", "TASK_2")
    game = make_game(task, seed=1)
    model = FakeReplanningDayModel()
    agent = LLMDecisionAgent(model)

    result = run_game_day("llm", agent, task, game)

    assert result["total_actions"] == 2
    assert result["invalid_actions"] == 1
    assert result["replan_count"] == 1
    assert len(result["plans"]) == 2
    assert result["trace_entries"][0]["result"]["error_code"] == "WRONG_LOCATION"
    assert result["trace_entries"][1]["decision"]["tool"] == "move"
    assert game.state.location == "forest"
    assert len(model.prompts) == 2
    assert "recovery_context" in model.prompts[1]
    assert "WRONG_LOCATION" in model.prompts[1]


def test_llm_agent_prompt_includes_recent_history() -> None:
    model = FakeChatModel()
    agent = LLMDecisionAgent(model)

    agent.observe_result(
        {"success": True, "action": "inspect", "observation": "shop"},
        {"location": "town", "gold": 500, "inventory": {}, "equipment": {}, "success": False},
    )
    agent.decide({"location": "town"}, "Buy Ancient Key.")

    assert "recent_history" in model.last_prompt
    assert "shop" in model.last_prompt


class FakeChatModel:
    model_name = "fake-model"
    last_prompt = ""

    def complete(self, prompt: str) -> str:
        return self.complete_with_metrics(prompt).text

    def complete_with_metrics(self, prompt: str) -> LLMResponse:
        self.last_prompt = prompt
        assert "allowed_tools" in prompt
        return LLMResponse(
            text='{"tool": "move", "args": {"location": "town"}, "reason": "Need shop."}',
            model_name=self.model_name,
            usage=LLMUsage(input_tokens=3, output_tokens=2, total_tokens=5),
            latency_ms=12.0,
        )


class FakeDayPlanModel:
    model_name = "fake-model"

    def complete(self, prompt: str) -> str:
        return self.complete_with_metrics(prompt).text

    def complete_with_metrics(self, prompt: str) -> LLMResponse:
        assert "day_planning_rules" in prompt
        assert "energy_costs" in prompt
        assert "There is no clock time" in prompt
        return LLMResponse(
            text=(
                '{"day_objective": "Collect sword materials.", '
                '"reasoning": "Move to town first because iron can be bought there.", '
                '"actions": ['
                '{"tool": "move", "args": {"location": "town"}, "reason": "Reach shop."}'
                '], '
                '"final_day_actions": "今日行动：前往城镇购买材料。"}'
            ),
            model_name=self.model_name,
            usage=LLMUsage(input_tokens=4, output_tokens=3, total_tokens=7),
            latency_ms=15.0,
        )


class FakeReplanningDayModel:
    model_name = "fake-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        return self.complete_with_metrics(prompt).text

    def complete_with_metrics(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            text = (
                '{"day_objective": "Try gathering wood.", '
                '"reasoning": "The plan intentionally starts with an illegal action.", '
                '"actions": ['
                '{"tool": "forage", "args": {"resource": "wood"}, "reason": "Gather wood."}'
                '], '
                '"final_day_actions": "今日行动：采集木材。"}'
            )
        else:
            text = (
                '{"day_objective": "Recover from the failed action.", '
                '"reasoning": "Move to the forest before foraging.", '
                '"actions": ['
                '{"tool": "move", "args": {"location": "forest"}, "reason": "Reach forest."}'
                '], '
                '"final_day_actions": "今日行动：先移动到森林。"}'
            )
        return LLMResponse(
            text=text,
            model_name=self.model_name,
            usage=LLMUsage(input_tokens=4, output_tokens=3, total_tokens=7),
            latency_ms=15.0,
        )
