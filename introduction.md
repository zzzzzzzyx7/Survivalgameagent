# 自主生存策略游戏 Agent 项目计划书 V1.0

## 一、项目名称

中文正式名称可以叫：

> **基于 LLM Agent 的自主生存与长程任务规划系统**

更适合 GitHub 的英文名称：

> **SurvivalAgent: An LLM Agent for Autonomous Planning and Decision-Making in Interactive Game Environments**

简历里可以稍微短一点：

> **基于 LangGraph 的自主生存策略游戏 Agent**

---

# 二、项目一句话定位

构建一个轻量级生存策略游戏环境，使 LLM Agent 能够根据当前世界状态，自主制定计划、调用环境工具、管理资源、应对随机事件并动态重新规划，最终完成具有多步依赖关系的长期任务，同时建立自动化 Benchmark 对不同 Agent 策略进行评测。

注意关键词不是：

> LLM 玩游戏

而是：

> **LLM Agent 在一个受规则约束的动态环境中自主完成长期目标。**

这个定位非常重要。

---

# 三、核心研究 / 工程问题

这个项目实际上研究 5 个问题：

### 1. Agent 能否理解当前环境状态？

例如：

```text
HP = 48
Energy = 25
Gold = 100

Inventory:
Wood × 2
Iron × 1
Food × 0

Location:
Mine
```

Agent是否意识到：

> 现在继续挖矿可能导致 Energy 不足。

---

### 2. Agent 能否进行长程规划？

例如目标：

> 在第 10 天之前进入遗迹并击败守卫。

它不是一步完成，而可能需要：

```text
收集木材
→ 获得铁矿
→ 制作铁剑
→ 获得金币
→ 购买钥匙
→ 准备食物和药水
→ 前往遗迹
→ 战斗
```

---

### 3. 环境变化时能否 Replanning？

例如：

```text
计划：
去 Mine 挖 Iron

↓

环境：
Mine Closed

↓

Agent：
重新规划
```

而不是无限重复：

```text
mine()
mine()
mine()
```

---

### 4. Memory 是否能够帮助 Agent？

例如第一局死亡原因：

```text
进入遗迹时：
HP = 31
Potion = 0
```

记录经验：

```text
进入遗迹前最好 HP > 70
并携带至少一个 Potion
```

下一局观察 Agent 是否改变策略。

---

### 5. 不同 Agent 架构谁更好？

最终比较：

```text
Direct Agent
ReAct Agent
Planner Agent
Planner + Memory Agent
```

通过统一游戏任务自动跑 Benchmark。

这会成为整个项目最大的技术亮点。

---

# 四、整体系统架构

建议最终架构如下：

```text
                   User / Evaluation Runner
                           │
                           ▼
                     Task / Goal
                           │
                           ▼
                 ┌──────────────────┐
                 │   LLM Agent      │
                 │                  │
                 │ Goal Analysis    │
                 │ Planning         │
                 │ Tool Selection   │
                 │ Replanning       │
                 │ Reflection       │
                 └────────┬─────────┘
                          │
                     Tool Calling
                          │
                          ▼
              ┌───────────────────────┐
              │     Game Engine       │
              │                       │
              │ State Manager         │
              │ Rule Engine           │
              │ Action Validator      │
              │ Event System          │
              │ Reward / Goal Check   │
              └──────────┬────────────┘
                         │
                    Observation
                         │
                         ▼
              ┌───────────────────────┐
              │ Agent State / Memory  │
              └───────────────────────┘
```

旁边再独立一套：

```text
Evaluation Runner
       ↓
自动运行 N 个 Episode
       ↓
Metrics
       ↓
Evaluation Dashboard
```

---

# 五、最重要的架构原则

整个游戏世界的真实状态必须由：

> **Game Engine**

维护。

而不是 LLM。

例如 LLM 不能说：

> “我获得了 5 个 Iron。”

它只能调用：

```python
gather("iron")
```

Game Engine判断是否合法，再返回：

```text
Action failed:
Iron cannot be gathered in Forest.
```

或者：

```text
Success:
Iron +2
Energy -15
```

所以结构一定是：

```text
LLM提出行动

↓

环境判断是否合法

↓

环境修改真实状态

↓

把 Observation 返回给 LLM
```

这会让整个项目真正成为：

> **Agent + Environment**

而不是 Role Play。

---

# 六、游戏世界设计

