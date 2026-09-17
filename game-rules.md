# HarvestAgent World

### 一个面向 LLM Agent 长程规划与动态决策的轻量农场经营环境

核心目标不是“模拟一个完整农场游戏”，而是制造这样的决策：

> 我今天只有有限体力，到底应该浇水、挖矿、采集还是赚钱？
> 明天下雨，还要不要今天花体力浇水？
> 商店后天涨价，是现在买种子还是先升级工具？
> 为了完成 7 天后的任务，现在应该如何安排资源？

这才真正适合 Agent。

---

# 一、最核心的游戏循环

游戏按照“天”运行。

每一天：

```text
06:00 起床
    ↓
查看天气 / 状态 / 任务
    ↓
Agent 制定当天计划
    ↓
执行若干 Action
    ↓
体力、时间逐渐消耗
    ↓
18:00 前返回农场
    ↓
结算作物 / 事件 / 金钱
    ↓
进入下一天
```

完整 Episode 暂定：

> **14 天**

这样既能够出现长期规划，又不会一次测试耗费过多 Token。

---

# 二、玩家核心状态

第一版只保留 7 个状态：

| 状态        |   初始值 | 作用         |
| --------- | ----: | ---------- |
| HP        |   100 | 矿洞战斗       |
| Energy    |   100 | 执行动作       |
| Gold      |   500 | 购买种子、食物、工具 |
| Day       |     1 | 游戏时间       |
| Time      | 06:00 | 当天时间       |
| Location  |  Farm | 所在地点       |
| Inventory |  若干物品 | 保存资源       |

另外增加：

```text
FarmState
```

专门记录农田：

```text
Plot 1:
crop = turnip
growth = 2/4
watered = true
```

---

# 三、地图

第一版只需要 **6 个地点**。

| 地点        | 主要功能        |
| --------- | ----------- |
| 🏡 Farm   | 种植、浇水、收获、休息 |
| 🏪 Town   | 商店、出售商品     |
| 🌲 Forest | 木材、野果、草药    |
| ⛏ Mine    | 石头、铜矿、铁矿、战斗 |
| 🌊 River  | 简化捕鱼        |
| 🏛 Guild  | 接任务、领取奖励    |

移动消耗：

```text
30分钟
2 Energy
```

Farm → Town / Forest：

```text
30分钟
```

Mine 距离较远：

```text
60分钟
5 Energy
```

不需要真正做 Grid Map。

Agent只调用：

```python
move("mine")
```

---

# 四、每天的时间规则

一天从：

```text
06:00
```

开始。

到：

```text
18:00
```

结束。

超过：

```text
20:00
```

仍未休息：

```text
Energy -30
第二天初始 Energy -20
```

超过：

```text
22:00
```

强制结束当天。

这样 Agent 会面对：

> “要不要再挖一次矿？”

这种决策。

---

# 五、Energy 规则

每天：

```text
100 Energy
```

动作消耗：

| Action | Energy |       时间 |
| ------ | -----: | -------: |
| 移动     |    2~5 | 30~60min |
| 清理农田   |      5 |    30min |
| 播种     |      2 |    20min |
| 浇水     |  3 / 格 |    20min |
| 收获     |  2 / 格 |    20min |
| 砍木材    |      8 |    40min |
| 野外采集   |      5 |    30min |
| 挖矿     |     10 |    40min |
| 捕鱼     |      8 |    40min |
| 战斗     |      8 |    20min |
| Craft  |      3 |    20min |

Food 可以恢复 Energy。

例如：

```text
Berry
Energy +10

Bread
Energy +25

Cooked Fish
Energy +35
```

---

# 六、农场系统

建议农田只有：

> **9 格**

也就是：

```text
□ □ □
□ □ □
□ □ □
```

足够产生资源管理问题。

不要做几十格。

---

# 七、作物系统

第一版只设计 **4 种作物**。

