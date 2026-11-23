# Changelog

本项目在 2026-11-22 从零迭代到 2.0，同日继续到 3.0；以下是可复现的功能节点。

## 3.0 — 铁幕/超时空：根因是 2.4 把「放超武的队伍脚本」覆盖掉了

**AI 放铁幕/超时空靠的不是超武 AI，而是队伍脚本动作**（抽取源码可直接读到）：

| 脚本动作 | 含义 |
| --- | --- |
| 53 | `team_action_gather_at_enemy_base` —— 集结到敌方基地 |
| 5 | 等待 |
| **55** | `team_action_iron_curtain` —— **对本队放铁幕** |
| **56 / 57** | `team_action_chronoshift` —— **超时空传送本队** |
| 49 | 进攻 |

零售早就写好了这条链：

```
[Soviet Iron Curtain Team]  0C31EA4C-G = 0=53,0 → 1=5,10 → 2=55,0 放铁幕 → 3=49,0 进攻
[Allied Chrono-Sphere Unit] 0CAC55CC-G = 0=54,0 → 1=57,9 超时空 → 2=5,10 → 3=49,0 进攻
```

配套触发器也在，条件是**「超武快好了」、权重 5000**：
`Soviet Iron Curtain`（条件 5）、`Soviet Iron Curtain Easy`（5）、
`Allied C-Sphere Easy/Medium/Hard`（条件 6）。

**2.4 的「所有非 MCV 队伍统一换成 `ZAIATK01-G`」把这 4 个脚本一起覆盖了**，
引用它们的 **9 支队伍**（`Soviet Iron Curtain Team`、`Allied Chrono-Sphere Unit`、
`Soviet Apoc Hard/Medium`、`Soviet Armor Hard`、`Russian Tesla Tank`、`Libyan Boom`、
`Soviet Iron Curtain Unit Easy`）于是只会冲锋、不再放超武。
表现就是：AI 照常造铁幕/超时空建筑（`placed NAIRON` 912 次），**永远不放，日志毫无痕迹**。
核弹/闪电不受影响 —— 它们由引擎自己的超武 AI 发射，不走队伍脚本。

- `build_aimd` 现在会扫描源 aimd 的每个脚本段，**含 55/56/57 动作的脚本所对应的队伍保留零售脚本**；
  产物里"保留超武脚本的队伍数" **0 → 9**（与零售一致）。
- 新增 `assert_superweapon_teams_intact`：产物里必须至少各有一支队伍使用含铁幕 / 含超时空动作的
  脚本，否则**构建失败**。这正是 2.4 该有却没有的守卫。
- 顺带纠正前两轮的判断：`SW.*` 那批键**不是**这两个超武的关键（对核弹/闪电有效，保留不动），
  真正的原因是队伍脚本，与 `SW.AITargeting` 取值无关。

## 诊断 — 铁幕/超时空：是不是我们的进攻逻辑消灭了触发条件

2.9 之后这两个仍不发射。从抽取源码（`src__sim__superweapon__iron_curtain.rs`，真实实现）确认：
铁幕是 `SuperClass::Launch` 的 **case 1**，作用于目标格周围 **3×3**，罩住该范围内**所有物体**；
超时空是 `two_stage`（自家单位格 → 落点）。**两者都需要一簇停在原地的自家部队。**

而本模组恰好消灭了集群：160 支队伍不集结、出生即冲锋，加上地图每 20 秒 All to Hunt 再打散一次。
所以"AI 找不到机会"是很强的怀疑——这也解释了为什么核弹/闪电正常（它们只要敌方格子）。

新增**诊断开关**（默认关）：

```bash
python tools/build_mod.py --rules-dir "F:/Games/red2" \
    --out "F:/Games/VERA20K/Mods/SuperAI-assembly" --assembly-teams
```

`--assembly-teams` 只跳过"换不集结脚本"这一步，让 AI 恢复原版"先集结再出击"。
产物与正式版**只差 160 行 `Script=`**（已校验：`rulesmd.ini`/`artmd.ini` 逐字节相同，
`aimd.ini` 的非 `Script` 行完全相同），所以对照是单变量的。

判定：集结版**会放** ⇒ 是我们的进攻节奏消灭了条件，再谈取舍；
**两版都不放** ⇒ 引擎没有「作用于自家单位」的 AI 发射路径，记为限制并停止调配置。

