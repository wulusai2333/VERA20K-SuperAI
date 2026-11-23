# AI 调参实战手册

这份文档回答三个问题：**AI 的建造决策链到底怎么走**、**改哪个键能影响哪一步**、
**哪些看起来能改的键其实是死的**。它同时是一份踩坑记录——每一条都写清「症状 →
当时的错误结论 → 实际原因」，因为本项目在同一类问题上反复浪费过时间。

> 适用引擎：VERA20k 0.4.0（Ares 扩展开启）。
> 本文所有「引擎行为」结论都可以在**引擎抽取源码**里逐行核对（本地自备，不入库；
> 把 VERA20k 的 `src/` 拷到任意目录即可），括号内给出文件名与函数名。

**先读这两节**（2.4 起的核心设计）：

- [§9 打掉就重建](#9-打掉就重建原生节点重规划不需要触发器) ——
  建筑重建是引擎原生机制；哪些类型本来就「立即」、怎么让全部类型都立即、三条硬边界。
- [§10 设计取向：原版三难度 + 两条机制](#10-设计取向原版三难度--两条机制24-起) ——
  2.4 撤掉了哪些调参、为什么，以及每条保留项的归属。
- [§13 超级武器：AI 为什么「充满不放」](#13-超级武器ai-为什么充满不放) ——
  `SW.*` 开关全表、证据链、以及 `AISuperDefense*` 只管 ForceShield 这个易误判点。

---

## 1. 五条铁律

先记住这五条，它们解释了本项目 90% 的「AI 不听话」。

| # | 铁律 | 后果 |
| --- | --- | --- |
| 1 | **基地计划整局只生成一次**，之后永不重算 | 计划里没有的东西，这一局就永远不会有 |
| 2 | **`AIBuildCounts` 的副本落在「该类型第一个节点之后」的随机位置**，不是紧跟其后 | 早期类型的高计数会把后期类型挤到队尾，而不是「先建很多个」 |
| 3 | **日志里的 `placed` 是「真的落地了」，计划数不是** | 计划 40 座防御、实际落地 5 座是正常现象，验收只能看日志 |
| 4 | **`AIBuildThis=no` 的类型永远进不了计划**，和钱、科技等级都无关 | 原版靠它把一整类建筑从 AI 手里藏起来 |
| 5 | **`[AI]` 段里一大半比例/上限键是死键** | 改它们 100% 无效，且不会有任何报错 |
### 1.1 铁律 1：计划只生成一次

`recalc_base_plan` 只有两个调用点，都要求计划为空：

- `world_spawn.rs` → `refresh_ai_base_after_deploy`：第一台建造厂展开时；
- `house_base.rs` → `initialize_house_base_from_build_const`：地图触发器 30。

计划一旦非空，引擎再也不会重新生成它。中途能发生的只有三类**局部**改动：

| 改动 | 位置 | 触发条件 |
| --- | --- | --- |
| 插一个节点（重建） | `ai_build_need.rs` → `insert_rebuild_node` | 缺钱且缺矿场/战车工厂/矿车 |
| 插一个节点（补电） | `ai_base_building.rs` → `power_plant_to_splice` | 电力不足且当前节点耗电 |
| 插/删节点（墙） | `ai_base_building.rs` → `build_walls` | 防御抽签命中 |
| 删一个节点 | `ai_base_building.rs` / `ai_base_defense.rs` | 防御节点找不到可选类型，或节点放不下 |

**所以调参的思路永远是「让一次性生成的那张计划表是对的」**，而不是指望 AI 中途自我纠正。

### 1.2 铁律 2：`AIBuildCounts` 是「随机撒点」，不是「前置倍数」

Ares 的 `HouseClass_GenerateAIBuildList_CountExtra`（`base_plan_generation.rs`）对每个类型：
从建造厂之后开始，找到该类型的**第一个**节点，再插入 `count - 1` 个副本，
每个副本的位置是 `RandomRanged(该节点下标 + 1, 计划总长)`。

推论：

- `count=6` 的电厂 → 5 个电厂散落在整张计划的各个位置，把后面所有东西往后推；
- 电厂在列表最前面，所以它拿到的是**最大**的散布空间；
- 计划是有序执行的，被推到后面的战车工厂/高科/维修厂就是「迟迟不建」。

历史事故：1.x 把每类都设成 **60**，实测 **403 座电厂 vs 12 座战车工厂**。
2.0 降到 6/4/4/2 后仍有偏科，因为**排序信息**才是被破坏的东西，不是总数。

现行方案：早期类型压小、后期类型给足真实数量。

```
电厂 3 · 矿场 2 · 兵营 2 · 战车工厂 3 · 高科 2 · 雷达 1 · 维修厂 2（Yuri 维修厂/研磨机各 1）
```

### 1.3 铁律 3：只信日志里的 `placed`

每次成功落地都有一行（`ai_base_building.rs`，`place_building` 成功后打印）：

```
[<时间> INFO  vera20k_core::sim::ai_base_building] <房主> placed <类型> at (x, y)
```

计划数与落地数的差额有几个正当来源：

- **防御节点会被直接删掉**：`choose_building` 拿到 `-1` 节点后调用
  `choose_next_production`，后者要求候选防御的 `Prerequisite` 全部被**已有建筑**满足；
  不满足就 `remove_node`——不是延后，是**丢弃**。40 个防御节点按
  `RandomRanged(3, 计划长-1)` 散布，落在前几位、家里还没雷达/高科的一律白扔。
- 选址失败会被换格子甚至换建筑；
- 墙会抢走防御抽签。

### 1.4 铁律 4：`AIBuildThis` 是硬闸门

`recalc_candidate_allowed` 要求 `candidate.ai_build_this`，否则这个类型连
「可见候选」都不是。原版用它藏起一批建筑——**维修厂就是被这样藏起来的**。

### 1.5 死键清单

**判定方法**：在引擎源码里搜这个键的字面量。下表分成两档，因为这两档的可靠度不同。

**A 档：确认死键。** `[AI]` 段的读取者集中在 `general.rs` 的 `GeneralRules::from_ini`
与 `loading.rs`，这两份都在抽取集里，而下列键在其中**没有任何读取者**：

```
RefineryRatio  RefineryLimit  BarracksLimit  WarRatio   WarLimit
DefenseRatio   DefenseLimit   AALimit        TeslaLimit HelipadLimit
AirstripLimit  AttackInterval AutocreateTime InfantryReserve  BaseSizeAdd
BuildDummy
```

改它们 100% 无效，也不会报错。想让 AI 多造战车工厂，改的是 `AIBuildCounts` 和
`[AI] BuildWeapons=` 的**顺序**，不是 `WarRatio`。

**B 档：抽取集里找不到读取者，但未确认。** 本仓库只抽取了 93 个源文件（引擎的一个子集），
所以「找不到」不等于「不存在」。这一类**必须自己改一档、单独打一局、用
`analyze_log.py` 量出差异**才能下结论：

```
BuildSpeed
```

> `BuildSpeed=.025` 一直写在模组里并被文档描述成「约 28 倍建造速度」，
> 但抽取集里没有任何代码读它。**这是一个未验证的声明**，不要当既定事实引用；
> 要么实测差异，要么在文档里标注未验证。

**曾经被我误判为死键的一条**：`AIHateDelays`。它在抽取集里**是活的**
（`general.rs` 有 `[General] AIHateDelays=` 字段，`house_strategy.rs` 用它启动
非战役局的索敌计时器）。误判原因很蠢：搜 `HateDelays` 时它作为子串命中了，
我却把结果记成了靶子。**教训：搜子串命中不等于确认，要打开那一行看读的是哪个键名。**

**确认有读取者的键**（可作为白名单使用）：`AIExtraRefineries`、`AISlaveMinerNumber`、
三个 `*BaseDefenseCounts`、`AIPickWallDefensePercent`、`AIBaseSpacing`、
`AIRestrictReplaceTime`、`AIAlternateProductionCreditCutoff`、`TotalAITeamCap`、
`MaximumAIDefensiveTeams`、`MinimumAIDefensiveTeams`、`UseMinDefenseRule`、`TeamDelays`、
`DissolveUnfilledTeamDelay`、`AITriggerSuccess/FailureWeightDelta`、`MultiplayerAICM`、
`FillEarliestTeamProbability`、`HarvestersPerRefinery`、
`MaximumBuildingPlacementFailures`、`PowerSurplus`、`AttackDelay`、`AIHateDelays`、
`AIBuildCounts`、`AIExtraCounts`、`ProduceCashAmount`。

---

## 2. 建造决策链：每一步能改什么

```
① 计划生成（只发生一次）
   recalc_base_plan
     ├─ 候选 = 所有 AIBuildThis=yes 且 Owner/TechLevel 放行的建筑
     ├─ 种子顺序：BuildConst → BuildPower → BuildBarracks(移到 0) → BuildWeapons(移到 1)
     ├─ 前置补全：反复扫候选，Prerequisite 被已有节点满足的就追加
     ├─ 矿场复制：有矿车的国家用 AIExtraRefineries，没有矿车的国家用 AISlaveMinerNumber-1
     ├─ Ares AIBuildCounts：每个类型的首节点后面随机撒 count-1 个副本（按难度取数）
     ├─ 防御节点：*BaseDefenseCounts 个 "-1" 节点，随机位置（≥3）
     └─ 围墙节点：**本模组不会产生**（AIPickWallDefensePercent=0，见 §11）
② 选建筑
   choose_building
     ├─ 节点是 "-1" → choose_next_production 选防御（前置不满足就删节点）
     ├─ 电力不足 → power_plant_to_splice 在当前位置插一座电厂
     └─ 否则 → 把节点类型写成 building_choice
③ 生产 → ④ 出场选址 → ⑤ 落地
   Exit_Object → building_site → place_building → 日志 "placed"
```

| 想控制什么 | 改哪里 | 注意 |
| --- | --- | --- |
| 某个建筑造不造 | 该建筑的 `AIBuildThis` | 铁律 4，硬闸门 |
| 某个建筑造几个 | Ares `AIBuildCounts` | 铁律 2，位置是随机的；按难度取数（冷酷在前） |
| **基地能长多大** | **`*BaseDefenseCounts`** | 2.4 起不再靠 `AIBuildCounts` 堆量，见 §7.12 |
| 科技树种类 | `[AI] BuildConst/BuildPower/BuildRefinery/BuildBarracks/BuildWeapons/BuildTech/BuildRadar` | 只影响种子与 `POWER`/`PROC` 这类前置组的解析 |
| 防御数量 | `Allied/Soviet/ThirdBaseDefenseCounts` | 是**计划数**，实际落地会少（铁律 3）；同时也是最强的向外扩张驱动 |
| **不造围墙** | `AIPickWallDefensePercent=0,0,0` | **唯一的围墙入口**，0 = 完全不造，见 §11 |
| 矿场数量 | 有矿车：`AIExtraRefineries`；无矿车（Yuri）：`AISlaveMinerNumber` | 见 §4 |
| 兵种/组队 | `aimd.ini` 的 `[TeamTypes]`/`[AITriggerTypes]` | 权重 5000 是接管标记，别乱用（§5） |
| **AI 组不组队** | **`UseMinDefenseRule` + `MinimumAIDefensiveTeams`，必须与「有没有守家队类型」配套** | **配错 = AI 一兵不发，见 §7.11** |

---

## 3. 为什么「基地车没了也迟迟不建」——原版死锁，不是引擎限制


这是本项目**最贵的一个误判**。曾经在 `docs/ai-design.md` 和
`docs/troubleshooting.md` 里写成「VERA 的 AI 没有生产 MCV 的决策路径，只能改引擎源码」。
**完全错误。** 引擎和数据把整条恢复链都铺好了，只有一个开关被关掉：

```
AMCV Prerequisite=GAWEAP,GADEPT
SMCV Prerequisite=NAWEAP,NADEPT
PCV  Prerequisite=YAWEAP,YAGRND      ; YADEPT 在原版被注释掉
```

而原版三个维修厂全部 `AIBuildThis=no`（还带着注释
"taken out to remove useless building - DB"）。于是：

1. 维修厂进不了计划 → AI 永远没有维修厂；
2. `CanBuild(AMCV)` 因为缺 `GADEPT` 永远为假 → AI 永远造不出 MCV；
3. 建造厂被打掉后，**没有建造厂就不能造任何建筑**（`choose_building` 在
   `build_const_order` 为空时直接返回）→ 唯一活路是战车工厂产 MCV，而它被 ② 堵死；
4. 数据里那 3 条「本户拥有 0 座建造厂」的 AI 触发器和 3 支 `Max=1` 的 MCV 队伍
   （脚本 `043F23CC-G` = 找空地 + 展开）因此**永远不会起作用**。

修复就是打开三个开关：`GADEPT`/`NADEPT`/`YADEPT` 的 `AIBuildThis=yes`。

### 3.1 仍要承认的两个真实限制

- **AI 需要同时有战车工厂和维修厂**才能产 MCV。两者都没了，无解——不要承诺「AI 永远能重建」。
- **MCV 必须找到 4×4 空地才能展开**。日志里
  `MCV deploy blocked at origin (x, y)` 就是找不到空地：
  `world_spawn.rs` 的 `deploy_mcv` 在 `can_place_building_at` 失败时打印它。
  一张实测日志里 89 次/局，58 个不同原点——**基地太挤时 MCV 会被反复拒绝展开**。
  这跟「不造 MCV」是两个独立问题，排查时别混为一谈。

---

## 4. Yuri 的矿场为什么自己复制自己

Yuri 有三个特殊之处，叠在一起变成「矿场洪水」：

1. **`YuriCountry` 没有矿车**：`HarvesterUnit=HARV,CMIN`，而 HARV 属苏军、CMIN 属盟军。
   于是 `recalc_base_plan` 走「无矿车」分支，用 **`AISlaveMinerNumber - 1`** 当矿场复制数
   （不是 `AIExtraRefineries`）。原版 `AISlaveMinerNumber=4,3,2` → 困难难度复制 3 座。
   **这就是为什么只改 `AIExtraRefineries` 对 Yuri 无效。**
2. **`YAREFN` 是全局唯一的 `ResourceGatherer=yes` 建筑**（"移动矿场是建筑变形体"），
   带 `UndeploysInto=SMIN`、`BaseNormal=no`。
3. `node_may_replan` 对「资源采集建筑」有专门分支：**丢了就能立刻重规划，
   完全绕过 `AIRestrictReplaceTime`**，条件是
   `resource_gatherers() < AISlaveMinerNumber`。SLAV 是 `Slaved=yes` 而非
   `ResourceGatherer=`，所以永远不计入——这个条件在实战里经常恒真。

后果（实测）：某局 Yuri 的 134 次放置里 **75 次是 YAREFN（56%）**，且只有 **18 个不同格子**；
`(817,554)` 在 11 秒内被放了 **8 次**。战车工厂拖到第 92 次才出现，高科 0 次。

**修法**：`AISlaveMinerNumber` 4,3,2 → **2,2,2**。一次改动同时把复制数从 3 降到 1、
让重规划门槛在 2 座时就满足。

> 顺带一个日志陷阱：`YAREFN` **没有** `Refinery=yes`/`FreeUnit=`，所以它落地时
> 不会打印 `Completed refinery ... spawned free ...`。整份日志里 `Completed refinery YAREFN`
> 是 0 行，**这不代表失败**。GAREFN/NAREFN 才有那一行。

---

## 5. 触发器权重 5000 是接管标记，不是加强

`ai_team_creation.rs` 里 `PRIORITY_WEIGHT = 5000`。语义是：抽签过程中一旦有 5000 权重的
触发器命中，**清空之前所有条目**，之后只允许 5000 的参与。

所以给「重建基地车」触发器设 5000 是**灾难**：那支队伍在维修厂建好之前永远凑不齐，
于是这支 AI 在 `DissolveUnfilledTeamDelay` 到期前**一支队伍都不会再组建**——
表现就是「中后期 AI 完全不进攻」。当时正好把维修厂关着，等于给自己造了一个永久沉默的 AI。

正确做法：与进攻触发器同权（250），让抽签自己决定。原版用 5000 是有正当用途的
（超武、间谍护卫），它们的条件很窄——但**不要在「可能凑不齐的队伍」上用**。

`tools/build_mod.py` 里加了断言：任何名字含 `MCV` 的触发器若权重 ≥ 5000 就直接
`SystemExit`，把坑变成构建失败。

---

## 6. 标准操作流程（改 AI 数值时必须照这个顺序）

```powershell
cd <仓库目录>

# 1. 只改 tools/build_mod.py —— 它是唯一真相源，直接改发布版 INI 会被下次重建覆盖
#    （规则：RULES_EDITS / SECTION_KEY_EDITS / BUILD_COUNTS）

# 2. 重建到临时目录并确认幂等
python tools/build_mod.py --rules-dir "<原版规则目录>" --out %TEMP%/rebuild

# 3. 逐字节对齐仓库
#    重建结果必须与 mod/SuperAI/* 完全一致，否则说明有人手改过发布文件
#    （用 Get-FileHash -Algorithm SHA256 比对三个文件）

# 4. 无窗口加载校验（规则语法、地图、Ares）
python tools/check.py --game-dir "<游戏目录>"

# 5. 装进游戏
python tools/install.py --game-dir "<游戏目录>"

# 6. 打一局，然后判读日志结构（不看强弱，只看有没有建对）
python tools/analyze_log.py --log "<游戏目录>/logs/ra2.log" --session last
python tools/analyze_log.py --log "<游戏目录>/logs/ra2.log" --session all --strict
```

### 6.1 `tools/analyze_log.py` 的验收闸门

它按 `VERA20k <版本> starting` 切会话，再按 `sim::runtime] Initialized authored native`
切「一次启动里的第二场对局」，然后**只统计 `placed` 行**：

| 闸门 | 判据 |
| --- | --- |
| 战车工厂不能太晚 | 首次落地序号 ≤ 该户放置总数的 25% |
| 防御不能太少 | 防御占比 ≥ 10% |
| 墙不能太多 | 墙占比 ≤ 15% |
| 不能偏科 | 单一类型 ≤ 30%（电厂豁免） |
| 不能原地打转 | 同一格同一类型 ≤ 3 次 |
| 提示 | 没有维修厂的房主会被单独列出（它不可能重建 MCV） |

放置数少于 25 的房主会被跳过，样本不够不做结论。

### 6.2 基地规模怎么调（2.4 起：默认就是原版节奏）

2.4 把 `BUILD_COUNTS` 清空了，所以**默认没有任何 `AIBuildCounts`**：
每种建筑一个节点，节奏由三个原版难度决定，扩张靠「打掉就重建」（§9）。

想改规模，按下面的优先级选一个，不要同时动：

| 想要什么 | 只改这一个地方 | 说明 |
| --- | --- | --- |
| **默认（推荐）** | 不动 | 原版节奏 + 被动重建。基地约 20–40 栋 + 25/20/6 防御 |
| 基地更大 | `*BaseDefenseCounts`（如 `60,60,60`） | 防御节点沿周长**向外**找位置，是唯一不破坏建造顺序的扩容旋钮 |
| 每种建筑多个 | 给 `BUILD_COUNTS` 填小值（2–4） | 副本是随机撒点，值越大越容易打乱建造顺序；**不要回到 60** |
| 大图（120 AI） | 保持默认，别再放大 | 119 户 × 每户建筑数，建筑总量很容易失控 |

> 上限：单个类型的副本插入被 `BASE_PLAN_INSERT_LIMIT=256` 截断，
> 防御节点同样如此，所以标到 300 与标到 256 等价。

### 6.3 改动前基线（2.1，2026-11-22 的日志）

留着做对照，别把「现在也这样」当成「本来就该这样」：

| 指标 | 2.1 实测 |
| --- | --- |
| 全日志闸门 | 1095 条判据、**289 条 FAIL** |
| 战车工厂过晚 | 119 个房主 |
| 同格重复 > 3 | 45 个房主 |
| 墙过多 | 27 个房主 |
| 维修厂落地 | **119 个房主，0 次** |
| AMCV/SMCV/PCV 落地 | **0 次**（全日志 82,736 行） |
| MCV 展开被拒 | 89 次/局（58 个不同原点） |

2.2 的对照（14:54Z 那一局，3 个槽位）：科技树已经正常（战车工厂第 4/19 位、维修厂 2 座、
高科 3–5 座），但**基地只有 98 / 84 栋就停了**，而且完全不出兵 ——
前者是 §7.12 的节点用尽，后者是 §7.11 的死锁。

---

## 7. 踩坑记录

每条格式：**症状 → 当时的错误结论 → 实际原因**。

### 7.1 只造电厂、不造后面的厂

- **症状**：AI 电厂、兵营、矿场铺满，战车工厂/维修厂/高科迟迟不来。
- **错误结论**：AI 的优先级有问题，要调 `[AI]` 里的 `WarRatio`/`WarLimit`。
- **实际原因**：那些是死键（§1.5）。真正原因是 `AIBuildCounts=60` 把后期类型
  用随机撒点推到了队尾（§1.2）。

### 7.2 「AI 不会造 MCV = 引擎限制」

- **症状**：建造厂被拆后 AI 再也不起来。
- **错误结论**：引擎没有这条路径，只能改源码。
- **实际原因**：数据里三个维修厂 `AIBuildThis=no`，把 MCV 的前置掐死了（§3）。
  写进文档前先在源码里确认「引擎有没有这条路」，别凭现象下结论。

### 7.3 调 `AIExtraRefineries` 治不好 Yuri 的矿场洪水

- **症状**：改成 `0,0,0` 后盟军/苏军矿场正常了，Yuri 还是满屏 YAREFN。
- **错误结论**：键没生效 / 被别处覆盖。
- **实际原因**：Yuri 没有矿车，走的是 `AISlaveMinerNumber - 1` 分支（§4）。

### 7.4 把「YAREFN 没有完成日志」当成放置失败

- **症状**：`Completed refinery YAREFN` 全日志 0 行，怀疑 Yuri 矿场建不起来。
- **错误结论**：Yuri 矿场有 bug。
- **实际原因**：那个日志属于「产矿场送矿车」的路径，只有带 `Refinery=yes`/`FreeUnit=`
  的类型才有。YAREFN 是建筑变形体，没有这段。

### 7.5 把 5000 权重当成「提高优先级」

- **症状**：给 MCV 触发器设 5000 后，AI 中后期几乎不再进攻。
- **错误结论**：5000 太高把别的触发器压住了，改成 6000 试试。
- **实际原因**：5000 是接管标记，`≥5000` 全部同权接管，改更大没用（§5）。

### 7.6 `AIBaseSpacing=2` 让基地卡在约 70 栋

- **症状**：基地规模上不去，大量选址失败。
- **实际原因**：选址间距放大后可用周长不够。保持 `1`。

### 7.7 文档与代码漂移

- **症状**：文档说防御 `100,100,100`、每类建筑 60 个副本，而 `build_mod.py`
  里写的是 `40` 和 6/4/4/2（2026-11-22 时的实际值）。
- **错误结论**：以为有一份文档是权威，照着它调参。
- **实际原因**：改了 `build_mod.py` 忘了同步文档。`build_mod.py` 是唯一真相源，
  文档只是它的说明。
- **纪律**：`docs/ai-design.md`、`README.md`、`mod.ini` 的 `About` 与
  `build_mod.py` 里的常量必须在同一次提交里一起改。改完用
  `git diff --stat` 扫一眼有没有漏掉文档。

### 7.8 在 GBK 控制台下解析日志/调用探针

- **症状**：`check.py` 抛 `UnicodeDecodeError: 'gbk' codec can't decode byte ...`；
  PowerShell 打印中文标题变成 `????AI`。
- **实际原因**：Windows 控制台默认 cp936，而引擎输出 UTF-8。
  `check.py` 原用 `text=True`，会按控制台码页解码。
- **修复**：`subprocess.run(..., encoding="utf-8", errors="replace")`，
  并对 `sys.stdout` 做 `reconfigure(encoding="utf-8", errors="replace")`。
  写日志分析脚本时一律显式指定 `encoding="utf-8"`。

### 7.9 一次启动里有好几场对局

- **症状**：同一份日志里，`Computer1` 一会儿造 Yuri 建筑、一会儿造苏军建筑。
- **实际原因**：`vera20k.exe` 追加写同一个 `ra2.log`，重开一局不会重启进程；
  第二场以 `sim::runtime] Initialized authored native` 开始。
- **纪律**：切分会话必须两级切，`analyze_log.py` 已经这么做。

### 7.10 以为「计划 40 座防御」就会落地 40 座

- **症状**：把 `*BaseDefenseCounts` 调到 100，实际只多出几座。
- **实际原因**：`-1` 节点找不到可选防御就会被**删除**（§1.3），且围墙会抢抽签。
  验收只看日志里的实际落地数。

### 7.11 没有守家队类型，却打开了 `UseMinDefenseRule`（2.2 的事故）

**这是本项目最隐蔽的一次事故：基地建得漂漂亮亮，AI 却一兵不发。**

- **症状**：科技树全出、超武都造出来了、防御也铺满，但 AI 不造兵、不进攻、地图上没有任何部队。
  日志里 `placed` 行一切正常，没有任何报错。
- **当时的错误结论**：怀疑触发器权重、队伍上限、`TeamDelays`、资金，甚至以为地图触发器把它清光了。
- **实际原因**：两条改动撞在一起，构成永久死锁。

  1. `tools/build_mod.py` 把**所有非 MCV 队伍类型**都改写成 `IsBaseDefense=no`
     （`build_aimd` 里那句 `("Aggressive","yes"),("IsBaseDefense","no")`）。
     于是模组里 `IsBaseDefense=yes` 的队伍类型是 **0 个**（零售有 12 个）。
  2. 2.2 又把 `UseMinDefenseRule` 从 `no` 改成 `yes`、`MinimumAIDefensiveTeams` 从 `0` 改成 `1`。

  而 `ai_team_creation.rs` 的判定是：

  ```
  base_defense  = <TeamType 的 IsBaseDefense>          -> 恒 false（第 1 步）
  defense_teams = <队伍类型是守家队的队伍数>            -> 恒 0
  needs_defense = !has_enemy
                  || (use_min_defense_rule && defense_teams < min_defensive)
  if needs_defense { 只放行 base_defense 触发器 } else { 正常 }
  ```

  有敌人时 `needs_defense = (true && 0 < 1) = true` → 只放行守家队触发器 →
  **一个都不存在** → 163 条触发器全部被拒 → 不组队 → 出兵选择器没有「队伍还需要什么」
  → 不造兵 → 不进攻。基地建造走的是另一条路径，完全不受影响，所以看起来「一切正常」。

- **修法**：`UseMinDefenseRule=no`、`MinimumAIDefensiveTeams=0,0,0`、
  `MaximumAIDefensiveTeams=0,0,0`（`MaximumAIDefensiveTeams` 只是跟着改，没有守家队可限）。
- **永久防护**：`build_mod.py` 现在有 `assert_defense_gate_consistent`：
  若 `aimd.ini` 里没有任何 `IsBaseDefense=yes` 的队伍类型，而
  `UseMinDefenseRule=yes` 或 `MinimumAIDefensiveTeams` 非全零，**构建直接失败**并说明原因。
  下次谁再想「给 AI 留一支守家队」，会在构建期被拦住，而不是进游戏看 AI 发呆。
- **教训**：只要我们把某类对象**全部改写**掉（这里是「所有队伍都不是守家队」），
  就必须回头检查**依赖这类对象存在的所有判定**。零售的默认值是**和零售数据配套**的，
  不是和我们的数据配套的。

### 7.12 「AI 不扩张」——其实是计划节点用完了

- **症状**：AI 把基地建到某个规模就完全停手，有平地也不再往外铺。
- **实际原因**：`base_plan` **整局只生成一次**（§1.1），每个节点对应一栋建筑；
  选址只在 `house.base_reservation().perimeter_cells()` 上做（`ai_base_site.rs` 的
  `ordinary_site`），没有任何可用周长格时返回 `(0,0)`、放置失败。
  所以**节点数就是扩张预算**：2.2 把每类压到 1–3，总节点只有十几个，
  基地十几栋就建完了。
- **修法**：把量放在**中后期类型**上（分散插入不会占掉队首），并同时抬高
  `*BaseDefenseCounts` —— 防御节点是**向外**找位置，是最强的扩张驱动。
- **代价与边界**：这不是真正无限（真无限要引擎中途重算计划）。节点够多 + 持续重建
  + 按需补电，表现为「整局都在长」。120 人图要降档，否则建筑总量会失控。

### 7.13 单位生产与队伍创建**没有任何日志**

- **症状**：AI 不造兵，但日志里什么都看不出来，`analyze_log.py` 也不会报——因为它只统计建筑。
- **实际原因**：引擎只记录建筑落地（`placed`）、矿场完成、MCV 展开被拒等，
  **单位生产和组队完全不写日志**；`replays/replay_tick*.json` 也只有输入指令
  （`ending.terminal_score_snapshot` 实测为 `null`），没有局面快照。
- **纪律**：涉及「造不造兵、组不组队、打不打」的问题，**不能只靠日志下结论**，
  要么进游戏看，要么先做一个可观测的间接信号。这正是 7.11 拖了一整轮才定位的原因。

---

## 8. 源码位置速查

文件名即源码路径（例如 `src__sim__ai_team_creation.rs` 对应 `src/sim/ai_team_creation.rs`）。

| 想看什么 | 文件 | 关键函数 |
| --- | --- | --- |
| 计划怎么生成 | `src__sim__base_plan_generation.rs` | `recalc_base_plan`、`preflight_recalc`、`prerequisites_satisfied` |
| 计划数据结构 | `src__sim__base_plan.rs` | `fill_successful_building`、`insert_rebuild_node` |
| 选建筑 / 落地 | `src__sim__ai_base_building.rs` | `choose_building`、`find_node`、`node_may_replan`、`exit_building`、`build_walls` |
| 防御选型 | `src__sim__ai_base_defense.rs` | `choose_next_production` |
| 经济崩溃自救 | `src__sim__ai_build_need.rs` | `restart_production`、`sell_node` |
| 组队与触发器 | `src__sim__ai_team_creation.rs` | `PRIORITY_WEIGHT`、`is_eligible`、`factories_admit` |
| 出兵选择 | `src__sim__ai_unit_choice.rs` | `choose` |
| MCV 展开 | `src__sim__world__world_spawn.rs` | `deploy_mcv`、`refresh_ai_base_after_deploy` |
| 键在哪读 | `src__rules__ruleset__general.rs`、`src__rules__ruleset__loading.rs`、`src__rules__ares_building_type.rs` | `from_ini`、`ai_extra_copies` |

> `AIBuildThis` 的解析默认值是 `false`（`src__rules__object_type__reader.rs`）——
> 所以「没写」和「写了 no」等价，都是不可建。
## 9. 「打掉就重建」——原生节点重规划，不需要触发器

**结论：建筑重建是引擎原生机制，不是我们新加的东西。**
每个计划节点都记着「这格该有一栋什么」（`src__sim__base_plan.rs`）；
建筑没了，节点还在，引擎会让它重建（`ai_base_building.rs` → `node_may_replan`）。
而且**按类型**区别对待，这正是你直觉里「电厂、碉堡应该马上补」的来源：

| 建筑类型 | 丢失后能否立刻重建 | 判定 |
| --- | --- | --- |
| **电厂**（`Power>0`） | **立即** | `ty.power > 0` |
| **有武器的建筑**（碉堡、光棱塔、爱国者、防空炮…） | **立即** | `ty.primary().is_some()` |
| 贴着自家建筑的围墙 | 立即 | 邻格有自家建筑 |
| **兵营 / 战车工厂 / 高科 / 维修厂** | 要等 `AIRestrictReplaceTime` | 时间分支 |
| Yuri 矿场（`ResourceGatherer`） | 立即 | `resource_gatherers() < AISlaveMinerNumber` |

所以「电厂被打掉立刻造一个」「碉堡被打掉立刻造一个」**本来就是原生行为**。
要让它对**所有建筑**都成立，只改一条键：

```ini
AIRestrictReplaceTime=0     ; 0 = 不限制；零售 400（约 27 秒）
```

两个容易忽略的细节：

- **重建会插队**：重建的是同一个节点，位置不变（通常很靠前），而
  `choose_building` 取的是**最靠前的未满足节点**，所以「被打掉的东西」
  天然比「还没造过的东西」优先。
- **失败会放弃**：连续 `MaximumBuildingPlacementFailures + 1`（默认 6）次放不下，
  节点会被删掉（`base_plan.rs` → `count_placement_failure`），不会无限硬撑。

### 9.1 三条硬边界

| 边界 | 说明 |
| --- | --- |
| **触发器不能下建造令** | `[AITriggerTypes]` 只能组队。想让 AI「造建筑」，只有「计划节点」这一条路，配置层面无解 |
| **没有建造厂就什么都不造** | `choose_building` 在 `build_const_order` 为空时直接返回。所以丢厂后唯一活路是产 MCV，而 MCV 需要战车工厂 + 维修厂 |
| **计划里没有的类型不会重建** | 只有「本该有、后来没了」的东西会补；从没进过计划的类型永远不会出现 |

### 9.2 基地车：救急 + 扩建，共 6 条触发器

基地车不是建筑计划的一部分，所以它走的是触发器。`[AITriggerTypes]` 里一共 **6 条**
（每条触发器只能比较**一种**对象的数量，见 `owned_count_holds`）：

| 触发器 | 条件 | 权重 | 作用 |
| --- | --- | --- | --- |
| 3 条零售 `… MCV - H` | 本户建造厂 **== 0** | `5000` | **救急**：厂全没了 → 只造基地车 |
| 3 条新增 `… MCV - Expand` | 本户建造厂 **< 3** | `5000` | **扩建**：不满 3 座就补基地车去展开 |

`Max`（3 支 MCV 队伍）从 `1` 改成 **`2`**：`at_max_teams` 的判定是
「本户该类型队伍数 `>= Max` 就挡住」，所以零售的 1 决定了**一次只能有一台基地车**。

`5000` 就是 `PRIORITY_WEIGHT`：命中即**清空该次抽签的其它全部触发器**。
「立即」靠的就是它，不是权重数值大小。

#### 比较掩码怎么写

32 字节、64 个十六进制字符；`compare` 把**小端**的 word(0) 当数量、word(4) 当运算符
（0 `<` / 1 `<=` / 2 `==` / 3 `>=` / 4 `>` / 5 `!=`）：

| 含义 | 前 16 个字符 | 说明 |
| --- | --- | --- |
| 建造厂 == 0（零售） | `0000000002000000` | 数量 0，运算符 2 |
| 建造厂 < 3（新增） | `0300000000000000` | 数量 3，运算符 0 |

后面再补 48 个 `0`。**长度不是 64 或含非十六进制字符时，整条触发器会被静默丢弃**
（`parse_ai_trigger_comparison` 返回 `None`）——
`tools/build_mod.py` 的 `assert_mcv_triggers_well_formed` 会在构建期拦住这种错误。

#### 收敛过程

```
1 座厂 → count(厂)=1 < 3 → 扩建触发器命中 → 出第 1 台车
      → 下次组队检查（TeamDelays，困难 20 秒）出第 2 台（Max=2）
      → 两台各开去空地展开 → 3 座厂
      → count(厂)=3 → 触发器不再命中 → 停
某座厂被拆 → count(厂)=2 → 重新补车 → 又回到 3 座
```

#### 代价（必须知道）

- **达到 3 座厂之前，这户暂停组建新的进攻队**（已在场的部队不受影响，仍在 All-to-Hunt
  下作战）。窗口长度 = 造两台车 + 开去展开的时间，建造速度很快，通常几十秒。
  若更在意「进攻不能停」，把扩建触发器权重从 `5000` 降到 `500`：
  仍常被抽中，但不再独占抽签，代价是从「立即」变成「几次组队检查之后」。
- **只能近似「厂 + 车 < 3」**：触发器只数建造厂，在编基地车由 `Max=2` 封顶，
  所以瞬态最多 3 座厂 + 1 台在路上的车。
- **「一次两个」实际是「第一台立刻、第二台下一次组队检查」**：一次抽签只产出一支队伍。
  把一支队伍编制改成 2 台可以让两台同时出，但脚本是「开到空地展开」，
  两台同点会互相挡住（`MCV deploy blocked`），所以不做。
- 前提仍是维修厂可建（`AIBuildThis=yes`）：`assert_mcv_recovery_fillable` 强制
  6 条 MCV 触发器与「三个维修厂可建」必须同时成立，否则构建失败。
  局内维修厂被打掉无法预防，靠 `DissolveUnfilledTeamDelay=900`（60 秒）解散重试。

### 9.3 怎么验证「重建」生效

建筑**丢失**没有日志，只能从「同一类型隔一段时间又在**别的格子**出现」反推：

```bash
python tools/analyze_log.py --log "<游戏目录>/logs/ra2.log" --session last --rebuilds
python tools/analyze_log.py --log "<游戏目录>/logs/ra2.log" --session last --rebuilds 60
```

输出按户/类型给出「重建事件」数。它是**有噪声的代理指标**（慢速新建也会被算进去），
所以要连同闸门报告一起看，别单独当结论。

---

## 10. 设计取向：原版三难度 + 两条机制（2.4 起）

2.4 把前几版堆起来的一大批调参**整批撤掉**了，设计收敛成一句话：
**让原版三难度决定节奏，我们只加「猛攻」和「打掉就重建」。**

### 10.1 撤掉的

| 撤掉的 | 原因 |
| --- | --- |
| 23 个类型的 `AIBuildCounts` | 它不是「难度旋钮」：计划整局只生成一次，副本又是随机撒点，抬高只会破坏建造顺序（60 → 403 电厂 vs 12 战车工厂）。**2.6 起只保留 6 个生产建筑，见 §11** |
| 三个 `*BaseDefenseCounts` 的抬升 | 回原版 `25/20/6`，让三个难度各自决定防御规模 |
| 67 条攻击触发器的 250 权重与难度位全开 | 回原版 `70/60/70`，AI 出手频率交回难度 |
| TaskForce 编制缩放 | 2.0 之后本来就是空操作（`MULTIPLIER=1`），纯死代码 |
| `AIHateDelays` / `AITriggerSuccess/FailureWeightDelta` | 两条机制都不需要，回原版 |

### 10.2 留下的（每条都是某条机制的必需品）

| 键/改动 | 值 | 属于哪条机制 |
| --- | --- | --- |
| 全部非 MCV 队伍 → `ZAIATK01-G` + `Aggressive=yes` + `IsBaseDefense=no` | — | 猛攻 |
| `UseMinDefenseRule=no`、两个 `*AIDefensiveTeams=0` | — | 猛攻（没有守家队） |
| `TeamDelays` | `300,450,600` | 猛攻（原版 33–58 秒太慢） |
| `TotalAITeamCap` | `10` | CPU 上限（编制仍是原版） |
| **`AIRestrictReplaceTime`** | **`0`** | **重建** |
| 3 条 MCV 触发器 | 权重 `5000`、三难度 | 重建基地车 |
| 维修厂 `AIBuildThis=yes` | — | 重建基地车的**前提** |
| `AIPickWallDefensePercent` | **`0,0,0`** | **完全不造围墙**，见 §11 |
| `AIExtraRefineries` / `AISlaveMinerNumber` | `0,0,0` / `2,2,2` | 修 Yuri 矿场自我复制与同格重建 |
| `DissolveUnfilledTeamDelay` | `900` | 凑不齐的队伍尽快腾出编制 |
| `MultiplayerAICM` / `BuildSpeed` / `Paranoid=no` | — | 模组身份与 FFA 观战 |

### 10.3 代价

- **基地回到原版规模**（一户约 20–40 栋 + 25/20/6 防御），不再有 2.3 那种几百个节点。
- **扩张是被动的**：只有被打掉才会重建、才会向外挪；**没人打它，基地就静止**。
  这是设计的取舍，不是 bug。
- 想更饱满**只动一处**：`*BaseDefenseCounts`（防御节点沿周长向外找位置，
  是唯一不破坏建造顺序的扩容旋钮）。

---

## 11. 围墙：全部关掉（2.6 起）

**结论：`AIPickWallDefensePercent=0,0,0`，AI 一座围墙都不造。**

### 11.1 为什么这个键就够了

引擎里造墙只有**一个**入口（`ai_base_building.rs`）：

```
choose_building 处理 "-1"（防御）节点时：
    draw = RandomRanged(0, 99)
    if draw < AIPickWallDefensePercent
        && build_walls(...)              // ← 全源码唯一调用点
```

`build_walls` 只在这里被调用；`AIPickWallDefensePercent` 也全源码只有一个读取点。
所以 **0 就是「永远不掷出围墙」**，而且剩下的每一次防御抽签都会落到**真枪**上。

另一条路 `scan_base_perimeter` 只在消费 `-3` 控制节点时跑，而遭遇战的重算计划
**从不插入 `-3`**（只插 `-1` 防御、副本、矿场复制），所以我们的 5 张图不会走到那条路。

### 11.2 为什么必须关掉

| 代价 | 说明 |
| --- | --- |
| 吃掉防御名额 | 每格围墙都是**一个计划节点**，跟真正的防御抢同一份预算（`*BaseDefenseCounts`） |
| 堵自己的路 | `ProtectWithWall=` 的建筑会绕一圈墙，把自己的出入口和 AI 的寻路一起堵住 |
| 观感上的假象 | 一座「92 段围墙 + 63 座真防御」的基地，看起来铺得很大，实际火力只有一半 |

### 11.3 想恢复怎么办

把 `AIPickWallDefensePercent` 调回正数即可（零售 `50,25,10`，本模组 2.3–2.5 曾用 `10,10,10`）。
注意 `tools/build_mod.py` 的 `assert_no_walls` 会**阻止构建**，所以恢复时必须同时删掉那条断言 ——
这是故意的：围墙的副作用很容易被忘掉，改回来应该是**有意识的决定**。

---

## 12. 按难度给数量：冷酷 3 兵营 / 5 战车工厂（2.6 起）

`AIBuildCounts` 是**按难度**的整数列表，用 `HouseDifficulty::table_index()` 取值，
而**冷酷 = 0、中等 = 1、简单 = 2**（向量「最难在前」，别按直觉写成「简单在前」）。
值 `n` 的含义：该类型先占 1 个种子节点，再在**首节点之后随机位置**插 `n-1` 个副本。

| 类型 | `AIBuildCounts` | 冷酷 | 中等 | 简单 |
| --- | --- | --- | --- | --- |
| `GAPILE` / `NAHAND` / `YABRCK` | `3,1,1` | **3 个兵营** | 1 | 1 |
| `GAWEAP` / `NAWEAP` / `YAWEAP` | `5,1,1` | **5 个战车工厂** | 1 | 1 |

只有这 6 条，其余类型不写这个键（回到「一种一个」）。

- 副本会插在首节点**之后**的随机位置，所以**不会推迟战车工厂第一次出现**——
  那是种子节点决定的。总共只多 6 个节点，也不会重演 1.x「60 → 403 电厂」的偏科。
- 数量是被**长期维持**的：打掉一栋，节点回到未满足状态，「打掉就重建」会补回来（§9）。
- `assert_build_counts` 会在构建期检查三件事，因为这三类错误都是**静默失效**：

| 错误 | 后果 | 断言 |
| --- | --- | --- |
| 段名拼错（`[GAPIL]`） | 引擎根本读不到，白写 | 目标必须都是存在的段名 |
| 列表少于 3 项 | 缺的难度**静默退化成 1 个节点** | 必须正好 3 个整数 |
| 顺序写反（`1,1,5`） | 冷酷拿不到 5 个 | 必须与 `BUILD_COUNTS` 完全一致 |

---

## 13. 超级武器：AI 为什么「充满不放」

### 13.1 结论（核弹/闪电**已实测确认**；铁幕/超时空待确认）

**改动**：给 AI 能造出来的 6 个带目标超武，显式写上 Ares 的 `SW.*` 开关。
零售数据里 12 个超武段**一条 `SW.*` 都没有**，AI 就停在默认瞄准状态。

| 超武 | 建筑 | AI 可造 | `SW.AITargeting` | 备注 |
| --- | --- | --- | --- | --- |
| `NukeSpecial` | `NAMISL` | 是 | `offensive_cell_clear` | **实测可用** |
| `LightningStormSpecial` | `GAWEAT` | 是 | `offensive_cell_clear` | **实测可用** |
| `PsychicDominatorSpecial` | `YAPPET` | 是 | `offensive_cell_clear` | 同族 |
| `GeneticConverterSpecial` | `YAGNTC` | 是 | `offensive_cell_clear` | 同族 |
| `ChronoSphereSpecial` | `GACSPH` | 是 | `offensive_cell_set` + `SW.AffectsHouse/AffectsTarget=yes` + `SW.AIRequiresTarget=no` + `.Constraints/.Preference` | 传送**自家**部队，**仍不发射（2.9）** |
| `IronCurtainSpecial` | `NAIRON` | 是 | `defensive_cell_set` + `SW.AffectsHouse/AffectsTarget=yes` + `SW.AIRequiresTarget=no` + `.Constraints/.Preference` | 罩**自家**部队，**仍不发射（2.9）** |

> 2.9 对这两个改用了**一次性写全所有候选键**的做法：`SW.AITargeting` 平键 +
> `SW.AITargeting.Constraints` + `SW.AITargeting.Preference`（后两个键名在二进制里存在），
> 再补 `SW.AffectsHouse=yes`、`SW.AffectsTarget=yes`、`SW.AIRequiresTarget=no`。
> 理由见 §13.1.2：**没有任何无头手段能判断哪个键是活的**，所以只能一次全写，
> 让"键名/取值不对"这个可能性被彻底排除。被忽略的键不会造成伤害。
>
> 已经确认的事实：AI **确实造出了这两个建筑**（日志 `placed NAIRON` 912 次、
> `placed GACSPH` 121 次），所以问题只在"要不要开火"。
> 另外 `house_state.rs` 的 `HouseSuperWeaponTargets` 只建模了 `nuke_target` / `emp_target`，
> 暗示原生 AI 瞄准只覆盖固定几种超武。
>
> **若 2.9 仍不发射，结论就定为：引擎没有「作用于发射方自家单位」的超武 AI 发射路径。**
> 这是引擎限制，不再继续试配置 —— 届时会写进 README 的已知限制。

每个段都同时写：

```ini
SW.AllowPlayer=yes
SW.AllowAI=yes
SW.AutoFire=yes        ; ← 关键：自动发射（AI 没有「点击」这条路径）
SW.UseAITargeting=yes
SW.RequiresTarget=yes
```

### 13.1.1 最容易搞错的一点：`cell_clear` 还是 `cell_set`

那 7 个取值是**同一个枚举**的变体，成对出现：

```
offensive_cell_clear  defensive_cell_clear  offensive_cell_set  defensive_cell_set
attacked  lightningstorm_inactive  dominator_inactive
```

- **`cell_clear` = 挑一个「空的」格子**；**`cell_set` = 挑一个「里面确实有东西」的格子**。
- **`offensive` = 敌方地盘**；**`defensive` = 自家地盘**。

于是「打敌人」和「帮自己」是两回事：

| 超武要的效果 | 正确取值 | 选错的后果 |
| --- | --- | --- |
| 核弹/闪电：炸敌方空地 | `offensive_cell_clear` | — |
| 铁幕：罩住**自家有部队**的格子 | **`defensive_cell_set`** | 用 `defensive_cell_clear` 会让 AI 在自家找**空地**去罩 —— 罩空地没意义，于是**一发都不放** |
| 超时空：把自家部队送到**敌方有东西**的格子 | **`offensive_cell_set`** | 用 `offensive_cell_clear` 会挑敌方空地当落点，没有可传送的目标 → 空转 |

**这就是 2.7 的实际翻车方式**：核弹和闪电能用（模式选对了），铁幕和超时空一发不放（模式选错）。
另外这两个作用于**自家单位**的超武还要 `SW.AffectsHouse=yes`，否则 AI 不会把目标选在自己地盘上。

> 如果铁幕仍不放，按顺序**一次只改一个值**试：
> `defensive_cell_set` → `defensive_cell_set,attacked` → `attacked`。
> 超时空：`offensive_cell_set` → `defensive_cell_set` → 放弃（它是两段式超武，
> 「先选自己部队、再选落点」，引擎可能本来就没有对应的 AI 发射路径）。
> `SW.AITargeting` 支持逗号分隔多个词，构建期会逐个校验。

**不动的**：`ForceShieldSpecial`（本来就在放）、`ParaDropSpecial`、`SpyPlaneSpecial`、
`PsychicRevealSpecial`、`ChronoWarpSpecial`（`GADUMY` 是 `AIBuildThis=no`，AI 造不出来）。

### 13.1.2 三个「无头判定器」全部失效（2.9 实测记录）

想把「这个键到底被不被解析」变成可测的是非题，试了三条路，**全都不可用**。
记在这里，免得以后又从头试一遍：

| 判定器 | 期望 | 实测结果 | 结论 |
| --- | --- | --- | --- |
| `--probe` 的 `rules_digest` | 解析后规则的摘要：改注释不变、改活键变 | **改一条注释它也变** | 它是**文件内容哈希**，不是语义摘要。`tools/probe_rules.py --selftest` 一次就能证伪 |
| 非法值是否被拒绝 | 写 `bogus` 应当报错 | `[NukeSpecial] Type=BogusType`、`SW.AutoFire=bogus`、甚至 `SW.TotallyBogusKey=1` **全部静默接受** | 引擎对未知键/非法值一律不吭声，**永远观察不到"被拒绝"** |
| 录像 `replays/*.json` | 记录超武发射指令 | 每局只有 **4–5 条**本地玩家指令，没有 AI 动作 | 录像只存玩家输入，看不到 AI |

再加一条：**只有 `superweapon::force_shield` 会写日志**，核弹/闪电/铁幕的发射都不写。
所以「AI 到底放没放超武」这件事，**只能进游戏看**。

> 方法论教训：**先确认判定器有效，再用它下结论**。
> 这次三条路都是先写了自检（注释/活键/死键三测、对照用例），才没把"摘要变了"
> 误当成"键被解析了"——否则会得出完全相反的结论。

### 13.1.3 铁幕/超时空：一个「是不是我们自己把机会弄没了」的对照实验

原版铁幕的**真实实现**在抽取源码里（`src__sim__superweapon__iron_curtain.rs`）：
`SuperClass::Launch` 的 **case 1**，作用于目标格周围 **3×3 格**，
把该范围内**所有物体**逐个套上铁幕。也就是说它需要**一格**，而且那一格周围得**有自家单位**。
超时空更严：它是 `two_stage`（先选自家单位所在格、再选落点），需要**一簇停在那里的部队**。

本模组恰好把这种"集群"消掉了：

| 我们做的事 | 后果 |
| --- | --- |
| 151 支队伍换成 `ZAIATK01-G`（不集结、出生即冲锋） | 部队一出来就散开、持续移动 |
| 地图 `AIHuntAll` 每 20 秒把槽位 1–119 全部 All to Hunt | 临时聚起来的部队每 20 秒再被打散 |

所以有一个很有力的怀疑：**不是 AI 不想放，而是它找不到一个 3×3 里塞着自家部队的格子**。
这也解释了为什么核弹/闪电正常 —— 它们要的是"敌方格子"，那种格子遍地都是。

**判定方法（单变量）**：

```bash
python tools/build_mod.py --rules-dir "<原版规则目录>" \
    --out "<游戏目录>/Mods/SuperAI-assembly" --assembly-teams
```

`--assembly-teams` 是**诊断开关**（默认关）：它只跳过"把队伍脚本换成不集结脚本"这一步，
让 AI 恢复原版"先回基地集结、再成队出击"。产出的模组与正式版**只差这 160 行 `Script=`**
（`rulesmd.ini`/`artmd.ini` 逐字节相同，其余 `aimd.ini` 行也完全相同）。

在 Options → Mods 切到 `超级AI 诊断版（队伍集结）`，开同一张图看 5–10 分钟：

| 结果 | 结论 | 下一步 |
| --- | --- | --- |
| **集结版会放铁幕/超时空** | 我们的进攻逻辑确实消灭了触发条件 | 谈取舍：队伍在基地停留几秒、或把 All to Hunt 从 20 秒放宽到 45–60 秒 |
| **两版都不放** | 与进攻逻辑无关，是引擎没有「作用于自家单位」的 AI 发射路径 | 记为引擎限制，停止调配置 |

> 为什么必须靠人眼：超武发射**不写日志**（只有 `force_shield` 写）、录像只存玩家指令、
> `--probe` 没有模拟模式（`-h` 只有 `-SPAWN`，能开一局但看不到结果）。
> 上面三个判定器在 §13.1.2 里已经逐一实测失效。

### 13.1.4 根因：2.4 把「放超武的队伍脚本」一起覆盖掉了

**AI 放铁幕/超时空，靠的不是超武 AI，而是队伍脚本动作。** 这是抽取源码里能直接读到的
（`src__sim__team_script_vm__actions.rs`）：

| 脚本动作 | 函数 | 含义 |
| --- | --- | --- |
| 53 | `team_action_gather_at_enemy_base` | **集结到敌方基地** |
| 54 | `team_action_regroup_at_base` | 回自家基地集结 |
| 5 | — | 等待 |
| **55** | `team_action_iron_curtain` | **对本队放铁幕** |
| **56 / 57** | `team_action_chronoshift` | **超时空传送本队** |
| 49 | — | 进攻 |

零售数据里这套东西**早就写好了**：

```
[Soviet Iron Curtain Team]  Script=0C31EA4C-G
   0C31EA4C-G = 0=53,0 集结到敌方基地 → 1=5,10 等待 → 2=55,0 放铁幕 → 3=49,0 进攻 → …
[Allied Chrono-Sphere Unit] Script=0CAC55CC-G
   0CAC55CC-G = 0=54,0 回基地集结 → 1=57,9 超时空传送 → 2=5,10 → 3=49,0 进攻 → …
```

配套的触发器也在，**条件就是"超武快好了"、权重 5000**：

| 触发器 | 条件 | 权重 |
| --- | --- | --- |
| `Soviet Iron Curtain` | **5 = 铁幕快好了** | 5000 |
| `Soviet Iron Curtain Easy` | 5 | 5000/10/5000 |
| `Allied C-Sphere Easy/Medium/Hard` | **6 = 超时空快好了** | 5000 |

**所以"选一队集结到敌人门口然后罩上"根本不需要我们发明 —— 零售就是这么做的。**

**问题出在 2.4**：那次"把所有非 MCV 队伍的 `Script=` 统一换成 `ZAIATK01-G`"，
把引用这 4 个脚本的 **9 支队伍**（`Soviet Iron Curtain Team`、`Allied Chrono-Sphere Unit`、
`Soviet Apoc Hard/Medium`、`Soviet Armor Hard`、`Russian Tesla Tank`、`Libyan Boom`、
`Soviet Iron Curtain Unit Easy`）的脚本一起覆盖了。于是：

- 触发器还在（条件 5/6、权重 5000，命中时独占抽签）；
- 但它拉出来的队伍脚本已经变成"冲锋"，**放超武那一步被删掉了**；
- 表现就是：AI 照常造铁幕/超时空建筑（日志 `placed NAIRON` 912 次），**却永远不放**，
  而且**日志里一个字都看不出来**。

核弹/闪电不受影响，因为它们由引擎自己的超武 AI 发射，不走队伍脚本。

**修复**：`build_aimd` 现在先扫描源 aimd 的每个脚本段，找出含 55/56/57 动作的脚本，
**这些脚本对应的队伍保留零售脚本**（和 MCV 队伍同样待遇）。产物里
"保留超武脚本的队伍数" 从 **0 → 9**（与零售一致）。

**防回归**：新增 `assert_superweapon_teams_intact` —— 产物里必须至少各有一支队伍使用
"含铁幕动作"和"含超时空动作"的脚本，否则**构建直接失败**。
这正是 2.4 该有却没有的守卫：一次"统一换脚本"就能静默删掉整套超武使用路径。

> 顺带纠正之前两轮的判断：`SW.*` 那批键不是这两个超武的关键
> （它们可能确实无效，但对核弹/闪电那四个是有效的，所以保留不动）。
> 真正的原因是**队伍脚本**，跟 `SW.AITargeting` 的取值无关。

### 13.2 证据链（为什么这么判断）

| 证据 | 出处 |
| --- | --- |
| AI **确实会**放超武 | 日志：`sim::superweapon::force_shield  ForceShield launched at (657,293) by 'Computer2'` |
| 但进攻型一次都没放过 | 全日志没有任何 `SuperWeapon launch queued` / 核弹 / 闪电风暴 / 心灵控制器记录 |
| 引擎会记录发射 | 二进制里有日志串 `SuperWeapon launch queued: owner=` |
| 引擎实现了 Ares 的 SW 扩展 | 二进制键名：`SW.AllowPlayer SW.AllowAI SW.AutoFire SW.ManualFire SW.AffectsHouse SW.UseAITargeting SW.AITargeting SW.RequiresTarget SW.FireIntoShroud SW.Shots SW.AlwaysGranted` |
| `SW.AutoFire` 就是「自动发射」那条路 | `house_state.rs:891`：「launched that was neither **PostClick** nor **`SW.AutoFire`**」——发射只分「玩家点击」和「自动」两类，AI 只能走后者 |
| `SW.AITargeting` 的合法取值 | 二进制：`offensive_cell_clear`、`defensive_cell_clear`、`offensive_cell_set`、`defensive_cell_set`、`attacked`、`lightningstorm_inactive`、`dominator_inactive` |

**为什么只算「中」等级**：真正决定 AI 是否发射的代码
（`superweapon/` 下除 `iron_curtain.rs` 之外的模块）**不在 93 文件抽取集里**，
所以这是「按引擎自身的键名与语义推导 + 有旁证」，不是读源码得出的定论。
`assert_superweapon_autofire` 只保证「键写对了、值合法」，**不能保证引擎真的会开火**。

### 13.3 一个必须记住的误判

`AISuperDefenseProbability` / `AISuperDefenseFrames` / `AISuperDefenseDistance`
**不是**这个问题的开关。零售注释写明它们只管 **ForceShield**
（"this is the percent chance to use ForceShield"）。
这也正好解释了为什么偏偏只有 ForceShield 在放 —— 它是唯一走那条通道的超武。
看到「只有 ForceShield 生效」时，不要以为「AI 会用超武，所以进攻型的只是没瞄准好」。

### 13.4 怎么验证

进游戏（**无法用脚本自测**：引擎没有无头模拟入口，`--probe` 只加载规则和地图）：

1. 让一个 AI 造出核弹井/天气控制器/心灵控制器，等它充满；
2. 应看到它**自动**把超武丢到敌方基地的空地上；
3. 若仍然不放，按顺序试，**每次只改一个变量**：
   - 去掉 `SW.RequiresTarget`（某些实现里它会让找不到目标的超武一直等待）；
   - 把 `SW.AITargeting` 换成 `attacked`；
   - 暂时把 `RechargeTime` 从 `10` 改小，确认「是不是根本没充满」这个前提。

---

## 14. 防御选型：为什么 AI 防空造得少（3.1 修掉）

### 14.1 机制：**先选类别，再选建筑**

`ai_base_defense.rs`（`AI_ChooseNextProduction` 的移植，逐行可查）对每个 `-1` 节点这样选：

1. 把本户每栋建筑的 `AntiAirValue` / `AntiArmorValue` / `AntiInfantryValue`
   按**象限**累加，取总量最小的象限（"最弱象限"）的**占比**；
2. 取**指定敌人**的兵力构成（air / vehicles / infantry），按 `AIForcePredictionFudge=` 加噪声；
3. **类别 =（敌人占比 − 我方占比）最大的那一项**；
4. 候选 = `[AI] Allied/Soviet/ThirdBaseDefenses=` 里**该类别值 > 0** 的建筑；
5. 在候选里按该类别的值加权随机；该类别没有候选才回退 armor → infantry → air。

**关键**：一栋建筑能不能被造，先看它**是不是这个类别的候选**。
所以"某种防御造得少"往往不是概率问题，而是**它压根不在多数类别里**。

### 14.2 零售数值的坑

| 建筑 | Inf | Armor | Air | 后果 |
| --- | --- | --- | --- | --- |
| `NASAM` 盟军爱国者 | **0** | **0** | 25 | **只在 air 类别出现** |
| `NAFLAK` 苏军防空炮 | **0** | **0** | 25 | **只在 air 类别出现** |
| `YAGGUN` 尤里盖特机炮 | 25 | 10 | 25 | **三个类别都是候选** |

air 类别要胜出，得让**敌人的空中占比**超过我方防空覆盖 —— AI 之间几乎没有空军，
所以 air 很少赢，盟/苏的防空炮也就很少被选。日志实测（同一份 log）：
`YAGGUN` 62 次 > `NASAM` 41 次 > `NAFLAK` 29 次；盟军防空约占其防御 17%、苏军约 12%。

> **和"打掉才重建"无关**：重建只管"节点空了要不要再建一栋"，
> "建哪一种"完全由上面的类别逻辑决定。防空少是**选型**问题，不是产量问题。

### 14.3 修法：给盟/苏防空炮尤里那个形状

```ini
[NASAM]  AntiInfantryValue=25   AntiArmorValue=10     ; 零售 0 / 0
[NAFLAK] AntiInfantryValue=25   AntiArmorValue=10     ; 零售 0 / 0
```

- **防御节点数一个没动**（`*BaseDefenseCounts` 仍是零售 `25/20/6`），
  建造强度不变，只是同样这些节点里防空被选中的概率从"几乎 0"提到和盖特机炮同级；
- 权重分布：infantry 25/100、armor 10/55、air 100%（唯一候选）；
- 想更激进就调大这两个数（如 30/15），想收一点就 15/5 —— 一个旋钮。

`assert_aa_defenses_competitive` 守住这一点：三个防空建筑的三类值必须**都非零**，
否则构建失败 —— 因为 `0/0/25` 这种"看起来正常、实际被架空"的数值最容易在换数据时静默回归。

### 14.4 怎么量

`tools/analyze_log.py` 现在会报防空占比，并带一条 `AA_MIN=20%` 的闸门：

```
AA: 6 of 17 defences (35%)
PASS  AA defences 6 of 17 (35% of defences, gate 20%)
```

改动前的基线：`NASAM` 41 / `NAFLAK` 29 / `YAGGUN` 62（占各自防御 12–17%）。

---

## 15. 空军与防空部队：为什么「看不到」以及怎么加（3.2）

### 15.1 结构性原因（不是随机性问题）

单位生产**不写日志**（只有建筑 `placed` 写），所以这一节靠的是数据本身：

| 事实 | 数字 |
| --- | --- |
| 零售 TaskForce 总数 | 132 |
| 含**飞行单位**的 TaskForce | **7** |
| 用这些 TaskForce 的 TeamType | 11 支，**全部 `Max=1`** |
| 含**防空单位**的 TaskForce | 37 |
| 含防空单位的 AITrigger | 46 / 165 |
| 含飞行单位的 AITrigger | 10 / 165，权重只有 20–70 |

**空军为什么几乎看不见**：11 支空军队伍全部 `Max=1` —— 一个 AI 同一时刻
**最多只有一支**空军队伍在场；而且其中一支是 1 架基洛夫。权重又只有 40–70，抽中概率和普通进攻队一样。

**防空为什么比例低**：46/165 的触发器才带防空单位，其余 119 条组出来的队伍没有防空。

### 15.2 改法（`boost_air_and_aa`）

| 改动 | 数值 |
| --- | --- |
| 空军队伍上限 | `Max` `1` → **`6`**（9 支队伍） |
| 每支空军队伍的飞机数 | `max(零售+1, 3) × 2` → **6–10 架**（上限 16） |
| 空军触发器权重 | **×3**（上限 1500） |
| 防空触发器权重 | **×2**（上限 1500） |

（3.2 先做到 `Max=3`、每队 3–5 架；3.3 按要求把队伍数与规模各再翻一倍。）

- 权重是**按难度分三档**同时乘的，难度之间的相对关系不变；
- 上限 1500 保证不会盖过 5000 权重的接管触发器（MCV 扩张 / 超武）；
- 只改权重和数量，**没有新增队伍类型**，所以不会破坏 TaskForce 的兵种搭配。

结果：空军从「每户同时最多 1 支、1–4 架」变成「**最多 6 支、每支 6–10 架**」；
带防空的队伍在抽签中的权重占比从约 28% 提到约 44%。

实际数值（零售 → 3.3）：黑鹰 4→10、入侵者 4→10、入侵者支援 2→6、
基洛夫（硬）3→8、基洛夫（中）2→6、基洛夫（反巨炮）1→6。

> **规模提醒**：6 队 × 10 架 = 单户理论峰值 60 架。战机便宜（1200/2000）、
> 10 万初始资金够用，但单位数明显上升，可能影响帧率；超编飞机还会在空中排队待降。

### 15.3 防回归

`assert_air_and_aa_boosted`：产物里必须有 ≥5 条空军 TaskForce 条目且每支空军队伍的
飞机数 ≥3，否则构建失败。用它对着零售 aimd 跑会直接报错
（`air task force entry ORCA has only 2 aircraft`），所以「改回零售」这种回归会被拦住。

### 15.4 想再调

| 想要 | 改哪里 |
| --- | --- |
| 更多空军队伍 | `AIR_TEAM_MAX`（6 → 8/10）、`AIR_WEIGHT_FACTOR`（3 → 4/5） |
| 单队飞机更多 | `AIR_SIZE_FACTOR`（2 → 3）或 `AIR_UNIT_MIN`（3 → 4/5） |
| 更多防空 | `AA_WEIGHT_FACTOR`（2 → 3） |
| 回退到 3.2 | `AIR_SIZE_FACTOR=1`、`AIR_TEAM_MAX=3` |

### 15.5 为什么「打完一批，很久不造第二批」（3.4 修掉）

**原版没有空军冷却时间**，真正的原因在触发器的**胜率反馈**（`AiTriggerTrackRecord`，
`team_script_vm.rs`，对应 `RegisterSuccess @ 0x0041FD60` / `RegisterFailure @ 0x0041FE20`）：

- 每条 AI 触发器有一个运行时权重，初始 = `weights[0]`（hard 档）；
- 队伍**被摧毁时**结算：达成脚本动作 `49`（进攻）算成功，否则算**失败**；
- 失败 `-= AITriggerFailureWeightDelta`（零售 **−50**），成功 `+= 20`；
- 结果**钳制在 `[weights[1], weights[2]]`** —— 也就是**中档 / 简单档的权重**之间。

飞机是最容易在到达「进攻」那一步之前就被打掉的东西，所以空军触发器几乎每次都被判失败：

| 触发器（3.3 之后） | 初始 | 地板 `weights[1]` | 几次失败到底 |
| --- | --- | --- | --- |
| `Allied Harrier - H1` | 150 | **30** | 3 次 |
| `Soviet Kirov Medium` | 210 | **30** | 4 次 |
| `Nation Korea` / `Kirov Hard` | 1500 | **30** | 30 次 |

砸到 30 之后就停在地板 —— 而普通进攻触发器是 40–70，所以空军「再也抽不到」。
我们的进攻队不受影响：`ZAIATK01-G` 第二步就是 `49`，基本都算成功。

**叠加因素**：我们把 `DissolveUnfilledTeamDelay` 改成过 900（15 秒）。
一支 10 架飞机的队伍，第一架还没下线就被判「空队伍解散」，**这也算一次失败**。

**修法**：

1. 空军触发器的三个权重槽**全部设成三者最大值** → 钳制区间退化成一个点 → **权重恒定**，
   失败多少次都不掉（`210/210/210`、`1500/1500/1500`）；
2. `DissolveUnfilledTeamDelay` **900 → 2400**（40 秒），让慢队伍有机会出现第一个成员。

**防回归**：`assert_air_and_aa_boosted` 现在要求每条空军触发器的 `weights[1] == weights[2]`，
否则构建失败（实测会把 `210/30/210` 这种形状报出来）。

> 副作用：空军压力变成**恒定**而不是自适应 —— 这正是要的效果；
> 但如果你之后觉得地面进攻变慢，可以把 `DissolveUnfilledTeamDelay` 单独回调到 1500。

### 15.6 飞行兵也是空军：`JUMPJET` 被错分到防空分支（3.5 修掉）

`AIR_UNITS` 原来只列了**飞机**（`ORCA/BEAG/ZEP/...`），而火箭飞行兵 `JUMPJET`
同时满足两件事：**会飞**、**能对空**。于是它落在了 `AA_UNITS` 里，
3.2–3.4 的空军强化一条都没落到它身上：

| 队伍 | 3.4 实际状态 |
| --- | --- |
| `Allied Rocketeer - H1` | `Max=1`、5 人、权重 `100/20/100`（**没钉死 → 失败会掉到 20**） |
| `Allied Anit-Grand Cannon`（同用火箭兵编队） | `Max=1`、5 人、权重 `140/20/140` |
| `Allied Grizzly Attack - H3`（6 灰熊 + 4 火箭兵） | `Max=1`、4 人、权重 `100/60/100` |

基洛夫正常、火箭兵稀少，差别**不在原版数据**（零售两边都是 `Max=1`：
基洛夫 3 支队伍 1–3 架，火箭兵 2 支队伍 4–5 人），而在**分类**：
`ZEP` 在 `AIR_UNITS` 里，`JUMPJET` 不在。

**修法**：把 `JUMPJET` 加进 `AIR_UNITS`。分支顺序是 `if air / elif aa`，
所以飞行单位**优先按空军**处理，立刻拿到：`Max` → 6、人数 `max(n+1,3)×2`、权重 ×3 并钉死。

| 队伍 | 3.5 结果 |
| --- | --- |
| `Allied Rocketeer - H1` | `Max=6`、**12 人**、权重 `150/150/150` |
| `Allied Grizzly Attack - H3` | `Max=6`、**10 人** + 6 灰熊、权重 `150/150/150` |
| `Allied Anit-Grand Cannon` | `Max=6`、**12 人**、权重 `210/210/210` |

**防回归**：守卫新增两条 —— 必须存在 `JUMPJET` 编队条目，且每一条 ≥6 人。
实测：把火箭兵改回 5 人会报 `air task force entry JUMPJET has only 5 aircraft`；
整条删掉会报 `no JUMPJET task-force entry`。
