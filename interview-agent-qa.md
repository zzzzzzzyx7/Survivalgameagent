# SurvivalAgent 面试问答参考

本文档用于把 SurvivalAgent 作为简历项目讲给 Agent 相关岗位的面试官。回答默认采用“候选人本人”的口吻，可以按实际贡献范围适当删改。

## 30 秒项目介绍

SurvivalAgent 是我做的一个轻量级 Agent Benchmark 项目。它模拟了一个受规则约束的生存经营游戏环境，让 Agent 在 14 天 episode 内完成赚钱、种植、制作铁剑、获得 Ancient Key、击败 Guardian 等任务。

这个项目的重点不是游戏本身，而是把 `Agent`、`Environment`、`Tool`、`Skill`、`Evaluation` 和 `Trace` 拆开。Agent 只能输出结构化 tool 调用，真实状态只能由环境层校验后更新。这样可以比较不同 Agent 策略，比如 direct、ReAct、planner、planner with replanning 和 LLM day-planning agent，并用 success rate、invalid action rate、steps、token、latency、cost、failure category 等指标评估。

我希望用它展示三件事：第一，能设计一个可控的 Agent 实验环境；第二，能处理 tool calling、规划、重规划、记忆和评测闭环；第三，能把 Agent 的运行过程通过 trace 和 Streamlit UI 可视化出来，方便调试与复盘。

## 一、项目定位与架构

### Q1：这个项目一句话怎么概括？

可以回答：

这是一个用于研究 LLM Agent 在规则环境中自主规划和执行的 benchmark 框架。它不是纯 prompt demo，而是把环境状态、工具调用、规划策略、运行日志和评测指标都工程化了。

追问要点：

- 核心边界是 `Agent -> Tool decision -> Environment validation -> Observation/Trace`。
- Agent 不能直接改金币、体力、背包、装备等状态。
- 评测 runner 用固定任务和 seed 做可重复比较。

### Q2：为什么选择游戏环境做 Agent 项目？

可以回答：

因为游戏环境兼具可控性和复杂性。它有明确状态、动作、资源约束、长期目标、随机事件和失败反馈，适合验证 Agent 是否真的会规划，而不仅是生成文本。相比真实业务系统，游戏环境风险更低，但能覆盖很多 Agent 核心问题，比如工具选择、状态理解、资源管理、长程规划、失败恢复和评测。

追问要点：

- 资源约束：Energy、HP、Gold、Inventory。
- 长程目标：14 天内完成任务。
- 不确定性：天气、随机事件、钓鱼、挖矿掉落、敌人遭遇。
- 可评测：成功率、步数、无效动作率。

### Q3：整体架构怎么分层？

可以回答：

项目主要分为五层：

1. `app.environment`：唯一真实状态来源，负责规则校验和状态更新。
2. `app.tools`：薄封装，把结构化 tool 调用转给环境。
3. `app.skills`：高层能力，把目标路线拆成 tool-compatible decision。
4. `app.agents`：不同决策策略，包括 direct、ReAct、planner、replanning、LLM。
5. `evaluation` 和 `frontend`：分别负责 benchmark、trace、指标，以及 Streamlit 可视化。

这个分层的关键是依赖方向清晰。环境层不依赖 agent、frontend 或 evaluation，避免 Agent 绕过规则直接改状态。

### Q4：为什么强调 Environment 是唯一真实状态来源？

可以回答：

Agent 项目里一个常见问题是模型“说它完成了”，但系统状态并没有真的变化。这个项目把所有状态变更都放在环境层，Agent 只能提交结构化动作，比如 `move`、`trade`、`mine`、`craft`。环境会检查位置、资源、体力、天气、任务条件，然后返回 `ActionResult`。这样 trace 里的成功不是文本承诺，而是由环境状态验证出来的。

追问要点：

- 防止 LLM hallucination 直接污染状态。
- 让不同 Agent 可以在同一环境里公平比较。
- 方便定位错误属于规划错误、参数错误还是环境约束没满足。

### Q5：一次运行的数据流是什么？

可以回答：

一次 episode 里，runner 先创建 task 和 game，再创建对应 agent。每一步或每天，runner 把 `game.observe()` 得到的 observation 传给 Agent。Agent 输出 decision 或 day plan，runner 调用 `_execute_decision`，环境执行并返回 `ActionResult`。然后 runner 记录 `state_before`、`decision`、`result`、`state_after`、latency 和 token usage。episode 结束后写 trace，计算指标，并可把 reflection lesson 写入 memory。