## 2.9 — 铁幕 / 超时空：写全所有候选键，并把「测不出来」这件事记下来

实测反馈：2.8 之后这两个**仍然不发射**（核弹/闪电正常）。这一轮先查了两个前提：

- **建筑是有的**：日志 `placed NAIRON` **912 次**、`placed GACSPH` **121 次**
  —— 不是"没造出来"，纯粹是"不开火"。
- **没有任何无头手段能判断某个 `SW.*` 键是否生效**（三条路全部实测失效）：

| 判定器 | 实测结果 |
| --- | --- |
| `--probe` 的 `rules_digest` | 改一条**注释**它也变 → 是文件哈希，不是解析摘要 |
| 非法值是否被拒绝 | `Type=BogusType`、`SW.AutoFire=bogus`、`SW.TotallyBogusKey=1` **全部静默接受** |
| 录像 `replays/*.json` | 每局只有 4–5 条**玩家**指令，没有 AI 动作 |

（另外只有 `superweapon::force_shield` 会写日志，其余超武发射不写。）

因此改成**一次性写全所有候选键**，把"键名/取值不对"这个可能性排除掉：

```ini
SW.AITargeting=defensive_cell_set          ; 铁幕
SW.AITargeting.Constraints=defensive_cell_set
SW.AITargeting.Preference=defensive_cell_set
SW.AffectsHouse=yes
SW.AffectsTarget=yes
SW.AIRequiresTarget=no
```

超时空同理，取值换成 `offensive_cell_set`。`.Constraints`/`.Preference` 这两个键名在二进制里存在
（Ares 把瞄准规则拆成"约束/偏好"），被忽略的键不会造成伤害。

新增 `tools/probe_rules.py`：对临时 `Mods/_probe` 跑变体并比对摘要，
`--selftest` 会先验证摘要是否真的是语义摘要（**这次它当场证伪了自己**）。
这个工具的价值不是"测通了"，而是把"哪些判定器不可用"变成可复现的事实。

> 若 2.9 仍不发射，结论定为：**引擎没有「作用于发射方自家单位」的超武 AI 发射路径**，
> 记为引擎限制，不再试配置。`HouseSuperWeaponTargets` 只建模 `nuke_target`/`emp_target`
> 也支持这个判断。

## 2.8 — 铁幕 / 超时空：瞄准模式选错了

2.7 之后实测反馈：**核弹和闪电风暴正常开火，铁幕和超时空一发不放**。
这两个恰好是**唯一两个作用于自家单位**的超武 —— 问题出在 `SW.AITargeting` 的取值上。

那 7 个取值是**同一个枚举**的变体，成对存在：
`offensive_cell_clear` / `defensive_cell_clear` / `offensive_cell_set` / `defensive_cell_set`
/ `attacked` / `lightningstorm_inactive` / `dominator_inactive`。

- **`cell_clear` = 空格子，`cell_set` = 格子里有东西**；`offensive` = 敌方地盘，`defensive` = 自家地盘；
- 2.7 给铁幕写的是 `defensive_cell_clear` → AI 在自家找**空地**去罩，罩空地毫无意义 → 不开火；
- 超时空写的是 `offensive_cell_clear` → 挑敌方空地当落点，没有可传送的目标 → 空转。

改成：

| 超武 | 2.7 | 2.8 |
| --- | --- | --- |
| `IronCurtainSpecial` | `defensive_cell_clear` | **`defensive_cell_set`** + `SW.AffectsHouse=yes` |
| `ChronoSphereSpecial` | `offensive_cell_clear` | **`offensive_cell_set`** + `SW.AffectsHouse=yes` |
| 核弹 / 闪电 / 心灵 / 基因 | `offensive_cell_clear` | **不动**（已实测可用） |

`SW.AffectsHouse=yes` 只加给这两个「作用于自家单位」的超武：不加的话 AI 不会把目标选在自己地盘上。
`assert_superweapon_autofire` 放宽为支持**逗号分隔多个词**（逐个校验词表），
便于按回退阶梯试 `defensive_cell_set,attacked`。

> 证据等级：核弹/闪电**已由实测确认**；铁幕/超时空是本次按 `cell_clear`/`cell_set` 语义修正，
> **仍待实测**。若仍不放，按 `docs/ai-tuning-playbook.md` §13.1 的回退阶梯一次改一个值。

