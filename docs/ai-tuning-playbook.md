# AI 调参实战手册

这份文档回答三个问题：**AI 的建造决策链到底怎么走**、**改哪个键能影响哪一步**、
**哪些看起来能改的键其实是死的**。它同时是一份踩坑记录——每一条都写清「症状 →
当时的错误结论 → 实际原因」，因为本项目在同一类问题上反复浪费过时间。

> 适用引擎：VERA20k 0.4.0（Ares 扩展开启）。
> 本文所有「引擎行为」结论都可以在 `F:\Games\VERA20K\.workbuddy\work\src\` 下的
> 抽取源码里逐行核对，括号内给出文件名与函数名。

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
     ├─ Ares AIBuildCounts：每个类型的首节点后面随机撒 count-1 个副本
     ├─ 防御节点：*BaseDefenseCounts 个 "-1" 节点，随机位置（≥3）
     └─ 围墙节点：扫描基地周长时按需追加
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
| 某个建筑造几个 | Ares `AIBuildCounts` | 铁律 2，位置是随机的 |
| 科技树种类 | `[AI] BuildConst/BuildPower/BuildRefinery/BuildBarracks/BuildWeapons/BuildTech/BuildRadar` | 只影响种子与 `POWER`/`PROC` 这类前置组的解析 |
| 防御数量 | `Allied/Soviet/ThirdBaseDefenseCounts` | 是**计划数**，实际落地会少（铁律 3） |
| 防御 vs 围墙 | `AIPickWallDefensePercent` | 围墙每格一个节点，非常吃预算 |
| 矿场数量 | 有矿车：`AIExtraRefineries`；无矿车（Yuri）：`AISlaveMinerNumber` | 见 §4 |
| 兵种/组队 | `aimd.ini` 的 `[TeamTypes]`/`[AITriggerTypes]` | 权重 5000 是接管标记，别乱用（§5） |

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
cd F:\Games\VERA20K-SuperAI

# 1. 只改 tools/build_mod.py —— 它是唯一真相源，直接改发布版 INI 会被下次重建覆盖
#    （规则：RULES_EDITS / SECTION_KEY_EDITS / BUILD_COUNTS）

# 2. 重建到临时目录并确认幂等
python tools\build_mod.py --rules-dir "F:/Games/red2" --out %TEMP%\rebuild

# 3. 逐字节对齐仓库
#    重建结果必须与 mod/SuperAI/* 完全一致，否则说明有人手改过发布文件
#    （用 Get-FileHash -Algorithm SHA256 比对三个文件）

# 4. 无窗口加载校验（规则语法、地图、Ares）
python tools\check.py --game-dir "F:/Games/VERA20K"

# 5. 装进游戏
python tools\install.py --game-dir "F:/Games/VERA20K"

# 6. 打一局，然后判读日志结构（不看强弱，只看有没有建对）
python tools\analyze_log.py --log "F:/Games/VERA20K/logs/ra2.log" --session last
python tools\analyze_log.py --log "F:/Games/VERA20K/logs/ra2.log" --session all --strict
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

### 6.2 改动前基线（2.1，2026-11-22 的日志）

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

---

## 8. 源码位置速查

路径前缀 `F:\Games\VERA20K\.workbuddy\work\src\`（抽取版，只读）。

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