第一版不要做 Grid Movement。

建议使用：

> **Location-Based World**

也就是几个抽象地点之间移动。

MVP 使用 5 个主要地点。

## 1. Base 基地

功能：

```text
休息
恢复 Energy
存放资源
查看状态
```

---

## 2. Forest 森林

资源：

```text
Wood
Herb
Food
```

可能发生：

```text
Wolf Encounter
Merchant Encounter
```

---

## 3. Mine 矿区

资源：

```text
Iron Ore
Stone
```

特点：

```text
Energy 消耗高
可能塌方
可能遇到 Goblin
```

---

## 4. Village 村庄

可以：

```text
Buy
Sell
Craft
NPC Quest
```

重要商品：

```text
Food
Potion
Ancient Key
Iron
```

---

## 5. Ruins 遗迹

最终区域。

进入需要：

```text
Ancient Key
```

建议挑战需要：

```text
Iron Sword
```

最终：

```text
Guardian
```

---

# 七、玩家状态设计

第一版控制在这些变量：

```python
GameState = {
    "day": 1,

    "hp": 100,
    "energy": 100,

    "gold": 50,

    "location": "base",

    "inventory": {},

    "equipment": {},

    "quests": {},

    "world_state": {},

    "goal": {},

    "done": False
}
```

核心属性：

| State       | 范围 / 作用   |
| ----------- | --------- |
| HP          | 0～100     |
| Energy      | 0～100     |
| Gold        | ≥0        |
| Day         | 1～10      |
| Location    | 当前地点      |
| Inventory   | 当前物品      |
| Equipment   | 武器等       |
| Quest       | 已接受任务     |
| World State | 矿区关闭等环境状态 |

第一版**不要增加 Hunger**。

Food 可以直接：

```text
恢复 Energy
```

否则 HP + Energy + Hunger 三者存在较大功能重叠。

---

# 八、资源和物品

MVP 控制在大约 10 个。

### 原材料

```text
Wood
Iron Ore
Herb
```

### 消耗品

```text
Food
Potion
```

### 装备

```text
Wooden Sword
Iron Sword
```

### 关键物品

```text
Ancient Key
Guardian Gem
```

### 货币

```text
Gold
```

这已经足够形成复杂资源链。

---

# 九、制作系统

例如：

### Wooden Sword

```text
Wood × 3
Energy × 5
```

### Iron Sword

```text
Wood × 2
Iron Ore × 3
Energy × 10
```

### Potion

```text
Herb × 2
Gold × 10
```

这些规则全部放在：

```python
recipes.py
```

而不是写进 Prompt。

这样游戏逻辑与 Agent 分离。

---

# 十、移动机制

不同地点之间需要成本。

例如：

| From    | To      | Energy |
| ------- | ------- | -----: |
| Base    | Forest  |      5 |
| Base    | Village |      5 |
| Forest  | Mine    |     10 |
| Village | Mine    |     10 |
| Village | Ruins   |     15 |

可以不用真正做地图寻路。

Agent只需要理解：

> 不同移动存在成本。

---

# 十一、时间系统

建议：

```text
每完成若干操作 → 消耗时间
```

不要做分钟级时间。

使用：

```text
Action Point / Day
```

更加容易。

例如：

```text
每天最多 6 Action Points
```

或者更简单：

```text
move      +1 step
gather    +1 step
craft     +1 step
fight     +1 step
```

最终目标：

```text
最大 40 Steps
```

我反而更推荐 **Step Limit**，因为后期 Benchmark 更容易。

游戏 UI 可以把：

```text
Step 18 / 40
```

显示成：

```text
Day 5
```

但底层 Evaluation 统一使用 Step。

---

# 十二、Agent Action Space

第一版建议做 8 个 Tool。

## move

```python
move(location: str)
```

作用：

移动地点。

---

## gather

```python
gather(resource: str)
```

采集：

```text
Wood
Herb
Food
Iron
```

环境负责检查当前地点。

---

## craft

```python
craft(item: str)
```

环境检查：

```text
Recipe
Resources
Energy
Location
```

---

## trade

```python
trade(
    action: Literal["buy", "sell"],
    item: str,
    quantity: int
)
```

---

## rest

```python
rest()
```

恢复 Energy。

---

## use_item

```python
use_item(item: str)
```

例如 Potion。

---

## fight

```python
fight(enemy: str)
```