## 地图 — 新增 `SuperAI-IceLake-120-NoOre.yrm`（冰湖 120 人）

**地形一格不动**：`[IsoMapPack5]` 逐字节相同（43080 格），`Size`/`LocalSize`/`Theater`
也原样保留 —— 只改出生点列表。8 个出生点 → 120 个：

- 玩家位沿用原 `wp0`（`(180,27)`）——这张图的 0 号位**本来就在右上角**，独占；
- 119 个电脑只落在**原图 7 个电脑出生点所站的同一块冰面**（`tile 696` / 高度 `1`，
  10528 格，其中玩家左下方向 10209 格），所以必然可站；
- 排布用**最远点采样**（先取离玩家最远的一格，再反复取离已选点最远的格子），
  铺满后丢掉最靠近玩家的 4 个，把右上角留给玩家；
  实测相邻间距 **min 11 / 中位 13 / max 19 格**，基本等距，且按要求**不预留扩张空间**；
- `[Header]` 的 `WaypointN`/`NumberStartingPoints` 重写为 120
  （引擎换算 `((x-y+512)/2, (x+y+1)/2)`，能精确复现原图 8/8 个出生点）；
- `[Basic]` 的 `MaxPlayer`/`MaxPlayers` = 120；
- 触发器仍是原来三条（揭图 / 铁幕 / All to Hunt），只把 `All to Hunt` 的动作
  从槽位 1–7 扩到 1–119（沿用 10 槽分段 → 12 条），否则槽位 8+ 永远不出门。

构建：`tools/build_maps.py ice120`（原地改出生点，`--spacing N` 可要求最小间距），
**逐字节可复现**；构建期断言会核对地形/尺寸/剧场零改动。
`--probe` 报告 `max_start_waypoints: 120`，`check.py` 六张图全部 `OK`。

## 2.7 — 超级武器充满即自动发射

- 零售数据的 12 个超武段**一条 `SW.*`（Ares 超武扩展）键都没有**，AI 停在默认瞄准状态：
  ForceShield 这种自施放超武照常工作，**带目标**的核弹/闪电风暴/心灵控制器从不发射。
- 2.7 起给 AI 能造出来的 6 个带目标超武显式写：

```ini
SW.AllowPlayer=yes
SW.AllowAI=yes
SW.AutoFire=yes        ; 关键：AI 没有「玩家点击」这条路，只能走自动发射
SW.UseAITargeting=yes
SW.RequiresTarget=yes
SW.AITargeting=offensive_cell_clear   ; 铁幕用 defensive_cell_clear
```

  对应超武与建筑：`NukeSpecial`/`NAMISL`、`LightningStormSpecial`/`GAWEAT`、
  `PsychicDominatorSpecial`/`YAPPET`、`GeneticConverterSpecial`/`YAGNTC`、
  `ChronoSphereSpecial`/`GACSPH`、`IronCurtainSpecial`/`NAIRON`（全部 `AIBuildThis=yes`）。
- 不动的：`ForceShield`（本来正常）、`ParaDrop`/`SpyPlane`/`PsychicReveal`（支援类）、
  `ChronoWarp`（`GADUMY` 是 `AIBuildThis=no`，AI 造不出来）。
- 新增 `assert_superweapon_autofire`：校验 6 个段的键齐全、`SW.AITargeting` 必须落在引擎
  认识的词表里（`offensive_cell_clear` / `defensive_cell_clear` / `offensive_cell_set` /
  `defensive_cell_set` / `attacked` / `lightningstorm_inactive` / `dominator_inactive`）——
  拼错会被**静默丢弃**；并禁止把这些键写进那 5 个不该动的段。
- **证据等级：中**。决定 AI 是否发射的代码不在 93 文件抽取集里，本结论由「引擎自身的键名 +
  `house_state.rs` 对 `SW.AutoFire` 的说明（发射只分 PostClick 与 AutoFire 两类）+
  日志里只有 ForceShield 在放」推导而来，**尚未进游戏实测**（引擎没有无头模拟入口）。
  判定步骤与回退顺序写在 `docs/ai-tuning-playbook.md` §13。
- 顺带记一个易误判点：`AISuperDefenseProbability/Frames/Distance` **只管 ForceShield**，
  调它们不会让核弹开火。

## 2.6 — 不造围墙、冷酷 3 兵营 / 5 战车工厂