## 二、Tool、Skill 与状态设计

### Q6：项目有哪些 Tool？为什么固定成 15 个？

可以回答：

当前 Tool surface 固定为 15 个：`move`、`plant`、`water`、`harvest`、`forage`、`mine`、`fish`、`craft`、`trade`、`accept_quest`、`submit_quest`、`use_item`、`fight`、`inspect`、`rest`。

我刻意不让 Tool 无限膨胀。Tool 应该是环境动作边界，保持低层、稳定、可校验；更复杂的能力放到 Skill 或 Agent 策略里。这样可以避免每遇到一个新目标就新加工具，导致工具面不可控。

### Q7：Tool 和 Skill 的区别是什么？

可以回答：

Tool 是原子动作，比如移动、交易、挖矿、休息。它只负责执行或失败，不负责策略。Skill 是高层能力，比如 Resource Acquisition、Farming Cycle、Money Making、Combat Preparation，它会根据当前 observation 和 goal 选择下一步调用哪个 Tool。

简单说，Tool 是“能做什么”，Skill 是“为了目标下一步该怎么做”。

### Q8：为什么需要 Skill 层，而不是直接让 LLM 调 Tool？

可以回答：

Skill 层有两个价值。第一，它给非 LLM baseline 提供可复用策略，方便和 LLM 做对照。第二，它把领域知识模块化，比如赚钱、种植、战斗准备，这些逻辑可以被 direct、planner 和 replanning agent 复用。实际工程里，纯 LLM tool calling 容易受 prompt 波动影响，Skill 相当于把确定性业务流程固化下来。

### Q9：`inspect` 这个工具为什么要单独设计？

可以回答：

`inspect` 用来在信息不足时查看 state、farm、shop、recipes、weather、quests、goal 等信息。它很有用，但也容易让 Agent 陷入反复查看、不行动的循环。所以项目里 Skill 是否允许主动 `inspect` 由 `SURVIVAL_AGENT_SKILLS_ALLOW_INSPECT` 控制，LLM prompt 里也要求不要重复最近已经执行过的 inspect。

### Q10：游戏状态里最关键的字段有哪些？

可以回答：

核心状态在 `GameState` 里，包括 day、step、hp、energy、gold、location、weather、inventory、equipment、farm、quests、world_state、goal、done 和 success。这里面我最关注三类状态：

- 资源状态：Energy、HP、Gold、Inventory。
- 世界状态：天气、随机事件、mine level、pending enemy。
- 目标状态：goal、deadline、success condition。

这些字段共同决定 Agent 的动作是否合法，以及是否完成目标。

## 三、Agent 设计

### Q11：你实现了哪些 Agent？

可以回答：

项目里有几类 Agent：

1. `direct`：确定性规则策略，根据目标和 observation 直接选下一步 tool。
2. `react`：在 direct decision 上增加 thought/reason，用于模拟 ReAct 风格的可解释决策。
3. `planner`：先生成固定 subgoal plan，再逐步执行。
4. `planner_replanning`：基于 LangGraph，把 progress checker、planner、replanner、executor 串成工作流。
5. `llm`：调用 OpenAI-compatible 接口，要求模型输出结构化 JSON day plan。
6. `scripted`：测试和验收用的任务脚本策略。

### Q12：Direct Agent 的意义是什么？

可以回答：

Direct Agent 是一个 deterministic baseline。它没有模型成本，也没有 prompt 不稳定性，能验证环境规则和任务路线本身是否可解。同时它能作为 LLM Agent 的比较对象，避免只展示一个模型 demo 却不知道效果好坏。

### Q13：ReAct Agent 在这里怎么体现？

可以回答：

这个项目里的 ReAct Agent 不是完整的 LLM ReAct loop，而是在 direct decision 基础上附加 thought/reason。它主要用于把“动作选择”和“推理说明”放进 trace，对比纯动作 baseline 和带推理信息的 baseline。后续如果扩展，可以把它替换成真正的 Thought、Action、Observation 多轮 LLM ReAct。

回答时要诚实说明：

- 当前 ReAct 是轻量实现，不是论文级完整 ReAct。
- 它的价值主要在 trace 可解释性和 baseline 对照。

### Q14：Planner Agent 是怎么规划的？

可以回答：