| 作物         | 种子价格 | 生长 |    售价 | 特征     |
| ---------- | ---: | -: | ----: | ------ |
| Turnip 萝卜  |   20 | 3天 |    45 | 快速     |
| Potato 土豆  |   35 | 5天 |    90 | 中等收益   |
| Tomato 番茄  |   60 | 7天 | 80×多次 | 长期收益   |
| Pumpkin 南瓜 |  100 | 9天 |   260 | 高投入高收益 |

这里开始出现 Agent 决策。

比如当前：

```text
Day = 8
Episode Day = 14
```

南瓜：

```text
9天成熟
```

所以：

> 第 8 天再买南瓜已经无法在 Episode 结束前成熟。

Agent应该意识到这一点。

这就是：

**Temporal Planning。**

---

# 八、浇水规则

作物每天需要：

```text
water()
```

如果当天没有浇：

```text
当天不增长
```

但是不死亡。

这样降低环境复杂度。

例如：

```text
Tomato

Day1 ✓
Day2 ✓
Day3 ✗
Day4 ✓
```

生长进度只有：

```text
3天
```

而不是4天。

---

# 九、天气系统

每天早上公布：

```text
Sunny
Rainy
Storm
```

概率例如：

```text
Sunny 65%
Rainy 25%
Storm 10%
```

### Sunny

正常。

### Rainy

农作物自动浇水。

意味着：

```text
今天不用花 Energy 浇水
```

Agent可以把体力用来：

```text
Mine
Forest
Fishing
```

### Storm

农作物自动浇水。

但是：

```text
Mine Closed
River Closed
```

这会直接破坏原计划。

例如 Agent：

```text
Day 5计划：
去 Mine 获得 Copper
```

结果：

```text
Storm
Mine unavailable
```

必须 Replanning。

这非常适合你的 Agent。

---

# 十、天气预报

有一个很重要的设计：

> Agent 可以看到**第二天的天气预报**。

例如：

```text
Today:
Sunny

Tomorrow:
Rainy
```

这会产生提前规划。

Agent可能：

> 明天下雨，不需要浇水，所以明天适合安排一整天矿洞。

这样 Planning 才不是只看当前状态。

---

# 十一、Forest 系统

Forest 提供：

| 资源          | 每次获得 | 用途     |
| ----------- | ---: | ------ |
| Wood        |  1～3 | Craft  |
| Berry       |  1～2 | Energy |
| Herb        |    1 | Potion |
| Wild Flower |    1 | 出售     |

资源每天有限。

例如：

```text
Wood:
最多采 3 次

Berry:
最多采 2 次
```

第二天刷新。

---

# 十二、Mine 系统

Mine 不要做真正的层数地图。

改成：

```text
Mine Level
```

例如：

```text
Level 1
Level 2
Level 3
```

进入更深层需要累计探索。

### Level 1

```text
Stone
Copper
```

### Level 2

```text
Copper
Iron
Goblin
```

### Level 3

```text
Iron
Crystal
Guardian
```

每次：

```python
mine()
```

环境随机返回资源。

例如：

```json
{
  "stone": 2,
  "copper": 1
}
```

---

# 十三、矿洞战斗

保持极度简单。

例如：

### Slime

```text
HP = 20
Damage = 5
Reward = 10 Gold
```

### Goblin

```text
HP = 40
Damage = 12
Reward = 25 Gold
```

玩家武器：

| 武器           | Damage |
| ------------ | -----: |
| 无武器          |      5 |
| Wooden Sword |     15 |
| Iron Sword   |     30 |

Agent只需要决定：

```text
fight
escape
use potion
```

不要做技能系统。

---

# 十四、River 捕鱼

钓鱼不要做小游戏。

直接：

```python
fish()
```

消耗：

```text
8 Energy
40min
```

结果随机：

```text
Small Fish    60%
Big Fish      25%
Trash         15%
```

售价：

```text
Small Fish 20G
Big Fish   50G
```