### 围墙全部关闭

- `AIPickWallDefensePercent`：`10,10,10` → **`0,0,0`**（零售 `50,25,10`）。
  这是引擎里**唯一**的造墙入口：`choose_building` 处理防御节点时先掷
  `RandomRanged(0, 99)`，只有 `draw < AIPickWallDefensePercent` 才调 `build_walls`。
  设为 0 后 AI 永不规划围墙，**而且每一次防御抽签都会落到真枪上**。
- 另一条 `scan_base_perimeter` 只在消费 `-3` 控制节点时跑，遭遇战的重算计划从不插入 `-3`，
  所以这张图里不会走到那条路。
- 新增 `assert_no_walls`：`AIPickWallDefensePercent` 必须全零，否则**构建失败**。
  围墙的副作用（吃防御预算、堵自己出入口）很容易被忘掉，改回来应该是有意识的决定。
- 日志验收：`GAWALL` / `NAWALL` / `YAWALL` 的落地数应为 **0**。

### 冷酷难度给足产能

`AIBuildCounts` 重新引入，但**只给 6 个生产建筑**（2.4 曾整表清空）：

| 类型 | `AIBuildCounts` | 冷酷 | 中等 | 简单 |
| --- | --- | --- | --- | --- |
| `GAPILE` / `NAHAND` / `YABRCK` | `3,1,1` | **3 个兵营** | 1 | 1 |
| `GAWEAP` / `NAWEAP` / `YAWEAP` | `5,1,1` | **5 个战车工厂** | 1 | 1 |

- 向量顺序是**「冷酷, 中等, 简单」**：引擎用 `HouseDifficulty::table_index()` 取值，
  而 `Hard = 0`。
- 值 `n` = 1 个种子节点 + 首节点之后**随机位置**插 `n-1` 个副本；总共只多 6 个节点，
  战车工厂第一次出现的时间仍由种子节点决定，不会重演 1.x「60 → 403 电厂」的偏科。
- 数量是**长期维持**的：被打掉后按「打掉就重建」补回。
- 新增 `assert_build_counts`，拦住三类**静默失效**：段名拼错（引擎读不到）、
  列表少于 3 项（缺的难度退化成 1 个节点）、难度顺序写反（冷酷拿不到 5 个）。

## 2.5 — 让基地铺开到 3 个，并且长期保持

- 新增 3 条 `… MCV - Expand` 的 `[AITriggerTypes]`（每条对应一个阵营）：
  条件「本户建造厂数量 **< 3**」、权重 **5000**、三难度全开。
  于是爬科技阶段一旦能造基地车，就立刻补车去展开，直到拥有 3 座建造厂。
- 3 支 MCV 队伍的 `Max`：`1` → **`2`**（`at_max_teams` 按「队伍数 >= Max」拦截），
  所以可以两台基地车同时在外。
- 与已有的 3 条「建造厂 == 0」救急触发器分工：**0 座 = 救急、少于 3 座 = 扩建**。
  收敛过程：1 座厂 → 出 2 台车 → 展开成 3 座 → 触发器不再命中 → 停；
  任意一座被拆 → 计数落到 2 → 重新补车。
- 比较掩码：`< 3` 即 `0300000000000000` + 48 个 0（小端 word(0)=数量 3、word(4)=运算符 0）；
  零售的 `== 0` 是 `0000000002000000` + 48 个 0。
  新增 `assert_mcv_triggers_well_formed`：掩码必须 64 个十六进制字符、MCV 家族必须 6 条、
  id 不得重复 —— 这些错误本来会被读取器**静默丢弃**。
- 代价：不满 3 座基地期间该户暂停组建新的进攻队（已在场部队不受影响，仍在 All-to-Hunt 下作战）；
  窗口 = 造两台车并展开的时间。

## 2.4 — 化繁为简：原版三难度 + 两条机制

设计收敛成一句话：**让原版三个难度决定节奏，只加「猛攻」和「打掉就重建」。**

### 机制二（新）：被打掉就立刻重建

- `AIRestrictReplaceTime`：`120` → **`0`**（0 = 不限制）。零售 `400`（约 27 秒）的窗口内
  只允许先补墙/防御/电厂；设为 0 后**任何建筑丢失都能立刻重规划**。
