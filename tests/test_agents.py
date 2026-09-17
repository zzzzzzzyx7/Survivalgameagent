from app.agents import DirectAgent, PlannerAgent, PlannerReplanningAgent, ReActAgent
from app.agents.graph import build_agent_graph, run_agent_graph
from app.agents.replanner import revise_plan, should_replan
from evaluation.runner import run_episode

G02_GOAL = "Craft an Iron Sword by the end of the 14-day episode."


def test_direct_agent_selects_tool_from_observation() -> None:
    decision = DirectAgent().decide(
        {
            "location": "farm",
            "inventory": {},
            "equipment": {},
        },
        G02_GOAL,
    )

    assert decision["tool"] == "move"
    assert decision["args"] == {"location": "town"}
    assert decision["skill"] == "Resource Acquisition"


def test_direct_agent_understands_chinese_text_goal() -> None:
    decision = DirectAgent().decide(
        {
            "location": "farm",
            "inventory": {},
            "equipment": {},
        },
        "制作一把铁剑",
    )

    assert decision["tool"] == "move"
    assert decision["args"] == {"location": "town"}
    assert decision["skill"] == "Resource Acquisition"


def test_react_agent_includes_reasoning_with_action() -> None:
    decision = ReActAgent().decide(
        {
            "location": "town",
            "inventory": {},
            "equipment": {},
        },
        G02_GOAL,
    )

    assert decision["tool"] == "trade"
    assert decision["args"]["item"] == "iron"
    assert "thought" in decision


def test_planner_agent_generates_and_executes_plan() -> None:
    agent = PlannerAgent()
    decision = agent.run_step(
        {
            "location": "farm",
            "inventory": {},
            "equipment": {},
        },
        G02_GOAL,
    )

    assert decision["tool"] == "move"
    assert decision["current_subgoal"] == "obtain_iron"
    assert decision["plan"] == ["obtain_iron", "obtain_wood", "craft_iron_sword"]


def test_planner_agent_does_not_replan_by_default() -> None:
    agent = PlannerAgent()
    agent.current_plan = ["mine_iron_and_depth", "craft_iron_sword"]
    agent.current_subgoal = "mine_iron_and_depth"

    agent.observe_result(
        {"success": False, "error_code": "LOCATION_CLOSED"},
        {"weather_today": "storm", "event_today": None},
    )

    assert agent.replan_count == 0
    assert agent.current_plan == ["mine_iron_and_depth", "craft_iron_sword"]


def test_planner_replanning_agent_revises_plan() -> None:
    agent = PlannerReplanningAgent()
    agent.current_plan = ["mine_iron_and_depth", "craft_iron_sword"]
    agent.current_subgoal = "mine_iron_and_depth"

    agent.observe_result(
        {"success": False, "error_code": "LOCATION_CLOSED"},
        {"weather_today": "storm", "event_today": None},
    )
    agent.run_step(
        {"location": "farm", "inventory": {}, "equipment": {}, "weather_today": "storm"},
        "Defeat the Guardian.",
    )

    assert agent.replan_count == 1
    assert agent.current_plan == [
        "fallback_resource_route",
        "mine_iron_and_depth",
        "craft_iron_sword",
    ]


def test_direct_react_and_planner_complete_g02_in_runner() -> None:
    for agent_type in ("direct", "react", "planner"):
        episode = run_episode(agent_type, "G02", seed=2)

        assert episode["success"], agent_type
        assert episode["done"], agent_type
        assert episode["invalid_actions"] == 0, agent_type
        assert episode["final_state"]["equipment"]["iron_sword"], agent_type
        assert episode["trace"][0]["decision"]["tool"] == "move"


def test_direct_react_and_planner_complete_all_benchmark_tasks() -> None:
    for agent_type in ("direct", "react", "planner", "planner_replanning"):
        for task_id in ("G01", "G02", "G03", "G04", "G05"):
            episode = run_episode(agent_type, task_id, seed=2)

            assert episode["success"], (agent_type, task_id)
            assert episode["invalid_actions"] == 0, (agent_type, task_id)


def test_planner_runner_trace_exposes_plan_state() -> None:
    episode = run_episode("planner", "G02", seed=2)

    first_decision = episode["trace"][0]["decision"]

    assert first_decision["current_subgoal"] == "obtain_iron"
    assert first_decision["plan"] == ["obtain_iron", "obtain_wood", "craft_iron_sword"]


def test_replanner_detects_closed_location_and_revises_plan() -> None:
    agent_state = {
        "game_state": {"weather_today": "storm", "event_today": None},
        "current_plan": ["obtain_wood", "mine_iron_and_depth", "craft_iron_sword"],
        "current_subgoal": "mine_iron_and_depth",
        "last_result": {"success": False, "error_code": "LOCATION_CLOSED"},
    }

    assert should_replan(agent_state)
    assert revise_plan(agent_state) == [
        "obtain_wood",
        "fallback_resource_route",
        "mine_iron_and_depth",
        "craft_iron_sword",
    ]


def test_build_agent_graph_returns_compiled_langgraph() -> None:
    graph = build_agent_graph()

    assert hasattr(graph, "invoke")


def test_langgraph_workflow_produces_planner_decision() -> None:
    state = run_agent_graph(
        {
            "goal": G02_GOAL,
            "game_state": {"location": "farm", "inventory": {}, "equipment": {}},
            "current_plan": [],
            "completed_subgoals": [],
            "memories": [],
            "replan_count": 0,
            "enable_replanning": True,
        }
    )

    assert state["decision"]["tool"] == "move"
    assert state["decision"]["current_subgoal"] == "obtain_iron"
