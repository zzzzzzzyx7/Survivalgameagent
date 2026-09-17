# 项目架构

本文档说明 SurvivalAgent 当前版本的分层边界、运行链路和主要数据流。

## 项目定位

SurvivalAgent 是一个 `Agent + Environment + Evaluation + Frontend` 项目。

核心原则：

```text
Agent 只能输出结构化 Tool 调用
Environment 负责校验规则、更新真实状态、返回 ActionResult
Evaluation Runner 负责运行 episode、记录 trace、统计指标
Frontend 负责展示和交互，不直接修改游戏规则
```

LLM 或其他 Agent 不能直接修改 `Gold`、`Energy`、`Inventory`、`Farm`、
`Quest` 等真实状态。所有状态变化都必须经过环境动作。

## 分层职责

### app.environment

环境层是唯一真实状态来源。

主要职责：

- 保存 `GameState`、`FarmPlot`、`ActionResult`。
- 校验动作是否合法。
- 扣除 Energy、Gold、HP 等资源。
- 处理种植、浇水、收获、移动、采集、挖矿、捕鱼、制作、交易、任务、战斗、休息。
- 结算天气、随机事件、作物成长和目标完成。

环境层不能依赖 Agent、Frontend 或 Evaluation。

### app.tools

Tool 层是很薄的封装层，当前固定 15 个环境动作：

```text
move
plant
water
harvest
forage
mine
fish
craft
trade
accept_quest
submit_quest
use_item
fight
inspect
rest
```

Tool 不保存状态，不实现策略，只把结构化调用交给环境执行。

### app.skills

Skill 层负责把高层目标拆成可执行 Tool。

当前第一阶段 Skill：

```text
Resource Acquisition
Farming Cycle
Fishing Route
Money Making
Combat Preparation
Recovery
Quest Completion
```

Skill 可以选择 Tool，但不能新增环境动作。是否允许 Skill 主动 `inspect` 由
`SURVIVAL_AGENT_SKILLS_ALLOW_INSPECT` 控制。

### app.agents

Agent 层负责决策。

当前 Agent 类型：

- `direct`：确定性规则决策。
- `react`：在 direct 基础上附加 thought/reason。
- `planner`：固定子目标计划 baseline。
- `planner_replanning`：遇到失败、天气或敌人阻塞时重规划。
- `llm`：调用模型，为当前游戏日生成动作链。

实时运行页面主要使用 `llm`。LLM 不再只输出单步动作，而是输出当天动作序列：

```json
{
  "day_objective": "今日目标",
  "reasoning": "规划原因",
  "actions": [
    {"tool": "move", "args": {"location": "town"}, "reason": "去商店"}
  ],
  "final_day_actions": "中文总结"
}
```

如果当天动作链中某一步失败，Runner 会把已完成步骤、失败动作、错误和当前状态放入
`recovery_context`，再请求 LLM 基于当前进度重新规划当天剩余动作。

### app.memory

Memory 层保存 episode 结束后的经验。

Runner 可在 episode 开始前读取相关 lesson，并在结束后把 reflection 写回本地 JSON
memory store。

### evaluation

Evaluation 层负责可重复运行。

主要能力：

- 运行单个 episode。
- 运行批量 benchmark。
- 支持前端文本任务。
- 支持把多个前端任务合并成 `ALL_TASKS`。
- 保存 trace JSON。
- 汇总 success rate、average steps、invalid action rate、token usage、latency、
  estimated cost 等指标。

LLM 超时、连接失败等模型层错误会作为 trace 记录展示，但不会当作游戏内动作推进
`GameState.step`。

### frontend

Frontend 使用 Streamlit。

当前页面：

- 任务输入区：动态增删任务文本，默认两条中文任务。
- 实时运行：新游戏、执行一天、自动运行、停止。
- 轨迹回放：优先显示当前实时运行的 LLM trace，并按 `Day n` 展示每日动作链。

Frontend 可以读取 Runner 和环境状态进行展示，但不应该实现或绕过环境规则。

## 依赖方向

```text
frontend      -> app, evaluation
evaluation    -> app.environment, app.agents, app.memory
app.agents    -> app.skills, app.tools, app.models, app.memory
app.skills    -> app.tools-compatible decisions
app.tools     -> app.environment
app.environment -> no agent dependency
```

最重要的约束：

```text
app.environment 不导入 app.agents、app.tools、frontend、evaluation
```

## 当前运行链路

### 实时运行

```text
Streamlit 实时运行页
  -> 构造前端文本 task
  -> make_game()
  -> make_agent("llm")
  -> run_game_day()
  -> LLM plan_day()
  -> Environment 逐条执行动作
  -> 前端实时更新当前动作链
  -> trace 写入 session_state
  -> 轨迹回放优先展示当前 trace
```

### 命令行批量 Benchmark

```text
scripts/run_benchmark.py
  -> 读取 evaluation/tasks/G01-G05
  -> run_benchmark()
  -> 保存 logs/benchmark/*.json
  -> 展示聚合指标和 episode 结果表
  -> 轨迹回放可读取这些日志
```

## Trace 数据

每条 trace 至少包含：

```text
step
day
decision
result
state_before
state_after
day_plan
decision_latency_ms
```

其中 `day_plan` 用于前端恢复每日动作链，`result.state_changes.energy` 用于展示
`体力变化`。