- 需要澄清一个常见误解：**重建不是新功能，是引擎原生的节点重规划**。而且本来就分档：
  电厂（`Power>0`）与**所有有武器的建筑**（碉堡/光棱塔/爱国者…）以及贴墙的围墙
  **一直是立即重建**的；兵营/战车工厂/高科/维修厂才受那个时间窗口限制。
- 重建会插队：重建的是同一个节点、位置不变，而 `choose_building` 取最靠前的未满足节点，
  所以「被打掉的东西」天然优先于「还没造过的东西」。
- 连续 `MaximumBuildingPlacementFailures+1`（默认 6）次放不下时节点会被删除，不会无限空转。

### 机制一：猛攻（保留，不再靠调参）

- 160 支队伍不集结、`Aggressive=yes`、`IsBaseDefense=no`（没有守家队 = 家里不留人）；
  3 支 MCV 队伍保留原版部署脚本。
- 3 条「本户 0 座建造厂」的 MCV 触发器 **权重 5000、三难度全开**。
  `5000` 是引擎的 `PRIORITY_WEIGHT`：命中即清空该次抽签的其它触发器，
  于是丢厂时 AI 只做一件事——造基地车。**前提是维修厂可建**，
  新增 `assert_mcv_recovery_fillable` 强制这一对必须同时成立（2.2 就是缺了前提才被它反噬）。

### 撤掉的调参（回原版）

- **`AIBuildCounts` 整表删除**：不再写这个键，Ares 回落到每种一个节点。
  它不是难度旋钮（计划只生成一次、副本随机撒点），2.3 的 6/10/14/28 一并撤销。
- `*BaseDefenseCounts`：`200,200,200` → 回原版 `25/20/6`（三难度各自决定）。
- 67 条进攻触发器的 250 权重与难度位全开 → 回原版；出手频率交回难度。
- TaskForce 编制缩放代码删除（`MULTIPLIER=1` 之后本来就是空操作）。
- `AIHateDelays`、`AITriggerSuccessWeightDelta`、`AITriggerFailureWeightDelta` → 回原版。

### 工具

- `tools/analyze_log.py` 新增 `--rebuilds`：按「同一类型隔 ≥N 秒又在别的格子落地」
  统计重建事件（默认 20 秒）。建筑丢失没有日志，这是唯一的可观测代理指标。
- 解析改为携带时间戳，闸门报告/JSON 输出不变。

## 2.3 — 修掉「AI 一兵不发」，并让基地持续扩建

### 修复：2.2 引入的死锁，AI 不造兵、不进攻

- **根因**：`build_aimd` 把所有非 MCV 队伍类型都改写成 `IsBaseDefense=no`（模组里
  `IsBaseDefense=yes` 的队伍类型数量为 **0**，零售有 12 个），而 2.2 又把
  `UseMinDefenseRule` 改成 `yes`、`MinimumAIDefensiveTeams` 改成 `1`。
  引擎的 `defense_gate` 于是永远要求「先有 1 支守家队才允许组队」，条件永不成立：
  **163 条触发器全部被拒 → 不组队 → 出兵选择器没有需求 → 不造兵 → 不进攻**。
  基地建造走另一条路径，所以日志里毫无异常。
- `UseMinDefenseRule=no`、`MinimumAIDefensiveTeams=0,0,0`、`MaximumAIDefensiveTeams=0,0,0`。
- `tools/build_mod.py` 新增 `assert_defense_gate_consistent`：若 `aimd.ini` 里没有
  `IsBaseDefense=yes` 的队伍类型，却把 `UseMinDefenseRule` 设为 `yes` 或
  `MinimumAIDefensiveTeams` 设为非零，**构建直接失败**并说明原因。

### 扩建：基地会一直往外铺

- `AIBuildCounts` 重新定标（2.2 是 3/2/2/3/2/1/2，压得太狠）：电厂 6、矿场 10、
  兵营 14、**战车工厂 28**、高科 18、雷达 10、维修厂 8（`YADEPT` 4、研磨机 4）。
  原因：计划**整局只生成一次**，每放一栋消耗一个节点，**节点数就是扩张预算**；
  2.2 只剩十几个节点，基地十几栋就静止。量集中在中后期类型，早期电厂保持小
  （缺电由 `power_plant_to_splice` 按需补），避免再次出现「电厂淹没一切」。