Planner Agent 先根据目标文本生成 subgoal plan。例如铁剑任务会变成 `obtain_iron -> obtain_wood -> craft_iron_sword`；Guardian 任务会变成 `obtain_ancient_key -> obtain_wood -> mine_iron_and_depth -> craft_iron_sword -> defeat_guardian`。每一步执行时，它会检查哪些 subgoal 已完成，然后把当前 subgoal 交给对应 Skill 生成 tool decision。

### Q15：Planner 和 Replanning 的区别是什么？

可以回答：

普通 planner 生成计划后基本按计划走。`planner_replanning` 会在执行结果或环境状态表明计划被阻塞时修改计划，比如矿洞关闭、storm、资源不足、体力不足、敌人阻塞等。它不是每一步都重新生成计划，而是在 `should_replan` 判断需要时插入 fallback subgoal，例如 `fallback_resource_route` 或 `resolve_enemy`。

### Q16：为什么用 LangGraph？

可以回答：

LangGraph 适合表达有状态、多节点、可分支的 Agent 工作流。这个项目把 replanning agent 拆成 `progress_checker`、`planner`、`replanner`、`executor` 四个节点。这样比一个大函数更容易扩展，例如后续可以增加 critic、memory retriever、tool validator 或 human approval 节点。

追问要点：

- 当前图是轻量工作流，不是复杂多智能体系统。
- 关键价值是把检查、规划、重规划、执行的状态流显式化。

### Q17：LLM Agent 为什么改成“按天规划”而不是单步决策？

可以回答：

单步决策比较稳，但很容易短视，而且每一步都调用模型会增加成本和延迟。按天规划让模型一次性输出当天动作链，比如移动、购买、种植、浇水、休息。Runner 再逐条校验执行。这样更接近长程规划，也能减少调用次数。

不过按天规划也有风险：中途某个动作失败后，后续动作可能都不再适用。所以我在 runner 里加了 `recovery_context`，把已成功步骤、失败动作、错误码和当前状态回传给 LLM，让它基于当前状态重规划当天剩余动作。

### Q18：LLM 的输出格式如何约束？

可以回答：

LLM prompt 要求只返回 JSON，day plan schema 包括 `day_objective`、`reasoning`、`actions` 和 `final_day_actions`。每个 action 必须包含 `tool`、`args`、`reason`，并且 tool 只能来自允许列表或 `stop`。解析时会检查 JSON 类型、actions 数组和 tool 名称，最多取前 8 个动作，避免模型一次计划过长。

### Q19：如果 LLM 输出非法 JSON 怎么办？

可以回答：

当前实现会剥离简单 markdown code fence，然后用 `json.loads` 解析。如果失败，runner 会把它当作 agent planning error 记录到 trace，不会推进游戏内 step。文档里也记录了 `JSONDecodeError` 的排查方式。

如果继续改进，我会加三层容错：JSON 子串提取、schema validation 和一次自动 repair prompt。但我不会让 repair 直接修改环境状态，仍然要经过 tool 执行。

### Q20：怎么防止 LLM 调不存在的工具或乱传参数？

可以回答：

第一层是 prompt 里明确列出 allowed tools 和每个工具参数 schema。第二层是解析时检查 tool 是否在 `ALLOWED_TOOLS`。第三层是 runner 的 `_execute_decision` 把参数转成环境方法调用，如果参数缺失或类型错误，会返回 `INVALID_TOOL_ARGS`，不会崩掉整个 episode。第四层是环境本身做位置、资源、体力、天气等规则校验。

## 四、执行、重规划与错误处理

### Q21：一次 day plan 中途失败时怎么处理？

可以回答：

`run_game_day` 会按顺序执行 LLM 计划里的 actions。如果某一步失败，比如在 farm 直接 `forage`，环境会返回 `WRONG_LOCATION`。runner 会记录这一步，然后构造 `recovery_context`，里面包含当天已执行步骤、失败动作、错误信息、当前状态和上一版计划。然后再次调用 `plan_day`，要求 LLM 保留已成功步骤，只修改当天剩余动作。

### Q22：为什么失败动作会推进 step，但 LLM 请求失败不推进 step？

可以回答：

这是刻意区分“游戏内动作失败”和“Agent 决策失败”。如果 Agent 做了非法动作，比如位置错误或资源不足，这属于游戏内尝试，应该推进 step 并计入 invalid action。反过来，如果模型接口超时或 JSON 解析失败，那不是角色在游戏世界里采取了动作，所以不应该改变 GameState，只应该记录为 trace 中的 agent error。