---

## inspect

```python
inspect(target: str)
```

用于查看：

```text
location
inventory
recipe
quest
enemy
```

---

# 十三、Tool Result 统一格式

这个非常值得认真设计。

所有 Tool 返回：

```json
{
  "success": true,

  "action": "gather",

  "observation": "You gathered 2 Wood.",

  "state_changes": {
    "wood": "+2",
    "energy": "-8"
  },

  "events": [],

  "step": 12
}
```

失败：

```json
{
  "success": false,

  "action": "craft",

  "error_code": "INSUFFICIENT_RESOURCES",

  "observation": "Iron Sword requires 3 Iron Ore, but you only have 1."
}
```

这样以后 Evaluation 特别方便。

---

# 十四、游戏规则必须是确定性的

例如：

```python
if state.energy < 10:
    return ActionResult(
        success=False,
        error_code="NOT_ENOUGH_ENERGY"
    )
```

而不能把这些交给 LLM 判断。

项目可以明确分成：

### LLM

负责：

```text
理解
规划
决策
重新规划
```

### Environment

负责：

```text
规则
状态
合法性
执行结果
```

---

# 十五、随机事件系统

第一版只需要 4 种。

## Enemy Encounter

例如：

```text
Wolf
Goblin
```

---

## Mine Closed

某几个 Step：

```text
Mine unavailable
```

迫使 Agent 找替代路线。

---

## Merchant Event

随机商人出现。

可能：

```text
Ancient Key 20% off
```

---

## Resource Shortage

例如：

```text
Iron temporarily depleted.
```

目的不是增加游戏性。

而是创造：

> **Plan Failure**

然后测试 Replanning。

---

# 十六、任务系统

至少设计 5 个 Benchmark Task。

## Task 1：资源任务

> Collect 5 Wood.

主要测试：

```text
基础 Tool Calling
```

---

## Task 2：制作任务

> Craft an Iron Sword.

需要：

```text
Wood
+
Iron
+
Craft
```

测试：

```text
短程 Planning
```

---

## Task 3：经济任务

> Accumulate 150 Gold.

Agent可能：

```text
采资源
→ 出售
```

测试：

```text
资源管理
```

---

## Task 4：探索任务

> Enter the Ruins.

需要：

```text
Ancient Key
+
资源规划
+
移动
```

---

## Task 5：最终任务

> Defeat the Guardian within 40 steps.

需要：

```text
武器
HP
Potion
Key
路线
资源
战斗
```

这是：

> **Long-Horizon Planning Benchmark**

---

# 十七、再加入条件化任务

为了避免 Agent 背答案，需要 Random Seed。

例如游戏开始时随机：

```text
Iron Sword Recipe
```

可能需要：

```text
3 Iron + 2 Wood
```

下一局：

```text
4 Iron + 1 Wood
```

商店价格也可以变化：

```text
Ancient Key:
80 / 100 / 120 Gold
```

矿区随机：

```text
开放
关闭
资源数量变化
```

这样 Agent不能死记固定 Action Sequence。

---

# 十八、Agent V1：Direct Tool Agent

最简单版本：

```text
Goal
+
Current State
+
Available Tools
        ↓
       LLM
        ↓
      Action
        ↓
 Environment
        ↓
 Observation
        ↓
       LLM
```

不提前生成完整计划。

这就是你的：

> **Baseline Agent**

---

# 十九、Agent V2：ReAct Agent

结构：

```text
Observation
↓
Reason
↓
Action
↓
Tool
↓
Observation
```

重点在：

> 每一步根据当前情况重新选择动作。

---

# 二十、Agent V3：Planner Agent

加入：

```text
Planner Node
```

首次接到目标后：

```text
Goal

↓

Subgoals

1. Obtain Iron Sword
2. Obtain Ancient Key
3. Prepare Potion
4. Enter Ruins
5. Defeat Guardian
```

然后：

```text
Executor
```

执行。

---

# 二十一、Agent V4：Planner + Replanning

建议这是你的**主系统**。

LangGraph：

```text
START
   ↓
Goal Analyzer
   ↓
Planner
   ↓
Executor
   ↓
Tool
   ↓
Observation
   ↓
Progress Checker
   ↓
任务正常？
 ↙         ↘
Yes         No
 ↓           ↓
Executor   Replanner
 ↓           ↓
 └───────────┘
       ↓
Goal Checker
   ↓       ↓
Success   Continue
```