作用主要是：

> 给 Agent 提供另一条赚钱路线。

于是获得 100 Gold 不再只有一种解。

---

# 十五、商店

商店出售：

| 商品           | Price |
| ------------ | ----: |
| Turnip Seed  |    20 |
| Potato Seed  |    35 |
| Tomato Seed  |    60 |
| Pumpkin Seed |   100 |
| Bread        |    30 |
| Potion       |    60 |
| Copper       |    50 |
| Iron         |   100 |

这样：

> Iron 可以自己挖，也可以买。

这是非常关键的设计。

例如 Agent缺：

```text
Iron ×2
```

有两种路线：

```text
去 Mine
Energy成本低金钱成本
```

或者：

```text
赚钱
→ 购买 Iron
```

这样才产生真正的策略。

---

# 十六、出售系统

商品可以卖给 Town Shop。

例如：

| Item        | Sell |
| ----------- | ---: |
| Wood        |   10 |
| Berry       |    8 |
| Wild Flower |   20 |
| Copper      |   35 |
| Iron        |   70 |
| Small Fish  |   20 |
| Big Fish    |   50 |

作物也可以出售。

---

# 十七、Craft 系统

MVP 只需要 5 个配方。

### Wooden Sword

```text
Wood ×5
```

### Iron Sword

```text
Wood ×3
Iron ×2
```

### Potion

```text
Herb ×2
Berry ×1
```

### Energy Snack

```text
Berry ×2
```

恢复：

```text
Energy +25
```

### Sprinkler

这是我非常推荐加入的东西：

```text
Copper ×2
Iron ×1
```

作用：

> 每天自动给一格农田浇水。

这会产生非常漂亮的长期投资决策。

---

# 十八、为什么 Sprinkler 特别适合 Agent？

例如：

```text
剩余10天
```

Agent可以：

### Strategy A

每天：

```text
手动浇水
Energy -18
```

### Strategy B

前期：

```text
挖 Copper + Iron
↓
Craft Sprinkler
```

之后每天节省：

```text
Energy
```

这是典型的：

> **短期投入换长期收益。**

非常适合测试长程 Planning。

---

# 十九、工具升级

为了控制工作量，只做：

```text
Pickaxe
```

两个等级：

```text
Basic Pickaxe
Iron Pickaxe
```

升级需要：

```text
Iron ×3
Gold ×150
```

效果：

```text
mine Energy:
10 → 6
```

于是 Agent需要判断：

> Episode只剩3天了，还有必要升级吗？

也是长期收益问题。

---

# 二十、任务系统

Guild 每局随机提供一些任务。

比如：

### Quest A

```text
在 Day 5 前提交：

Wood ×8

奖励：
150 Gold
```

### Quest B

```text
在 Day 8 前：

Potato ×3

奖励：
250 Gold
```

### Quest C

```text
击败 Goblin ×2

奖励：
Iron ×2
```

### Quest D

```text
提交：
Big Fish ×2

奖励：
Ancient Key
```

Agent需要决定：

> 这个任务值不值得接？

不是所有任务都应该完成。

---

# 二十一、主线任务

一个 Episode 给 Agent一个主要 Goal。

建议有 5 种。

### Goal 1

```text
Day 6前赚到1000 Gold
```

### Goal 2

```text
Day 8前制作 Iron Sword
```

### Goal 3

```text
Day 10前收获3个 Potato
```

### Goal 4

```text
Day 12前获得 Ancient Key
```

### Goal 5

最终综合任务：

> **在 Day 14 前获得 Ancient Key、Iron Sword，并击败 Mine Guardian。**

---

# 二十二、最终任务的多条解法

这是非常关键的。

例如 Ancient Key 有两种获取方法。

### 路线 A

商店购买：

```text
500 Gold
```

### 路线 B

完成：

```text
Big Fish ×2
```

的 Guild Quest。

Iron Sword 也有两种方式。

