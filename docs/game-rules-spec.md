# HarvestAgent World 当前规则规格

本文档描述当前代码实现中的游戏规则。它以 `app/environment/` 为准，用于解释
Agent、Runner 和 Streamlit 前端看到的世界。

## 1. 项目定位

HarvestAgent World 是一个轻量农场经营环境，用来测试 LLM Agent 的长期规划、资源分配、
动作执行和失败后重规划能力。

它不是角色扮演游戏。Agent 只能通过结构化 Tool 调用影响世界，环境负责校验规则并返回
真实结果。

## 2. Episode 与主目标

一个 episode 固定为 14 天。

前端任务输入区中的每一条文本都会被包装成一个临时 task。当前支持两种运行方式：

- 单个任务：只要求完成选中的任务文本。
- 全部任务：把所有输入框文本合并成 `ALL_TASKS`，要求 14 天内完成所有子目标。

命令行 benchmark 仍保留 G01-G05：

| Goal | 成功条件 |
| --- | --- |
| G01 | 当前 Gold >= 900 |
| G02 | 拥有 Iron Sword |
| G03 | 累计收获 Potato x3 |
| G04 | 拥有 Ancient Key |
| G05 | 拥有 Ancient Key、Iron Sword，并击败 Guardian 获得 Guardian Gem |

G01-G05 不再各自设置早期截止日，统一以 14 天 episode 为完成周期。

## 3. 初始状态

| 状态 | 初始值 | 说明 |
| --- | ---: | --- |
| Day | 1 | 当前天数 |
| Step | 0 | 已执行环境动作数 |
| HP | 100 | 战斗生命值 |
| Energy | 100 | 当天行动预算 |
| Gold | 500 | 购买种子、材料和道具 |
| Location | Farm | 起始地点 |
| Farm | 9 格空地 | 可直接种植 |

每日没有时钟时间。一天能做多少事只由 Energy 限制。

## 4. 地点与移动

当前地图有 6 个地点：

| 地点 | 功能 |
| --- | --- |
| Farm | 种植、浇水、收获、休息 |
| Town | 商店购买和出售 |
| Forest | 采集 Wood、Berry、Herb、Wild Flower |
| Mine | 挖矿、推进矿洞深度、遭遇敌人 |
| River | 捕鱼 |
| Guild | 接取和提交 Quest |

移动规则：

| 路线 | Energy |
| --- | ---: |
| 任意两个不同非 Mine 地点 | 4 |
| To Mine 或 From Mine | 6 |

同地点移动失败，未知地点失败。Storm 或 Mine Collapse 会关闭 Mine；Storm 也会关闭 River。

## 5. Energy 规则

每天基础 Energy 为 100。

| Action | Energy |
| --- | ---: |
| move | 4 |
| move to/from Mine | 6 |
| plant | 5 / 格 |
| water | 3 / 格 |
| harvest | 4 / 格 |
| forage | 10 |
| mine | 15 |
| mine with Iron Pickaxe | 9 |
| fish | 12 |
| craft | 8 |
| trade | 2 |
| accept_quest | 2 |
| submit_quest | 2 |
| fight | 10 |
| escape | 5 |
| use_item | 2 |
| inspect | 0 |
| rest | 0 |

规则细节：

- 成功动作按规则扣 Energy。
- 非法环境动作推进 Step，但不扣 Energy。
- LLM 超时或模型层异常会记录在 trace 中，但不推进游戏 Step。
- Food 和消耗品不恢复 Energy。
- `rest` 是唯一恢复 Energy 的方式。
- `rest` 会结束当天、进入下一天，并把 Energy 重置为 100。
- 如果成功动作把 Energy 用尽，环境会自动结束当天并在下一天恢复 Energy。

## 6. 农场系统

农田固定为 9 格。

每格记录：

- `plot_id`
- `crop`
- `growth`
- `watered`
- `sprinkler`
- `diseased`
- `ready`

作物规则：

- 作物当天被浇水，日结时 `growth +1`。
- 作物当天未浇水，日结时不成长。
- 作物不会因为缺水死亡。
- Rainy 和 Storm 会自动浇水。
- Sprinkler 每天自动浇 1 格所在农田。
- Crop Disease 事件会让一个作物当天停止成长。

### 批量种植、浇水、收获

当前实现把多格农田动作视为多次实际劳动：

```text
plant(crop=potato, quantity=9) -> 种 9 格，Energy -45
water(plot=all)                -> 按实际干燥作物格数扣 Energy
harvest(plot=all)              -> 按实际成熟作物格数扣 Energy
```

如果 LLM 输出 `plant(crop=potato)` 且没有提供 `plot`，环境会尽可能把当前可用种子种到空地里，
并按实际种下的格数扣 Energy。确定性 Agent 仍可通过 `plot=1` 等参数进行单格种植。

## 7. 作物

| 作物 | 种子 | 种子价格 | 生长天数 | 售价 | 说明 |
| --- | --- | ---: | ---: | ---: | --- |
| Turnip | turnip_seed | 20 | 3 | 45 | 快速回本 |
| Potato | potato_seed | 35 | 5 | 90 | 中等收益 |
| Tomato | tomato_seed | 60 | 7 | 80 | 成熟后可再生长 |
| Pumpkin | pumpkin_seed | 100 | 9 | 260 | 高投入高收益 |

## 8. 天气与随机事件

天气：