### Q23：哪些错误会触发 replanning？

可以回答：

对 planner_replanning，主要关注 `LOCATION_CLOSED`、`INSUFFICIENT_RESOURCES`、`NOT_ENOUGH_ENERGY`、`ENEMY_BLOCKING`。此外，如果当前天气是 storm 且 subgoal 依赖 mine 或 river，也会触发重规划；如果有 pending enemy 且当前目标依赖矿洞，也会插入处理敌人的 subgoal。

### Q24：你怎么处理随机性？

可以回答：

环境内部使用 `random.Random(seed)`，benchmark 传入固定 seeds，比如 1、2、3。这样不同 Agent 在同一任务和 seed 下遇到的随机条件可复现，便于公平比较。随机性包括天气、每日事件、挖矿掉落、钓鱼结果、敌人遭遇等。

### Q25：为什么设定 14 天 episode？

可以回答：

14 天是一个足够长但仍可控的规划窗口。简单任务可以很快完成，复杂任务如 Guardian 需要跨多天积累资源、装备和矿洞进度。前端的自定义中文任务也会被默认放进 14 天 deadline，避免用户没有写截止日期时任务不可评测。

## 五、Memory 与 Reflection

### Q26：Memory 是怎么做的？

可以回答：

Memory 是一个 JSON-backed episode lesson store。episode 结束后，runner 调用 reflection，把经验教训写成 `EpisodeLesson`，包含 episode_id、goal、outcome、lesson、tags。下一次运行时，如果传入 `--memory-path`，runner 会根据 goal 检索相关 lesson，并注入 Agent。

### Q27：Memory 检索用的是什么方法？

可以回答：

当前是简单关键词匹配。它会把 goal、lesson 和 tags 分词，计算 query terms 和 lesson terms 的交集数量，然后取 top-k。这样实现简单、可解释、无外部依赖，适合 MVP。

如果面试官追问缺点，可以补充：

- 它不具备语义检索能力。
- 中文分词能力很弱。
- 后续可以换成 embedding 检索、BM25 或混合检索，并加入 lesson 去重和有效性评估。

### Q28：Reflection 有什么价值？

可以回答：

Reflection 的价值是把一次 episode 的经验沉淀成可复用 lesson，而不是只留原始 trace。比如铁剑任务成功后可以记住“先获得 iron 和 wood，再在 farm 或 town craft”。失败时可以沉淀“不要在没有 Ancient Key 或铁剑时过早挑战 Guardian”。这些 lesson 可以作为下次规划的上下文。

### Q29：你怎么防止错误记忆影响后续决策？

可以回答：

当前版本的防护比较基础：memory 只作为 Agent 输入，不直接修改环境状态；并且检索数量有限，由 `settings.retrieved_memories` 控制。如果要继续增强，我会给 lesson 增加置信度、成功来源、过期机制和任务匹配度阈值，并在 trace 中标出哪些 memory 被使用，方便回溯。

## 六、Evaluation 与 Benchmark

### Q30：你怎么评估 Agent 表现？

可以回答：

Evaluation runner 支持单 episode 和批量 benchmark。指标包括：

- `success_rate`：任务成功率。
- `average_steps`：成功 episode 的平均步数。
- `invalid_action_rate`：无效动作占比。
- `token_usage`：输入、输出和总 token。
- `average_decision_latency_ms`：平均决策延迟。
- `estimated_cost_usd`：按配置价格估算成本。
- `failure_counts`：失败类别统计。

这些指标能同时评价任务效果、行为质量和模型成本。

### Q31：有哪些 benchmark 任务？

可以回答：

项目内置 G01 到 G05：

- G01：14 天内达到 900 Gold。
- G02：14 天内制作 Iron Sword。
- G03：14 天内收获 3 个 Potato。
- G04：14 天内获得 Ancient Key。
- G05：14 天内击败 Guardian。

这些任务覆盖经济路线、农业路线、制作路线、交易路线和战斗路线，复杂度逐步上升。

### Q32：怎么做 baseline 对比？

可以回答：

我会用同一批任务和同一组 seeds 跑 direct、react、planner、planner_replanning、llm。命令行入口是 `scripts/run_benchmark.py`，会输出每个 episode trace 和聚合 summary。这样可以回答三个问题：LLM 成功率是否更高，是否减少无效动作，是否值得额外 token 和 latency 成本。