---

# 二十二、LangGraph State

建议：

```python
class AgentState(TypedDict):

    goal: str

    game_state: dict

    current_plan: list[str]

    completed_subgoals: list[str]

    current_subgoal: str

    tool_history: list

    observations: list

    memories: list[str]

    reflections: list[str]

    step_count: int

    replan_count: int

    status: str
```

这里真正体现你会：

> **Stateful Agent**

---

# 二十三、Memory 分两种

不要一开始就 Vector DB。

## Working Memory

当前 Episode 内：

```text
我已经获得 2 Iron。

Merchant 在 Village。

Mine 今天关闭。
```

保存在：

```text
AgentState
```

---

## Episodic Memory

跨 Episode：

```text
Episode 7:
Failed because Agent entered Ruins at HP=32.

Lesson:
Prepare Potion before entering Ruins.
```

保存：

```text
memory.json
```

或者数据库。

---

# 二十四、Reflection

一次 Episode 结束后，不管成功还是失败，让 Agent分析：

```text
Goal
Final State
Action Trace
Failure Reason
```

生成：

```json
{
  "failure_reason": "insufficient preparation",

  "lessons": [
    "Do not enter Ruins with HP below 60.",
    "Prepare at least one Potion."
  ]
}
```

下一 Episode：

```text
Relevant Past Lessons
```

加入 Prompt。

---

# 二十五、一个很重要的问题：防止 Memory 越积越多

不要把所有 Reflection 全塞进 Context。

可以限制：

```text
最多保存 20 条 lesson
```

每次只选：

```text
Top 3 Relevant Memories
```

第一版甚至可以关键词匹配。

后期再尝试：

```text
Embedding Retrieval
```

这时候 RAG 才是自然加入的。

---

# 二十六、不要第一版强行做 RAG

你的主系统实际上已经有：

```text
Tool
Planning
State
Memory
Replanning
Reflection
Evaluation
```

技术密度足够高。

RAG 可以作为 Extension：

> 当游戏规则增长到几十种物品、技能、NPC、怪物时，让 Agent 从游戏 Wiki 中检索相关规则。

这样才合理。

---

# 二十七、Evaluation 系统是项目重点

整个项目建议至少投入 **25% 时间**做 Evaluation。

建立：

```text
benchmark/
```

里面放：

```text
任务
初始 State
Random Seed
最大步数
成功条件
```

例如：

```json
{
  "task_id": "T05",
  "goal": "Defeat Guardian",
  "max_steps": 40,
  "seed": 10086,
  "success_condition": "guardian_defeated"
}
```

---

# 二十八、主要 Benchmark 方法

每种 Agent：

```text
Direct
ReAct
Planner
Planner + Memory
```

每个 Task：

```text
20 Seeds
```

5 个任务：

```text
5 × 20
=
100 Episodes / Agent
```

4 个 Agent：

```text
400 Episodes
```

如果 Token Cost 太贵，可以缩成：

```text
10 Seeds
×
5 Tasks
×
4 Agents

=
200 Episodes
```

已经足够展示。

---

# 二十九、核心指标

## Task Success Rate

```text
成功 Episode / 总 Episode
```

这是最重要的。

---

## Average Steps

成功完成任务平均多少步。

越少通常越有效率。

---

## Invalid Action Rate

例如：

```text
Agent在森林里尝试 mine iron
```

统计：

```text
Invalid Actions / Total Actions
```

---

## Replanning Count

测试：

> Agent遇到环境变化时是否调整计划。

---

## Resource Efficiency

例如：

```text
完成任务剩余 HP
剩余 Gold
消耗 Food
```

可以作为次要指标。

---

## Token Usage

统计：

```text
Prompt Tokens
Completion Tokens
Total Tokens
```

---

## Cost

如果 API 支持：

```text
Cost / Episode
```

---

## Latency

```text
Average Decision Latency
```

---

# 三十、最终实验表可以长这样

真实完成以后：

| Agent            | Success | Avg Steps | Invalid Action | Tokens |
| ---------------- | ------: | --------: | -------------: | -----: |
| Direct           |      实测 |        实测 |             实测 |     实测 |
| ReAct            |      实测 |        实测 |             实测 |     实测 |
| Planner          |      实测 |        实测 |             实测 |     实测 |
| Planner + Memory |      实测 |        实测 |             实测 |     实测 |