### 路线 A

```text
自己去 Mine
获得 Iron
```

### 路线 B

```text
赚钱
→ Shop购买 Iron
```

Potion：

```text
自己 Craft
```

或者：

```text
Shop购买
```

因此不会出现唯一正确攻略。

---

# 二十三、每日随机事件

数量一定不要太多。

第一版 5 种足够：

| Event         | 效果             |
| ------------- | -------------- |
| Storm         | Mine / River关闭 |
| Merchant      | 随机物品打折         |
| Mine Collapse | Mine当天关闭       |
| Rich Ore      | Mine资源×2       |
| Crop Disease  | 随机作物当天停止生长     |

概率控制在：

```text
每天约20%出现事件
```

主要目的：

> **破坏 Agent 的静态计划。**

---

# 二十四、市场价格变化

这是一个可选但很有价值的机制。

例如：

```text
Day 1~4
Potato: 90

Day 5~9
Potato: 110

Day 10~14
Potato: 70
```

Agent可以提前获得：

```text
Market Forecast
```

但第一版如果担心复杂，可以不做。

建议 V1.1 再加入。

---

# 二十五、Agent每天应该收到什么？

非常重要。

不要把整个世界所有状态都塞过去。

每天开始时给：

```text
Day 6 / 14

Weather:
Sunny

Tomorrow:
Rainy

HP:
82

Energy:
100

Gold:
240

Location:
Farm

Inventory:
Wood ×3
Copper ×2
Potato ×1

Farm:
Turnip ×2 (2/3 days)
Potato ×3 (4/5 days)

Active Quest:
Deliver Potato ×3 before Day 8

Main Goal:
Defeat Guardian before Day 14
```

然后 Agent决定。

---

# 二十六、Agent可以使用的 Tool

第一版控制在：

```python
move(location)

plant(crop)

water(plot)

harvest(plot)

forage(resource)

mine()

fish()

craft(item)

trade(action, item, quantity)

use_item(item)

fight(action)

rest()
```

12 个 Tool 左右。

比我们之前的版本稍多，但这个游戏的策略空间也会明显更丰富。

---

# 二十七、Agent看不到哪些东西？

这是很重要的。

Agent不能直接访问：

```text
随机数
明天以后的天气
隐藏事件
未来矿洞掉落
```

只能通过：

```text
Observation
```

获取。

否则 Agent拥有全知信息，就没有真正决策意义了。

---

# 二十八、行动失败

例如：

```python
plant("pumpkin")
```

但：

```text
Pumpkin Seeds = 0
```

环境返回：

```json
{
  "success": false,
  "error": "NO_SEED",
  "observation": "You do not have Pumpkin Seeds."
}
```

仍然消耗少量：

```text
5 minutes
```

但不扣 Energy。

这样可以统计：

> Invalid Action Rate。

---

# 二十九、一天结束规则

Agent可以主动：

```python
rest()
```

结束当天。

如果：

```text
Energy <= 0
```

自动回 Farm。

惩罚：

```text
次日最大Energy = 70
```

如果正常睡觉：

```text
次日Energy = 100
```

这可以防止 Agent 无脑榨干体力。

---

# 三十、死亡规则

如果：

```text
HP <= 0
```

不要直接 Episode 失败。

更像轻量农场游戏：

```text
返回 Farm
Gold -10%
当天结束
```

但是如果最终任务超过 Deadline：

```text
Episode Failed
```

这样不会因为一次战斗随机性毁掉所有评测。

---

# 三十一、最终整个世界的资源循环

这一部分设计得比较重要。

```text
             Farming
            ↗       ↘
       Seeds          Crops
         ↑               ↓
       Gold ←──────── Sell
         ↑
         │
       Sell
      ↗     ↖
 Forest     Fishing
   ↓
 Wood/Herb
   ↓
 Craft
   ↓
Potion / Equipment
            ↑
            │
          Mine
            ↓
       Copper / Iron
            ↓
      Tools / Weapon
            ↓
        Guardian
```