| 天气 | 效果 |
| --- | --- |
| Sunny | 正常 |
| Rainy | 农田自动浇水 |
| Storm | 农田自动浇水，Mine 和 River 关闭 |

随机事件：

| Event | 效果 |
| --- | --- |
| Merchant | 商店随机物品打折 |
| Mine Collapse | Mine 当天关闭 |
| Rich Ore | Mine 资源产出增加 |
| Crop Disease | 随机作物当天停止成长 |

Storm 已合并到天气系统，不再作为 daily event 出现。

## 9. Forest 采集

Forest 可采集，当前不设置每日次数上限，只受 Energy 限制：

| 资源 | 每次数量 | Energy | 用途 |
| --- | ---: | ---: | --- |
| Wood | 1-3 | 10 | Craft、出售、Quest |
| Berry | 1-2 | 10 | 恢复 HP、Craft Potion |
| Herb | 1 | 10 | Craft Potion |
| Wild Flower | 1 | 10 | 出售 |

同一天可以重复采集同一种资源，直到 Energy 不足。

## 10. Mine 与战斗

Mine 使用 `mine()` 推进资源获取和矿洞深度。

| Level | 内容 |
| --- | --- |
| 1 | Stone、Copper |
| 2 | Copper、Iron、Goblin |
| 3 | Iron、Crystal、Guardian |

Iron Pickaxe 会把 `mine` 的 Energy 消耗从 15 降到 9。

战斗动作：

```text
fight(action=fight)
fight(action=escape)
fight(action=use_potion)
```

武器：

| 武器 | 效果 |
| --- | --- |
| 无武器 | 低伤害 |
| Wooden Sword | 中等伤害 |
| Iron Sword | 高伤害 |

Guardian 需要 Ancient Key，并且通常需要 Iron Sword 和足够矿洞进度。

## 11. River 捕鱼

`fish()` 只能在 River 使用。Storm 时 River 关闭。

| 结果 | 概率 | 售价 |
| --- | ---: | ---: |
| Small Fish | 60% | 20 |
| Big Fish | 25% | 50 |
| Trash | 15% | 0 |

Big Fish 可用于 `Q_BIG_FISH_2`，完成后获得 Ancient Key。

## 12. 商店与物品

Town 可买种子、食物、材料和 Ancient Key，也可出售资源和作物。

消耗品只恢复 HP：

| 物品 | 效果 |
| --- | ---: |
| Berry | HP +5 |
| Bread | HP +15 |
| Cooked Fish | HP +25 |
| Potion | HP +40 |

消耗品不恢复 Energy。

## 13. Craft

当前核心配方：

| 物品 | 材料 / 花费 | 效果 |
| --- | --- | --- |
| Wooden Sword | Wood x5 | 提升战斗能力 |
| Iron Sword | Wood x3, Iron x2 | 大幅提升战斗能力 |
| Potion | Herb x2, Berry x1 | HP 恢复道具 |
| Sprinkler | Copper x2, Iron x1 | 每天自动浇 1 格 |
| Iron Pickaxe | Iron x3, Gold x150 | 降低 mine Energy 消耗 |

## 14. Guild Quest

`Q_*` 是环境内置 Guild 支线任务，不是前端输入框中的主任务。

| Quest | 要求 | 奖励 | 截止 |
| --- | --- | --- | --- |
| `Q_WOOD_8` | 提交 Wood x8 | Gold +150 | Day 5 |
| `Q_POTATO_3` | 提交 Potato x3 | Gold +250 | Day 8 |
| `Q_GOBLIN_2` | 击败 Goblin x2 | Iron x2 | Day 14 |
| `Q_BIG_FISH_2` | 提交 Big Fish x2 | Ancient Key x1 | Day 14 |

流程：

```text
move(guild)
accept_quest(quest_id)
满足 requirements
move(guild)
submit_quest(quest_id)
```

接取和提交任务各消耗 2 Energy。

## 15. Tool Surface

当前 Tool 固定为：

```text
move(location)
plant(crop, plot?, quantity?)
water(plot)
harvest(plot)
forage(resource)
mine()
fish()
craft(item)
trade(action, item, quantity)
accept_quest(quest_id)
submit_quest(quest_id)
use_item(item)
fight(action)
inspect(target)
rest()
```

所有 Tool 都必须由 Environment 校验。Agent 不能直接修改状态。

## 16. LLM 每日动作链

实时运行中，LLM 每次为“当前游戏日”输出动作链，而不是只输出一步。

Runner 执行顺序：

```text
读取当前 observation
请求 LLM plan_day
逐条执行 actions
每一步记录 trace
如果某一步失败，把 recovery_context 返回给 LLM
LLM 从当前状态重新规划当天剩余动作
```

前端“当前动作链”和“轨迹回放”会展示每一步：

- 状态
- 动作
- 理由
- 结果
- 错误
- 体力变化
- 位置
- 金币
- 剩余体力

## 17. 命令行 Benchmark

命令行 Benchmark 用于观察 Agent 在多个 episode / seed 下的稳定性。

当前前端已不再提供“批量评估”页签。Benchmark 仍可通过脚本运行：

```powershell
python scripts\run_benchmark.py
```

评估指标：

- 成功率
- 平均步数
- 无效动作比例
- 平均延迟
- token 使用
- 估算成本

生成的日志可以在“轨迹回放”页面的历史日志区按 `Day n` 查看每日动作链。