不要为了 README 好看而虚构数字。

如果最终发现 Planner 反而表现更差，这也是一个非常值得分析的结果。

---

# 三十一、Failure Analysis

建议把失败分成：

```text
Planning Error

Invalid Action

State Understanding Error

Resource Mismanagement

Looping

Premature Goal Attempt

Failure to Replan

Combat Failure
```

Dashboard 可以显示：

```text
Failure Analysis

Planning Error            28%
Resource Mismanagement    24%
Looping                   18%
Invalid Action            12%
Other                     18%
```

这与你已有 Benchmark Evaluation 经验也能自然衔接。

---

# 三十二、游戏前端

第一版建议：

```text
Streamlit
```

不要 React 起步。

最终页面分成四块。

## 页面 1：Live Game

左侧：

```text
World Map

🌲 Forest
⛰ Mine
🏠 Base
🏪 Village
🏰 Ruins
```

中间：

```text
Agent

Goal
Plan
Current Subgoal
Current Action
```

右侧：

```text
HP
Energy
Gold
Inventory
Step
```

---

# 三十三、Agent Trace 页面

显示：

```text
Step 13

Current State

↓

Plan

↓

Selected Tool

gather("iron")

↓

Observation

Iron +2
Energy -15

↓

Plan Progress
```

非常适合面试展示。

---

# 三十四、Evaluation Dashboard

显示：

```text
Agent Comparison

Success Rate

Average Steps

Invalid Actions

Token Cost
```

再显示：

```text
Task Difficulty
```

和：

```text
Failure Categories
```

---

# 三十五、Episode Replay

这个功能我非常推荐。

保存：

```text
每一步
State
Action
Observation
```

例如：

```json
[
  {
    "step": 1,
    "action": "move",
    "args": {"location": "forest"},
    "state_before": {},
    "state_after": {}
  }
]
```

然后 UI：

```text
← Previous      Step 13 / 32      Next →
```

可以回看整个 Agent 游戏过程。

这个会非常有展示效果。

---

# 三十六、日志系统

建议每个 Episode 保存：

```text
episode_id

model

agent_type

seed

task

success

steps

tokens

latency

final_state
```

另外保存：

```text
完整 Trace
```

文件：

```text
logs/
    episode_001.json
```

后期 Evaluation 全部从这里读取。

---

# 三十七、建议数据库

第一版不需要 PostgreSQL。

直接：

```text
SQLite
```

保存：

```text
evaluation_runs
episodes
memories
```

游戏实时 State 可以纯 Python。

---

# 三十八、代码目录

推荐：

```text
survival-agent/

├── app/
│
│   ├── environment/
│   │   ├── game.py
│   │   ├── state.py
│   │   ├── locations.py
│   │   ├── items.py
│   │   ├── recipes.py
│   │   ├── events.py
│   │   ├── combat.py
│   │   └── rewards.py
│   │
│   ├── tools/
│   │   ├── movement.py
│   │   ├── gathering.py
│   │   ├── crafting.py
│   │   ├── trading.py
│   │   └── combat.py
│   │
│   ├── agents/
│   │   ├── state.py
│   │   ├── direct_agent.py
│   │   ├── react_agent.py
│   │   ├── planner_agent.py
│   │   ├── graph.py
│   │   ├── planner.py
│   │   ├── replanner.py
│   │   └── reflection.py
│   │
│   ├── memory/
│   │   ├── episodic_memory.py
│   │   └── memory_store.py
│   │
│   ├── models/
│   │   └── llm.py
│   │
│   └── config.py
│
├── evaluation/
│   ├── tasks/
│   ├── runner.py
│   ├── metrics.py
│   ├── failure_analysis.py
│   └── reports/
│
├── frontend/
│   ├── app.py
│   ├── game_view.py
│   ├── trace_view.py
│   └── evaluation_view.py
│
├── tests/
│   ├── test_environment.py
│   ├── test_tools.py
│   ├── test_rules.py
│   └── test_tasks.py
│
├── logs/
├── data/
├── README.md
├── requirements.txt
└── .env.example
```

---

# 三十九、技术栈

核心：

```text
Python
LangChain
LangGraph
Pydantic
```

模型：

```text
OpenAI / DeepSeek / Qwen
```

任选其一作为主模型。

建议通过统一接口：

```python
get_llm(model_name)
```

