# 项目结构

本文档说明当前仓库结构和主要文件用途。

```text
README.md        项目入口说明、运行命令、当前状态。
introduction.md  原始路线图和阶段设计。
game-rules.md    早期长版规则参考。
pyproject.toml   Python 包和工具配置。
.env             本地环境变量，例如 API key、模型、超时设置。
.gitignore       Git 忽略规则。
.ignore          rg/editor 搜索忽略规则。

app/
  config.py       运行配置和 .env 加载。

  environment/
    state.py      GameState、FarmPlot、ActionResult。
    game.py       环境动作执行入口和核心规则。
    energy.py     Energy 消耗表。
    locations.py  地点、移动消耗、Forest 采集表。
    crops.py      作物数据。
    items.py      物品、买卖价格、HP 消耗品。
    recipes.py    Craft 配方。
    quests.py     Guild 任务定义。
    events.py     随机事件。
    weather.py    天气规则。
    combat.py     敌人和战斗数值。
    rewards.py    成功条件判断。

  tools/
    面向 Agent 的薄 Tool 封装。当前 Tool surface 固定为 15 个。

  skills/
    高层 Skill，把任务路线映射到固定 Tool。
    包含资源获取、种植循环、赚钱、钓鱼、战斗准备、恢复、任务完成。

  agents/
    Direct、ReAct、Planner、Planner Replanning、LLM Agent。
    llm_agent.py 负责构造单步决策提示词和每日动作链提示词。

  memory/
    Episode lesson 数据结构和 JSON memory store。

  models/
    llm.py        OpenAI-compatible LLM 客户端，支持超时、重试和 token 统计。

evaluation/
  tasks/
    G01-G05 JSON benchmark 任务。前端不再依赖这些文件定义任务，
    但命令行 benchmark 和兼容测试仍会使用。

  runner.py       Episode runner、day runner、batch runner、trace 保存。
  metrics.py      指标聚合。
  failure_analysis.py 失败分类。
  reports/        生成的 benchmark summary，默认不纳入源码。

frontend/
  app.py          Streamlit 入口。
  task_inputs.py  动态任务文本输入区。
  game_view.py    实时运行页面，支持新游戏、执行一天、自动运行、停止。
  trace_view.py   轨迹回放页面，优先显示当前实时运行 trace，并按 Day 展示动作链。

scripts/
  run_benchmark.py 命令行 benchmark 入口。

tests/
  test_structure.py              导入、Tool、Skill 基础结构测试。
  test_environment_rules.py      环境规则测试。
  test_environment_acceptance.py 目标条件和 scripted 路线测试。
  test_agents.py                 Agent、Planner、Replanning 测试。
  test_evaluation_memory.py      Runner、Frontend helper、LLM factory、Memory 测试。

docs/
  architecture.md       当前架构和数据流。
  game-rules-spec.md    当前游戏规则规格。
  project-structure.md  本文件。
  tool-skill-audit.md   Tool / Skill 必要性审计。

logs/
  生成的 episode trace。
  命令行 benchmark 日志会写入 logs/benchmark/。

data/
  生成的本地 memory/database 文件。
```

## 运行入口

### Streamlit 前端

```powershell
python -m streamlit run frontend\app.py
```

主程序入口是：

```text
frontend/app.py
```

### 命令行 Benchmark

```powershell
python scripts\run_benchmark.py
```

命令行入口是：

```text
scripts/run_benchmark.py
```

### 测试

```powershell
python -m pytest -q
python -m ruff check .
```

当前验证结果：

```text
pytest: 67 passed
ruff: All checks passed
```

## 本地产物

以下内容属于运行产物或机器本地配置：

- `.env`
- `logs/`
- `data/`
- 本地虚拟环境目录，例如 `game_agent/`

这些文件不应该作为核心源码逻辑来维护。