- `*BaseDefenseCounts`：`40,40,40` → **`200,200,200`**。防御节点沿基地周长
  **向外**找位置，是最强的扩建驱动（每类插入上限 256）。
- 实测参考：2.2 那一局某 AI 建到 98 栋就停，而 2.1 配置下同一张图单户可到 370 栋。

## 2.2 — 让 AI 建全科技树、修得好基地

- **维修厂改为可建，AI 终于能造基地车**：`[GADEPT]` / `[NADEPT]` / `[YADEPT]` 的
  `AIBuildThis`：零售 `no` → **`yes`**。基地车的前置正好是维修厂
  （`AMCV` = `GAWEAP`+`GADEPT`，`SMCV` = `NAWEAP`+`NADEPT`，`PCV` = `YAWEAP`+`YAGRND`），
  所以在此之前 AI 再富也造不出 MCV，建造厂一被炸就是永久损失。
  改动前的日志里 82,736 行，一条维修厂都没有，正是这个原因。
- **`AIBuildCounts` 从「每类 60」改成分类型分级**：电厂 3、矿场 2、兵营 2、战车工厂 3、
  高科 2、雷达/机场 1、维修厂 2（`YADEPT` 1）、新增回收厂 `YAGRND` 1
  （Ares 零售默认是 1）。原因是副本被插在该类型第一个节点之后的随机位置：
  某一类额定太多，就会把战车工厂、高科、维修厂埋到很后面，AI 迟迟建不出来。
- `AIExtraRefineries`：`2,1,0` → **`0,0,0`**。额外矿场不再占掉基地规划位。
- `AISlaveMinerNumber`：`4,3,2` → **`2,2,2`**。对尤里（不拥有矿车）这个键是矿场复制数，
  同时决定 `YAREFN` 被毁后能不能就地重建。
- `AIPickWallDefensePercent`：`50,25,10` → **`10,10,10`**。围墙以前会挤掉防御规划的名额：
  改动前实测一个基地里有 92 段围墙、只有 63 栋防御建筑。
- `MaximumAIDefensiveTeams` / `MinimumAIDefensiveTeams`：`0,0,0` → **`1,1,1`**，
  `UseMinDefenseRule`：`no` → **`yes`**。每户保留一支守家队，不再全数冲锋。
  （**2.3 已回退**：模组没有守家队类型，这三条这样配会让 AI 完全不组队，见 2.3。）
- 3 个「自己 0 座建造厂」的 MCV 触发器：零售 `70/60/70` 且只在冷酷生效 →
  **250、三难度全开**。刻意**不是** 5000：在这个引擎里权重 5000 是接管标记，
  会把该户其它 AI 触发器全部压掉。
- 新增 `tools/analyze_log.py`：从 `ra2.log` 统计 AI 实际放下了哪些建筑
  （只数 `placed` 成功行，不数规划），按启动/对局切分，用科技树结构判断这一局到底建成了什么。
- 修 `tools/check.py` 的编码：`--probe` 的输出按 UTF-8 解码（原来按控制台代码页
  cp936 解码会抛 `UnicodeDecodeError`），自身输出也改成 UTF-8，中文模组名不再让报告崩掉。

## 2.0 — 收敛部队规模

- `TeamDelays`：`45,60,90` → **`300,450,600`**（20/30/40 秒）。
  组队间隔不再是 3 秒一次，AI 不会不停地凑新队伍。
- `TotalAITeamCap`：`45` → **`10`**（每户同时存在的队伍上限）。
  这是压总兵力的主开关：45 队 × 加倍编制能到上千单位，10 队 × 原版编制约 60–130。
- 进攻队 TaskForce 编制**不再 ×2**，回到原版人数（苏联装甲 7、天启 4、盟军超硬 13）。
- 目标：兵力让位给建筑，基地里不再被坦克塞满；`TeamDelays` 只是组队频率，
  不是寻路定时器，CPU 压力主要来自队伍/单位数量。

## 地图修订（2026-11-22）

- **修正 Flat 30 / Flat 120 的出生点**：`LocalSize` 左下角那块在可玩区菱形之外，
  旧的 `(6,251)` / `(6,501)` 会让 MCV 被就近改放到别处（于是展不开、也不在铁幕里）。
  改为 `(19,256)` / `(19,506)`：在菱形内，且 4×4 建造厂地基完全放得下。
  校验：两张图 29 / 119 个 AI 出生点全部在菱形内，只有旧玩家位判在外面。