这样游戏中的系统不是彼此孤立的。

Agent可以自己寻找资源路径。

---

# 三十二、一个完整案例

例如当前：

```text
Day 7

Goal:
Day 14前击败 Guardian

Current:

Gold: 220

Wood ×4
Iron ×0
Copper ×1

Potato ×2
Big Fish ×1

HP: 100
```

需要：

```text
Iron Sword
+
Ancient Key
```

Agent可能制定：

```text
Plan:

1. 明天是 Rainy
2. 不需要浇农田
3. 去 Mine 一整天
4. 收集 Iron
5. Craft Iron Sword
6. 继续捕鱼获得第二条 Big Fish
7. 完成 Guild Quest
8. 获得 Ancient Key
9. 准备 Potion
10. 进入 Mine Level 3
```

第二天：

```text
Storm
```

Mine关闭。

于是：

```text
Plan Failed
```

Agent重新规划：

```text
既然 Mine关闭：

今天去 River
→ 捕鱼
→ 完成 Big Fish Quest
→ 获得 Ancient Key

明天再处理 Iron Sword
```

这就是你想展示的 Agent。

---

# 三十三、为什么这一版比最开始的生存游戏更适合

最开始：

```text
Wood
→ Iron
→ Sword
→ Key
→ Ruins
```

其实有一点容易变成：

> 固定解谜。

现在加入轻量农场经营以后，就有：

```text
时间
+
Energy
+
Gold
+
Crop
+
天气
+
采集
+
矿洞
+
商店
+
Quest
+
Craft
```

于是同一个目标会存在多种策略。

Agent必须做的是：

> **Resource Allocation + Temporal Planning + Dynamic Replanning**

而不是记攻略。

---

# 三十四、但一定要控制复杂度

虽然参考农场经营游戏，但我建议 V1 固定为：

| 系统           |  V1规模 |
| ------------ | ----: |
| 地点           |     6 |
| 农田           |    9格 |
| 作物           |    4种 |
| 矿物           |    3种 |
| 野外资源         |    4种 |
| 武器           |    2种 |
| 食物/药物        |    3种 |
| Craft        |    5种 |
| Enemy        |    3种 |
| Quest        | 5～8模板 |
| Random Event |    5种 |
| Episode      |   14天 |

我认为这是比较合适的上限。

---

# 三十五、第一版甚至可以进一步砍掉

真正开发的时候，我建议 **V0.1** 先只有：

```text
Farm
Town
Forest
Mine
```

作物只有：

```text
Turnip
Potato
```

资源：

```text
Wood
Copper
Iron
```

再有：

```text
Energy
Gold
Weather
Shop
Craft
```

先让 Agent完成：

> **Day 10 前制作 Iron Sword，并赚到 500 Gold。**

只要这个跑通，就说明核心 Environment 已经成立。

之后再加入：

```text
Fishing
Quest
Guardian
Ancient Key
Sprinkler
```

这样开发风险会小很多。

---

## 最终建议的项目规则核心

你可以把项目的玩法总结成一句话：

> **Agent 在一个 14 天的轻量农场经营世界中，通过种植、采集、挖矿、捕鱼、交易和制作管理有限的时间、体力和金钱，并根据天气及随机事件动态调整计划，最终完成具有多种资源获取路线的长期任务。**

相比纯粹模仿《星露谷物语》，这套规则刻意保留了**经营、每日循环、资源生产和不同赚钱方式**，同时把大量与 Agent 研究无关的复杂系统删除掉了。

下一步最适合做的是把这套规则进一步冻结成一份**可直接编码的 Environment Specification**：我可以继续给你写出每一种物品、价格、掉落概率、作物成长状态、天气概率、`GameState` 数据结构以及 12 个 Tool 的精确定义，这样下一步就可以正式开始写 Python 了。
