# SurvivalAgent

SurvivalAgent 是一个轻量级的游戏环境与 Agent Benchmark 项目，用来研究
LLM Agent 如何在受规则约束的交互式世界中进行规划、行动、重规划和经验学习。

项目的核心边界是：

```text
Agent 只能提出结构化 Tool 调用
Environment 负责校验规则、更新真实状态、返回 observation
Evaluation Runner 负责批量运行、记录 trace、计算指标
```

这不是一个“LLM 角色扮演小游戏”，而是一个 **Agent + Environment +
Evaluation** 框架。

## 项目结构

```text
app/
  environment/   游戏真实状态、规则、事件、战斗、奖励和目标判定。
  tools/         面向 Agent 的薄 Tool 封装。
  skills/        高层 Skill，负责把任务路线映射到固定 MVP Tool。
  agents/        Direct、ReAct、Planner、Replanning、LLM Agent、Reflection。
  memory/        Episode lesson 数据结构和 JSON memory store。
  models/        LLM 统一工厂与模型适配器。

evaluation/
  tasks/         Benchmark 任务定义。
  runner.py      Episode runner、batch runner、trace logging。
  metrics.py     指标聚合与 summary 生成。
  reports/       生成的 benchmark summary，默认不纳入源码。

frontend/
  app.py         Streamlit 入口。
  game_view.py   实时运行页面，支持新游戏、执行一天和自动运行。
  task_inputs.py 动态任务文本输入区，默认两条中文任务。
  trace_view.py  轨迹回放页面，支持递归读取 logs 子目录。

scripts/
  run_benchmark.py 命令行 benchmark 入口。

tests/
  环境规则、Agent、Evaluation、Memory、LLM、结构检查测试。

docs/
  architecture.md       架构边界说明。
  game-rules-spec.md    游戏规则规格。
  project-structure.md  项目结构说明。

logs/
  生成的 episode trace。

data/
  生成的本地 memory/database 文件。
```

更多结构说明见 [docs/project-structure.md](docs/project-structure.md)。

## Tool 与 Skill 分层

MVP Tool 固定为 15 个，不继续增加：

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

第一阶段 Skill 固定为 7 个：

```text
Resource Acquisition
Farming Cycle
Fishing Route
Money Making
Combat Preparation
Recovery
Quest Completion
```

Tool 是环境动作边界，负责执行单个结构化动作。Skill 是高层能力边界，
负责根据 observation 和 goal 选择下一步应该调用哪个 MVP Tool。

当前第一阶段公开 `Quest Completion` Skill，Agent 可以通过 `accept_quest` 和
`submit_quest` 在 Guild 接取、完成并提交任务。

Skill 是否允许调用 `inspect` 由环境变量控制：

```powershell
$env:SURVIVAL_AGENT_SKILLS_ALLOW_INSPECT="true"
```

设置为 `false` 后，Skill 层不会主动返回 `inspect` decision。

## 日内规则

当前环境没有日内时钟，也没有每天几点强制结束的限制。一天内能执行多少动作只由
Energy 决定：成功动作会按规则扣除 Energy；无效动作只推进 step，不扣 Energy。
Food 和消耗品不再恢复 Energy，`rest` 是唯一恢复 Energy 的方式，会进入下一天并把
Energy 重置为 100。`use_item` 仅用于恢复 HP。`plant`、`water(all)` 和
`harvest(all)` 都按实际影响的地块数量重复扣除 Energy。

## 本地环境

使用已安装项目依赖的 Python 环境：

```powershell
python
```

项目目录中也可能存在本地虚拟环境 `game_agent/`。它被视为机器本地产物，
已被 `.gitignore`、`.ignore` 和 ruff 忽略。

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 运行测试

```powershell
python -m pytest -q
python -m ruff check .
```

## 运行 Benchmark

默认运行全部 baseline agent、全部 G01-G05 任务、seeds 1-3：

```powershell
python scripts\run_benchmark.py
```

指定 agents、tasks、seeds：

```powershell
python scripts\run_benchmark.py --agents direct react planner planner_replanning --tasks G01 G02 G03 G04 G05 --seeds 1 2 3
```

输出：

- episode trace 写入 `logs/benchmark/`
- summary 写入 `evaluation/reports/latest_summary.json`

## 使用 Memory

传入 `--memory-path` 后，runner 会在 episode 开始前检索相关 lessons，并在
episode 结束后写入新的 reflection lesson。

```powershell
python scripts\run_benchmark.py --agents planner_replanning --tasks G02 --seeds 1 2 --memory-path data\memory.json
```

## 使用 LLM Agent

默认 LLM 模型是：

```text
deepseek-flash
```

默认使用 DeepSeek 的 OpenAI-compatible API：

```text
https://api.deepseek.com
```

运行前需要设置 API key：

```powershell
$env:DEEPSEEK_API_KEY="your-api-key"
python scripts\run_benchmark.py --agents llm --tasks G02 --seeds 1
```