### Q33：failure category 是怎么来的？

可以回答：

`evaluation.failure_analysis` 会根据 episode 和 trace 做规则分类。比如没有 trace 可能是 planning error；有 invalid actions 会根据错误码分成 resource mismanagement、premature goal attempt、failure to replan 等；如果最后到 deadline 还没成功，就是 deadline missed；如果最后还有 pending enemy，可能是 combat failure。

### Q34：为什么要记录 trace？

可以回答：

Agent 的评测不能只看最后成功与否。Trace 可以看到每一步前后的状态、Agent 决策、环境结果、错误码、day plan 和 latency。它能解释“为什么失败”，也能帮助 debug prompt、skill、环境规则和 UI 展示。

### Q35：当前测试覆盖了什么？

可以回答：

项目有环境规则、Agent、evaluation、memory、frontend helper 和结构检查测试。比如测试 direct/react/planner 能完成 G02，测试多个 Agent 能完成 G01-G05，测试 replanner 遇到矿洞关闭会插入 fallback，测试 LLM day plan 解析和中途失败后的 recovery_context，测试 benchmark summary 和 memory retrieve/store。

本地文档记录的验证结果是 `pytest: 67 passed`、`ruff: All checks passed`。

## 七、Prompt 与 LLM 工程

### Q36：LLM prompt 里放了哪些信息？

可以回答：

prompt 里包含目标、当前 observation、recent history、memories、可用 skills、allowed tools、工具参数说明、day planning rules、energy costs 和 world hints。这样模型既知道当前状态，也知道工具边界和世界规则。

### Q37：为什么在 prompt 里加入 energy costs？

可以回答：

因为这个环境的行动预算主要由 Energy 决定。如果不告诉模型每个动作成本，它很容易计划超过当天体力上限的动作链。把 energy costs 显式放进 prompt，可以让模型在计划时考虑行动预算，比如 water all、plant quantity、harvest all 都需要按地块数量扣体力。

### Q38：recent_history 的作用是什么？

可以回答：

recent_history 保存最近几次执行结果和简化状态。它主要防止模型重复犯同样错误，比如刚 inspect 过 shop 就继续 inspect，或者刚失败过某个动作却不改变状态就重复执行。当前只保留最近 5 条，避免 prompt 无限变长。

### Q39：为什么限制 day plan 最多 8 个动作？

可以回答：

限制动作数是为了控制模型输出长度和错误传播。计划太长时，后面的动作往往建立在前面所有动作成功的假设上，一旦中途失败就整体失效。最多 8 个动作让计划粒度更可控，也配合 runner 的重规划机制。

### Q40：如果换成 OpenAI function calling 或 structured output，会怎么改？

可以回答：

当前是 prompt JSON 加手动解析，优点是简单、兼容 OpenAI-compatible 接口。生产化我会优先改成 structured outputs 或 function calling，把 schema 约束交给模型 API，同时保留环境层二次校验。也就是说，模型输出层更严格，但业务规则仍然不能只相信模型。

## 八、前端与可视化

### Q41：Streamlit UI 做了什么？

可以回答：

UI 主要有两部分：实时运行和轨迹回放。实时运行支持动态输入中文任务、创建新游戏、执行一天、自动运行、停止，并展示当天动作链。轨迹回放可以读取当前 session 的 LLM trace，也可以读取 `logs/` 下历史 benchmark trace，按 Day 展示每一步动作和状态变化。

### Q42：为什么前端不直接使用 G01-G05 JSON？

可以回答：

前端面向交互体验，所以支持用户输入任意任务文本。系统会根据中文或英文关键词推断 success condition，并生成临时 task。G01-G05 JSON 仍然保留给命令行 benchmark 和兼容测试。这样前端更灵活，benchmark 更稳定。

### Q43：前端展示 action chain 有什么调试价值？

可以回答：

它能把模型的“计划”和环境的“执行结果”放在一起看。比如模型计划了 5 个动作，但第 2 个因为位置错误失败，UI 会显示失败动作、错误码、当前状态，以及后续重规划出来的新动作。这样比只看最终失败更容易定位问题。

## 九、工程质量与设计取舍

### Q44：这个项目最重要的工程设计取舍是什么？

可以回答：