以后方便做模型对比。

UI：

```text
Streamlit
```

数据：

```text
SQLite
JSON
Pandas
```

可视化：

```text
Matplotlib / Plotly
```

测试：

```text
pytest
```

---

# 四十、开发阶段安排

我建议正式按照 **4 周 MVP** 开发。

## Week 1 —— 环境优先

目标：

> 不使用任何 LLM，也能完整玩通游戏。

Day 1：

```text
确定 GameState
地点
物品
Recipes
任务
```

Day 2：

```text
move
gather
rest
```

Day 3：

```text
inventory
craft
trade
```

Day 4：

```text
fight
HP
Potion
```

Day 5：

```text
Random Event
World State
```

Day 6：

```text
Guardian
最终目标
```

Day 7：

```text
pytest
修复规则
```

Week 1 验收标准：

你必须可以人工写：

```python
env.move(...)
env.gather(...)
env.craft(...)
```

最终通关。

---

# 四十一、Week 2 —— Agent 基础

Day 8～9：

```text
Tool 封装
```

Day 10：

```text
Direct Agent
```

Day 11：

```text
ReAct Agent
```

Day 12：

```text
LangGraph State
```

Day 13：

```text
Planner
```

Day 14：

```text
Planner + Executor 跑通
```

验收：

> Agent可以在一个固定世界中完成 Craft Iron Sword。

---

# 四十二、Week 3 —— 高级 Agent

Day 15：

```text
Progress Checker
```

Day 16：

```text
Replanner
```

Day 17：

```text
随机事件
+
Replanning
```

Day 18：

```text
Working Memory
```

Day 19：

```text
Episode Reflection
```

Day 20：

```text
跨 Episode Memory
```

Day 21：

```text
最终 Guardian Task
```

验收：

> Agent 能够遇到 Mine Closed 后改变原计划，而不是卡死。

---

# 四十三、Week 4 —— Evaluation + 展示

Day 22：

```text
Benchmark Task
```

Day 23：

```text
Evaluation Runner
```

Day 24：

```text
Metrics
```

Day 25：

```text
批量 Episode
```

Day 26：

```text
Failure Analysis
```

Day 27：

```text
Streamlit Demo
```

Day 28：

```text
README
实验结果
录制 Demo
整理简历
```

---

# 四十四、必须做的单元测试

例如：

### Craft

```text
材料充足 → success

材料不足 → fail

Energy不足 → fail
```

### Trade

```text
Gold足够 → success

Gold不足 → fail

商品不存在 → fail
```

### Move

```text
合法地点 → success

不存在地点 → fail
```

### Combat

```text
HP归零 → game over
```

### Goal

```text
Guardian defeated → success
```

这里体现：

> Agent 层有随机性，但 Environment 必须可靠。

---

# 四十五、Benchmark 必须固定 Random Seed

否则：

Agent A：

```text
一路没有遇到敌人
```

Agent B：

```text
连续遇到3次敌人
```

就不能公平比较。

所以 Evaluation：

```python
for seed in seeds:
    run(agent_a, seed)
    run(agent_b, seed)
```

确保环境完全一致。

这属于非常好的实验设计细节。

---

# 四十六、建议设计三个最终展示 Case

面试时不要随机让 Agent 跑 10 分钟。

提前准备三个场景。

## Demo 1：基础规划

目标：

> Craft Iron Sword.

展示：

```text
Goal
→ Plan
→ Gather
→ Move
→ Mine
→ Craft
```

时间：

30～45 秒。

---

## Demo 2：动态 Replanning

计划：

```text
去 Mine 挖 Iron
```

环境：

```text
Mine Closed
```

Agent：

```text
重新规划
→ Forest采Wood
→ Village出售
→ 买Iron
```

这是最重要的 Demo。

---

## Demo 3：Memory

第一次：

```text
Agent低血进入Ruins
→ Death
```

Reflection：

```text
Need Potion before Ruins
```

第二次：

```text
提前买 Potion
→ Survival
```

这个直接展示：

> Agent从失败中学习。

---

# 四十七、这个项目真正不要做什么

第一版明确排除：

```text
❌ Unity

❌ Godot

❌ 3D

❌ 实时操作

❌ 复杂寻路

❌ 多人联机

❌ Multi-Agent

❌ 复杂技能树

❌ 数十个 NPC

❌ 微调模型

❌ 强行加入 RAG
```