可选环境变量：

```powershell
$env:SURVIVAL_AGENT_MODEL="deepseek-flash"
$env:SURVIVAL_AGENT_LLM_BASE_URL="https://api.deepseek.com"
$env:SURVIVAL_AGENT_LLM_API_KEY_ENV="DEEPSEEK_API_KEY"
$env:SURVIVAL_AGENT_INPUT_COST_PER_1M="0.14"
$env:SURVIVAL_AGENT_OUTPUT_COST_PER_1M="0.28"
$env:SURVIVAL_AGENT_LLM_TIMEOUT_SECONDS="90"
$env:SURVIVAL_AGENT_LLM_MAX_RETRIES="2"
$env:SURVIVAL_AGENT_LLM_RETRY_BACKOFF_SECONDS="1.5"
$env:SURVIVAL_AGENT_SKILLS_ALLOW_INSPECT="true"
```

如果没有设置 `DEEPSEEK_API_KEY`，本地测试仍可通过 fake model 覆盖 LLM
decision parsing，但不会发起真实模型请求。

如果实时运行中出现 `APITimeoutError`，通常是模型接口响应超过超时阈值。
可以在 `.env` 中提高 `SURVIVAL_AGENT_LLM_TIMEOUT_SECONDS`，例如设置为 `120`
或 `180`，保存后重启 Streamlit。项目会对超时、连接错误、限流和服务端错误做
有限重试；如果仍持续超时，优先换用更快的模型或稍后重试。

## 常见错误排查

### APITimeoutError

含义：LLM 接口在超时时间内没有返回结果。实时运行中，这通常发生在
`plan_day` 阶段，因为模型需要一次性生成当天动作链。

处理方式：

- 提高 `.env` 中的 `SURVIVAL_AGENT_LLM_TIMEOUT_SECONDS`，例如改为 `120` 或 `180`。
- 适当提高 `SURVIVAL_AGENT_LLM_MAX_RETRIES`。
- 换用响应更快的模型。
- 保存 `.env` 后重启 Streamlit。

### JSONDecodeError

含义：模型返回内容不是合法 JSON，程序无法解析成 `day_plan` 或 tool decision。

常见原因：

- 模型返回了空内容。
- 模型返回了普通说明文字，而不是 JSON。
- 模型在 JSON 外包了一段解释。
- 模型输出被截断，JSON 不完整。
- API 返回了错误文本。

处理方式：

- 重新点击“执行一天”。
- 检查模型是否适合稳定输出 JSON。
- 如果频繁出现，优先优化 LLM prompt 或增加 JSON 提取容错逻辑。



## 运行 UI

```powershell
python -m streamlit run frontend\app.py
```

UI 包含：

- 任务输入区：可增删多个任务文本框；每个文本框代表一个任务，默认是
  `拥有至少 900 金币` 和 `制作一把铁剑`。
- 实时运行：选择当前任务后创建新游戏，支持“执行一天”和“自动运行”；
  每次执行会让 LLM 先生成当天动作序列，再由环境逐条校验执行。如果当天中途动作失败，
  系统会把已执行步骤、错误和当前状态回传给 LLM，并在当前进度上重新规划当天剩余动作。
  前端会以“当前动作链”展示当天计划、每个动作的执行状态、结果、错误和执行后的关键状态。
  “当前任务”包含“全部任务”选项。选择“全部任务”时，所有任务文本会合并为一个
  组合 goal 传给 LLM，并要求每个子任务都在 14 天周期内完成。
- 轨迹回放：优先显示当前实时运行的 LLM trace，并按 Day 查看每日动作链；
  也可以在历史日志回放中查看 `logs/` 下的 episode trace。

## Benchmark 任务

```text
G01: 14 天 episode 内达到 900 Gold
G02: 14 天 episode 内制作 Iron Sword
G03: 14 天 episode 内收获 3 个 Potato
G04: 14 天 episode 内获得 Ancient Key
G05: 14 天 episode 内击败 Guardian
```


## Agent 对照

```text
direct
  直接根据 observation 选择下一步 tool。

react
  在 direct decision 基础上记录 thought/reasoning。

planner
  先生成固定 subgoal plan，再按计划执行。

planner_replanning
  使用 LangGraph 工作流，在失败、矿洞关闭、storm、pending enemy 等情况下重规划。

llm
  调用 deepseek-flash，实时运行中要求模型输出结构化 JSON day plan。
```

## 关键设计原则

- Environment 是唯一真实状态来源。
- Agent 不能直接修改 HP、Gold、Inventory、Equipment。
- 所有动作必须经过环境规则校验。
- Benchmark 使用固定 seed，保证不同 Agent 在同一环境条件下比较。
- Trace 记录每一步的 state_before、decision、result、state_after。
- Memory 和 Reflection 以 episode 为单位沉淀经验。