- Flat 200 补齐与 30 / 120 完全相同的触发器组合：开局 1 秒揭示全图、
  第 1 秒 + 每 10 秒在 0 号位施放铁幕、每 20 秒 All to Hunt。
  除触发器外，地形与出生点逐字节未变。
- 新增 `tools/build_maps.py retrigger`：只重写 `[Triggers]/[Events]/[Actions]/[Tags]`
  四段，地形与航点原样保留，用来给已有地图补同一套观战触发器。
- 这两张图的铁幕增加**开局第 1 秒**的一次施放（原来第一次在 10 秒），
  之后仍是每 10 秒补一次，基地从进图起就被覆盖。
- 铁幕按格子生效、与归属无关：施放点就是 0 号航点（玩家出生格），
  3×3 盖住基地车；就地展开的建造厂是 4×4，其中落在 3×3 里的格子会把整栋带进铁幕。
  验证方式：`RUST_LOG=debug` 跑一局，日志里第 1 秒出现 `IRONBLST.SHP` 的帧解码
  （铁幕施放动画），说明 `TAction109` 确实执行。
- 已知限制：引擎没有“部署单位”的触发器动作，地图里给本地玩家预置的建筑也会被跳过，
  因此无法做真正的“自动展开”；位置已调到只需按一次 `D`。
  施放动作的航点参数只接受 `A`–`Z`（0–25 号航点），30 / 120 人图这些航点全是出生位，
  所以铁幕无法铺到出生点 3×3 之外。

## 1.9

- 基地车完全还原原版：`[AMCV]/[SMCV]/[PCV]` 无 `Immune`、`Strength=1000`，
  与零售 `rulesmd.ini` 逐字节一致。
- 3 支 MCV 队伍恢复原版 `043F23CC-G` 部署脚本，其余 160 支队伍继续全员冲锋。
- 移除未使用的 `SPYSATX` 建筑定义与 AI 专用 MCV 克隆（引擎类型表不接受新类型）。

## 1.8（已回退）

- 尝试给 AI 使用可击杀的 MCV 克隆 `AMCV2/SMCV2/PCV2`；
  引擎 `[VehicleTypes]` 注册表仍只读原版 85 项，克隆不生效，已删除。

## 1.7

- 地图新增 `AIHuntAll`：每 20 秒对 1–7 号位执行 All to Hunt，
  清掉中后期囤在基地里的部队。
- 观战者必须坐 Start 1，触发器不会作用于 0 号位。

## 1.6

- **160 支队伍全部不守家、直接冲锋**（`ZAIATK01-G`）。
- `*BaseDefenseCounts=100,100,100`，防御建筑占比约 31%。
- `MaximumAIDefensiveTeams=0`、`MinimumAIDefensiveTeams=0`、`UseMinDefenseRule=no`。

## 1.5

- 新增 `ZAIATK01-G` 脚本，绕过原版脚本开头的 `54`（回基地集结）与
  `53`（到敌方基地外集结）。
- `DissolveUnfilledTeamDelay` 5000 → 900。

## 1.4

- 无矿版 Ice Lake：删除 `[OverlayPack]` / `[OverlayDataPack]`，
  矿石不再阻塞基地选址（100 秒 863 栋，对比有矿 632 栋）。
- 矿场加 `ProduceCashAmount=100` / `ProduceCashDelay=60` 支撑无矿经济。
- `AIBuildCounts` 每类 60。

## 1.3

- 建造厂 `SpySat=yes`：展开基地即全图。
- Ice Lake 地图内置 `RevealAll`（1 秒）与 `IronCurtain`（每 10 秒，航点 A）。
- 修正 `[Actions]` 行格式：首字段是动作条数，末字段是航点字母。

## 1.2

- 基地扩张：`AIBaseSpacing=2`（后来发现会导致选址失败，1.4 起回到 1）。
- 65 支进攻队编制 ×2，进攻触发器权重 250。
- `TotalAITeamCap=45`、`MaximumAIDefensiveTeams` 调整、`AIHateDelays` 缩短。

## 1.1

- 回退到最小改动，只保留资金、组队间隔、建造速度三项，用于验证基线。

## 1.0

- 第一版：放大进攻队编制、精英等级、触发器权重，缩短组队间隔。