否则这个项目会失控。

---

# 四十八、完成 MVP 后再考虑的扩展

按照价值排序：

### Extension A：Multi-Agent

例如：

```text
Warrior
+
Healer
```

研究：

```text
Task Allocation
Communication
Coordination
```

这个可以成为 V2。

---

### Extension B：玩家 + AI 队友

玩家通过自然语言：

> 你先去矿洞，我去找食物。

Agent理解任务并执行。

展示效果非常好。

---

### Extension C：Game Wiki RAG

增加大量：

```text
Recipe
Monster
NPC
Quest
Item
```

让 Agent 不能一次拿到所有游戏规则。

需要主动：

```text
search_game_knowledge()
```

---

### Extension D：不同模型 Benchmark

比较：

```text
GPT
Qwen
DeepSeek
```

在同一个环境的：

```text
Planning
Cost
Latency
Success
```

这也非常符合你目前 LLM Benchmark 方向。

---

# 四十九、Github README 最终应该展示什么

首页不要先放一大堆代码。

建议：

```text
1. 一张系统截图 / GIF

2. 一句话介绍项目

3. Architecture

4. Agent Workflow

5. Game Environment

6. Benchmark

7. Experiment Results

8. Failure Analysis

9. Quick Start
```

面试官进入 GitHub 后 30 秒内应该知道：

> 这不是小游戏，而是 Agent Benchmark Environment。

---

# 五十、最后的简历写法

做完以后可以写成：

> **基于 LangGraph 的自主生存策略游戏 Agent**

> 设计并实现具备资源、制作、交易、战斗及动态事件机制的交互式游戏环境，将移动、采集、制作等环境操作封装为结构化 Tool，实现 LLM Agent 与受约束环境的自主交互。

> 基于 LangGraph 构建 Planner–Executor–Replanner 工作流，通过 Agent State 管理目标、子任务、环境状态及历史 Observation，实现复杂长期任务的动态规划与异常恢复。

> 引入 Episodic Memory 与 Reflection 机制，使 Agent 从历史失败 Episode 中抽取策略经验，并在后续任务中进行记忆检索与决策调整。

> 构建自动化 Agent Benchmark，对 Direct、ReAct、Planner、Planner+Memory 等策略在多任务、多随机种子环境下进行对比，从任务成功率、平均行动步数、非法动作率、Token 消耗及任务失败类型等维度进行评测。

最后一条会是这个项目最有价值的部分。

---

# 五十一、整个项目的优先级

如果时间开始不够，就按照这个顺序砍：

```text
必须完成

Game Environment
↓
Tool Calling
↓
Agent
↓
Planning
↓
Replanning
↓
Evaluation
```

然后才是：

```text
重要

Memory
↓
Reflection
↓
UI
```

最后才是：

```text
加分

RAG
↓
Multi-Agent
↓
复杂地图
```

也就是说：

**宁可没有特别漂亮的游戏界面，也必须把 Evaluation 做出来。**

---

# 五十二、最终的 MVP 验收标准

我建议你以后以这 8 条作为“项目是否完成”的标准：

1. Environment 可以脱离 LLM 独立运行，并拥有完整规则测试。
2. Agent 只能通过 Tool 修改游戏环境。
3. 至少存在一个需要 10 步以上完成的长期任务。
4. 至少存在三种会破坏原计划的环境变化。
5. Agent 能根据 Observation 进行 Replanning。
6. 至少实现 Direct、ReAct、Planner 三种 Agent 作为对照。
7. 可以批量运行 Episode，并生成 Success Rate 等指标。
8. 可以通过 UI 或 Replay 清楚展示 Agent 为什么采取每一步行动。

做到这里，这个项目就已经完整了。

---

## 我对整个项目的推荐范围

最终控制为：

**5 个地点 + 10 个左右物品 + 8 个 Tool + 5 个 Benchmark Task + 3～4 种 Agent + 200 左右 Evaluation Episodes + 一个 Streamlit 可视化界面。**

这个规模不会太小，也不会失控。

第一阶段甚至完全不要碰 LangGraph。你下一步真正应该做的是把 **Game Environment Specification** 写死：`GameState、Locations、Items、Recipes、Actions、Events、Task Success Conditions`。

只有环境确定以后，Agent 才有一个稳定的“世界”可以操作。之后我们再开始设计 LangGraph，会顺很多。
