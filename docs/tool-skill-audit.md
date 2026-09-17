# Tool / Skill 必要性审计

本文档记录当前 Agent 的动作边界和 Skill 边界。

## Tool Surface

当前 Tool surface 固定为 15 个。

| Tool | 必要程度 | 当前用途 |
| --- | --- | --- |
| `move` | 必须保留 | 所有跨地点行动都依赖移动。 |
| `plant` | 必须保留 | Farming 任务和赚钱路线需要种植；支持按地块批量种植。 |
| `water` | 必须保留 | 作物成长需要浇水；`water(plot=all)` 按实际干燥作物格数扣 Energy。 |
| `harvest` | 必须保留 | Farming 成功条件和销售路线依赖收获；`harvest(plot=all)` 按成熟格数扣 Energy。 |
| `forage` | 必须保留 | 木材、野果、草药、野花来自森林采集。 |
| `mine` | 必须保留 | 铁资源、矿洞深度、Guardian 路线依赖挖矿。 |
| `fish` | 必须保留 | Big Fish Quest 和替代赚钱路线依赖捕鱼。 |
| `craft` | 必须保留 | Iron Sword、Potion、Sprinkler、Iron Pickaxe 依赖制作系统。 |
| `trade` | 必须保留 | 种子、材料、钥匙、售卖商品都依赖 Town Shop。 |
| `accept_quest` | 必须保留 | Guild 任务必须先正式接取。 |
| `submit_quest` | 必须保留 | Guild 任务满足要求后必须提交领取奖励。 |
| `use_item` | 必须保留 | 消耗品只恢复 HP，不恢复 Energy。 |
| `fight` | 必须保留 | 敌人遭遇和 Guardian 目标依赖战斗。 |
| `inspect` | 支持保留 | 信息不足时可查看 state、farm、shop、recipes、weather、quests、goal。 |
| `rest` | 必须保留 | 唯一 Energy 恢复路径，并推进到下一天。 |

旧版 `gather` 兼容别名已删除，统一使用 `forage`。

## Skill Surface

当前第一阶段 Skill surface 为 7 个。

| Skill | 必要程度 | 当前用途 |
| --- | --- | --- |
| Resource Acquisition | 必须保留 | 统一处理木材、铁、钥匙、鱼类资源和武器材料获取。 |
| Farming Cycle | 必须保留 | 封装买种子、种植、浇水、休息、收获。 |
| Fishing Route | 必须保留 | 让 `fish` 在 Big Fish Quest 和赚钱路线中有稳定入口。 |
| Money Making | 必须保留 | 封装作物销售和森林采集销售的赚钱路线。 |
| Combat Preparation | 必须保留 | 处理钥匙、武器、矿洞深度、遭遇敌人和 Guardian 战斗。 |
| Recovery | 必须保留 | 封装 HP 消耗品和 rest 决策。 |
| Quest Completion | 必须保留 | 封装 Guild 接任务、补齐要求、提交任务和领取奖励。 |

Skill 不新增环境动作，只返回 Tool-compatible decision。

## Quest 机制

`Q_*` 是环境内置 Guild 支线任务，不是前端输入框中的主任务。

当前任务：

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
领取 rewards
```

`accept_quest` 和 `submit_quest` 各消耗 2 Energy。

## LLM Day Plan

实时运行中的 `llm` Agent 使用每日动作链，而不是单步决策。

LLM 输出格式：

```json
{
  "day_objective": "当天目标",
  "reasoning": "规划原因",
  "actions": [
    {"tool": "plant", "args": {"crop": "potato", "quantity": 9}, "reason": "种植九块地"}
  ],
  "final_day_actions": "今日行动：..."
}
```

Runner 会逐条执行 `actions`。如果中途失败，会把当天已成功步骤、失败动作、错误和当前状态
回传给 LLM，由 LLM 在当前进度上重新规划当天剩余动作。

## 当前保留结论

不建议继续增加新 Tool。

如果后续需要扩展能力，优先方式是：

```text
新增或调整 Skill / Prompt / Runner 策略
而不是扩大 Tool surface
```

当前 15 个 Tool 已经覆盖主线目标、支线任务、经济路线、战斗路线和前端实时运行需求。