我认为最重要的取舍是把环境规则和 Agent 决策彻底隔离。这样写起来会比直接让 Agent 修改状态麻烦，但带来了可测试、可复现、可评测和可解释。Agent 相关项目很容易变成不可验证的 prompt demo，这个项目尽量把它做成一个可运行的实验框架。

### Q45：这个项目最大的难点是什么？

可以回答：

主要难点是长程规划和局部失败的衔接。比如 LLM 一次计划一天动作，如果前面某一步失败，后续动作可能全部失效。为了解决这个问题，我没有让环境自动“猜测修复”，而是把失败信息封装进 recovery_context，让 Agent 基于真实当前状态重新规划。

### Q46：如果面试官问“这不就是规则系统吗”，怎么回答？

可以回答：

这里确实包含规则系统，而且是有意设计的。Agent benchmark 需要一个可验证的环境，如果环境本身不可控，就没法判断 Agent 是否做对了。规则系统在这里扮演 environment 和 baseline 的角色；LLM Agent 的价值体现在它如何在规则边界内做目标分解、动作组合、失败恢复和跨任务泛化。

可以补充：

我不会把 deterministic baseline 说成智能本身。它的作用是标尺。真正要比较的是，在相同环境和任务下，LLM 或 replanning 是否比 baseline 更稳、更少 invalid action，或者能覆盖更多自由文本任务。

### Q47：如果面试官问“为什么不用真实游戏或真实网页环境”？

可以回答：

真实环境更接近产品，但变量太多，难以复现和归因。这个阶段我优先做一个小而完整的封闭环境，把 Agent 的核心闭环跑通，包括 tool calling、planner、replanning、memory、benchmark 和 trace。后续可以把环境替换成真实网页、API 或业务系统，但架构边界仍然适用。

### Q48：项目当前有哪些不足？

可以回答：

我会坦诚说有几个不足：

- Memory 还是关键词检索，没有 embedding 和中文分词。
- LLM 输出是 JSON prompt 约束，还不是强 schema structured output。
- 自定义任务的 success condition 推断基于关键词，泛化能力有限。
- ReAct baseline 是轻量形式，不是完整 LLM ReAct loop。
- 环境规模还比较小，没有多 Agent 协作、人类审批或真实外部 API。

### Q49：下一步你会怎么改进？

可以回答：

我会优先做四件事：

1. 用 structured output 或 function calling 替换纯 JSON prompt。
2. 引入 embedding/BM25 hybrid memory，并评估 memory 对成功率的影响。
3. 增加 ablation benchmark，比如 no-memory、no-replanning、single-step LLM、day-plan LLM。
4. 扩展任务生成器和更细粒度 failure analysis，让 benchmark 更像一个小型 Agent eval suite。

### Q50：这个项目和实际 Agent 岗位有什么关联？

可以回答：

实际 Agent 工作通常不只是调用模型，而是要处理工具边界、状态同步、失败恢复、评测、成本和可观测性。这个项目虽然是游戏场景，但对应到业务系统就是：环境层相当于业务 API 和数据库，Tool 是可调用接口，Agent 是决策层，Runner 是 orchestration，Trace 是 observability，Benchmark 是 eval。它覆盖了 Agent 工程里很多通用问题。

## 十、压力面试问题

### Q51：如果 LLM 成本太高，你怎么办？

可以回答：

我会从三层优化。第一，用 deterministic skill 或 planner 处理确定性强的子任务，只把不确定或开放任务交给 LLM。第二，把单步 LLM 调用改成 day plan，减少调用次数。第三，记录 token usage 和 latency，用 benchmark 做成本和效果对比。如果低成本 baseline 已经能稳定完成任务，就不强行用 LLM。

### Q52：如果 Agent 一直循环怎么办？

可以回答：

当前 failure analysis 有简单 looping 检测，会看 trace 末尾动作是否重复。工程上我会进一步加 action repetition guard，比如最近 N 步同一动作失败就强制 inspect 或 replan；对 LLM prompt 加入 recent_history；对 planner 加入 subgoal timeout；对 benchmark 记录 looping category。

### Q53：如果环境规则变了，Agent 会不会崩？

可以回答：

这取决于变更类型。因为 Tool surface 和 Environment 分离，规则变化主要在 environment 层。确定性 Skill 可能需要调整策略，LLM prompt 的 world hints 也要同步更新。但测试和 benchmark 能快速暴露回归。长期看，可以减少硬编码 hints，让 Agent 更多通过 inspect 获取规则信息。

### Q54：如果自定义任务文本没法被关键词识别怎么办？

可以回答：

当前 fallback 会推到 Guardian 任务，这是一个保守但不够理想的 MVP。生产化我会把 task parsing 独立成模块，使用 schema-based LLM parser 或规则加模型混合方式，把 goal 解析为明确 success condition。如果解析置信度低，前端应该提示用户确认，而不是静默选择一个不相关任务。

### Q55：怎么证明 replanning 有用？

可以回答：

我会设计 ablation：同样任务、同样 seeds，比较 planner 和 planner_replanning 在 storm、mine_collapse、pending enemy 等场景下的 success rate、invalid action rate、failure_to_replan 数量和平均步数。当前代码中已经把 replanning error codes、计划插入逻辑和 trace 都暴露出来，后续可以专门构造 stress task。

### Q56：你如何区分 Agent 错误和 Environment 错误？

可以回答：

Agent 错误通常表现为 decision 生成失败、非法 JSON、未知 tool、参数错误或不符合当前状态的动作。Environment 错误则是规则实现本身和预期不一致。项目里通过 `ActionResult.error_code`、trace 的 `state_before/state_after` 和测试来区分。如果状态变化违反规则，那是 environment bug；如果环境正确拒绝了动作，那是 Agent planning 或 state understanding 问题。

### Q57：项目里哪些地方体现了可观测性？

可以回答：

主要是 trace 和 metrics。每一步记录 state_before、decision、result、state_after、day_plan、decision_latency_ms。episode 层记录 total_actions、invalid_actions、token_usage、estimated_cost、retrieved_memories、reflection。前端可以按 Day 回放这些 trace，命令行可以输出 summary。

### Q58：如果要接真实外部工具，需要注意什么？

可以回答：

我会继续保留环境或 tool gateway 作为唯一执行边界。真实外部工具需要权限控制、参数 schema、dry-run、幂等性、超时重试、审计日志和错误分类。高风险动作要有人类确认。Agent 仍然不能直接修改数据库或调用任意 API，而是通过受控 tool 执行。

### Q59：你在这个项目中怎么体现“Agent eval”的理解？

可以回答：

我把 eval 设计成任务、seed、episode、trace 和指标的组合，而不是只看单次 demo 成功。任务定义提供目标和 success condition，seed 保证复现，episode runner 收集完整执行过程，metrics 汇总效果、成本和失败类型。这样能支持横向比较不同 Agent，也能支持纵向比较某个策略改动前后的效果。

### Q60：这个项目最能代表你能力的点是什么？

可以回答：

我会说是“把 Agent demo 工程化成可评测闭环”的能力。项目里既有 LLM prompt 和 day planning，也有确定性 baseline、LangGraph replanning、环境规则、trace、memory、benchmark、UI 和测试。我没有只停留在模型调用，而是把 Agent 落地时必须面对的状态、工具、失败、成本和评测都放进了系统设计里。

## 十一、可直接放进简历的表述

可以使用：

> SurvivalAgent：构建轻量级 LLM Agent Benchmark 环境，模拟 HarvestAgent 风格生存经营任务，支持结构化 tool calling、day-level planning、LangGraph replanning、episode memory/reflection、trace replay 与批量评测。实现 Direct/ReAct/Planner/Replanning/LLM Agent baseline，使用固定 seed 对 G01-G05 任务评估 success rate、invalid action rate、steps、latency、token usage 与 estimated cost，并通过 Streamlit 展示实时动作链和历史轨迹回放。

更短版本：

> 设计并实现 Agent + Environment + Evaluation 框架，用规则游戏环境验证 LLM Agent 的规划、工具调用、失败重规划和经验记忆能力，配套 benchmark、trace、metrics 与 Streamlit 可视化。

## 十二、面试时的表达策略

建议优先强调：

- 我不是只做模型调用，而是做了可验证的 Agent 闭环。
- Agent 只能提出动作，环境负责校验和状态更新。
- 有 baseline、有 benchmark、有 trace，所以能比较和定位问题。
- LLM day plan 解决单步短视和调用成本问题，recovery_context 解决中途失败。
- 当前不足我清楚，并能说出具体改进路线。

尽量避免夸大：

- 不要把当前 ReAct 说成完整论文实现。
- 不要说 memory 已经是语义检索。
- 不要说自定义任务可以理解任意自然语言。
- 不要只报“能跑”，要讲为什么这样设计、怎么评估、哪里还能改。
