# AI 设计说明

这份文档解释模组**改了什么、为什么这样改**，以及哪些地方撞到了引擎的硬限制。

> 具体怎么调、哪些键是死的、怎么验证一局，见
> [ai-tuning-playbook.md](ai-tuning-playbook.md)。那份文档是操作手册，
> 这份是设计说明。

## 1. 目标

1. 电脑不再「攒一波、回家、再出发」，而是持续施压。
2. 基地向外交替铺开，而不是挤在建造厂旁边。
3. 中后期不囤兵：家里的部队会被定期清出去。
4. 观战者不会被打死，也不需要手动输入作弊码。
5. 科技树要**按顺序建全**：电厂 → 矿场 → 兵营 → 战车工厂 → 雷达 → 高科 → 维修厂 → 防御。
6. 建造厂被打掉后，AI 能靠维修厂产基地车并重新展开。

## 2. 规则层（`rulesmd.ini`）

### 经济

| 键 | 值 | 说明 |
| --- | --- | --- |
| `MultiplayerAICM` | `100000,100000,100000` | 开局按当前资金追加 `coef/100`，即 **×1001**。原版 `400` = 困难 5 倍 |
| `BuildSpeed` | `.025` | 原版 `.7`；数值是每 1000 信用点需要的分钟数，**全局生效** |
| `ProduceCashAmount` / `Delay` | 矿场 `100` / `60` | 每 4 秒 +100，无矿地图的经济来源 |
| `AIBuildCounts` | 见下 | 只给 6 个生产建筑，按难度取数 |
**`AIBuildCounts` 只保留 6 个生产建筑（2.6 起）**，其余类型不写这个键（回落到「一种一个」）。
它是**按难度**的整数列表，用 `HouseDifficulty::table_index()` 取值，**冷酷 = 0、中等 = 1、简单 = 2**
（向量「最难在前」）。值 `n` = 1 个种子节点 + 首节点之后随机位置插 `n-1` 个副本。

| 类型 | `AIBuildCounts` | 冷酷 | 中等 | 简单 |
| --- | --- | --- | --- | --- |
| `GAPILE` / `NAHAND` / `YABRCK` | `3,1,1` | **3 个兵营** | 1 | 1 |
| `GAWEAP` / `NAWEAP` / `YAWEAP` | `5,1,1` | **5 个战车工厂** | 1 | 1 |

为什么只给这 6 个、而且数量这么小：

1. **副本不是「紧跟在首节点后面」**，而是插在「该类型首节点之后到计划末尾」的
   **随机位置**。早期类型（电厂）的副本会撒到整张计划里，后期类型的只撒在尾部 ——
   1.x 把每类设成 60，实测 403 座电厂 vs 12 座战车工厂。只加 6 个节点不会有这个问题，
   而且战车工厂第一次出现的时间仍由种子节点决定。
2. **它不是「基地规模」旋钮**：计划整局只生成一次。节奏交给原版三难度，
   扩张交给「打掉就重建」与 3 基地扩建
   （`AIRestrictReplaceTime=0`，见 [playbook §9](ai-tuning-playbook.md#9-打掉就重建原生节点重规划不需要触发器)）。
   想加大基地规模就调 `*BaseDefenseCounts`。
3. 三类错误都是**静默失效**（段名拼错、列表少于 3 项、难度顺序写反），
   所以 `assert_build_counts` 在构建期强制检查，详见
   [playbook §12](ai-tuning-playbook.md#12-按难度给数量冷酷-3-兵营-5-战车工厂26-起)。

详见 [playbook §7.12](ai-tuning-playbook.md#712-ai-不扩张其实是计划节点用完了)。
引擎的 `BASE_PLAN_INSERT_LIMIT` 是 256。

### 基地与防御

| 键 | 值 | 说明 |
| --- | --- | --- |
| `Allied/Soviet/ThirdBaseDefenseCounts` | **原版 `25/20/6`** | 2.4 起回原版：三个难度各自决定防御规模。想扩容**只调这里**（防御节点沿周长向外找位置，不破坏建造顺序） |
| **`AIPickWallDefensePercent`** | **`0,0,0`** | 原版 `50,25,10`。**完全关闭围墙**：每格墙都是一个计划节点，跟真防御抢预算，`ProtectWithWall=` 的环还会堵自己的路。这是引擎里**唯一**的造墙入口，0 = 永不掷出围墙，防御抽签 100% 落到真枪 |
| `AIExtraRefineries` | `0,0,0` | 原版 `2,1,0`。额外矿场会占掉规划位 |
| `AISlaveMinerNumber` | `2,2,2` | 原版 `4,3,2`。**对 Yuri 它就是矿场复制数**（Yuri 没有矿车），同时决定丢失的矿场能否立刻原地重建 |
| `AIBaseSpacing` | `1` | **不要调大**。设 2 会让选址失败，基地卡在约 70 栋 |
| **`AIRestrictReplaceTime`** | **`0`** | **「被打掉就重建」的总开关**。0 = 不限制，任何建筑丢失后立刻可重规划；原版 `400`（约 27 秒）只允许先补墙/防御/电厂 |
| `[GACNST]/[NACNST]/[YACNST]` | `SpySat=yes` | 展开基地即全图，不耗电 |

> 计划里的防御数 ≠ 实际建成的防御数：`choose_building` 拿到防御节点后，
> 若找不到前置已满足的防御类型，会**直接删掉这个节点**（不是延后）。
> 验收只看日志里的实际落地数。
> 2.6 起围墙已完全关闭，所以这 25/20/6 个节点**全部**会变成真正的防御建筑。

### 维修厂与基地车

| 建筑 | 原版 | 模组 | 说明 |
| --- | --- | --- | --- |
| `GADEPT` / `NADEPT` / `YADEPT` | `AIBuildThis=no` | **`yes`** | 这一项决定 AI 能不能造基地车 |

原版三个维修厂都标了 `AIBuildThis=no`（注释还写着 "taken out to remove useless
building"），而基地车的前置正好是维修厂：

```ini
AMCV Prerequisite=GAWEAP,GADEPT
SMCV Prerequisite=NAWEAP,NADEPT
PCV  Prerequisite=YAWEAP,YAGRND    ; YADEPT 在原版被注释掉
```

于是原版 AI **在数学上不可能**造出基地车，数据里那 3 条「本户拥有 0 座建造厂」
触发器和 3 支 `Max=1` 的 MCV 队伍（脚本 `043F23CC-G` = 找空地 + 展开）全部空转。
打开维修厂之后这条链才真正可用；2.5 又补了 3 条「建造厂 < 3」的扩建触发器
（见 §3.3），让每户稳定铺到 3 个基地。

> 仍然存在的限制：AI 必须**同时**有战车工厂和维修厂；而且基地车要找到 4×4 空地
> 才能展开，太挤时会被反复拒绝（日志 `MCV deploy blocked at origin`）。

### 进攻节奏

| 键 | 原版 | 模组 | 说明 |
| --- | --- | --- | --- |
| `TeamDelays` | 2000/2500/3500 | `300,450,600` | 逻辑帧（15 帧/秒）：简单 20 秒、中等 30 秒、困难 40 秒才尝试组一支新队 |
| `TotalAITeamCap` | 30 | `10` | 每户同时存在的队伍上限，直接决定总兵力规模 |
| `MaximumAIDefensiveTeams` | 2 | `0` | 没有守家队类型，见下 |
| `MinimumAIDefensiveTeams` | 1 | `0` | 同上 |
| `UseMinDefenseRule` | yes | `no` | **必须为 no**，见下 |

> **这三条是一个整体，配错会让 AI 一兵不发。** 模组把所有非 MCV 队伍都改写成
> `IsBaseDefense=no`，所以任何一户都不可能拥有守家队；此时若
> `UseMinDefenseRule=yes` 且 `MinimumAIDefensiveTeams>0`，`defense_gate` 会要求
> 「先有守家队才允许组队」——条件永不成立，163 条触发器全被拒，AI 不组队、
> 不造兵、不进攻，而基地照常建造，日志里毫无异常。2.2 就是这样翻车的。
> `tools/build_mod.py` 现在对此有构建期断言。
> 详见 [ai-tuning-playbook.md §7.11](ai-tuning-playbook.md#711-没有守家队类型却打开了-usemindefenserule22-的事故)。
| `AIHateDelays` | 30/50/70 | **原版（2.4 起不调）** | 2.4 撤掉了这条调参 |
| `AITriggerSuccessWeightDelta` | 20 | **原版（2.4 起不调）** | 同上 |
| `AITriggerFailureWeightDelta` | -50 | **原版（2.4 起不调）** | 同上 |
| `DissolveUnfilledTeamDelay` | 5000 | `900` | 凑不齐的队伍 60 秒后解散，腾出编制 |
| `[AI] Paranoid` | yes | `no` | 电脑不抱团针对玩家 |
| `AINearestEnemy`（VERA 扩展） | 否 | `yes` | 电脑选最近的敌人，FFA 会互殴 |

> **`TeamDelays` 与 CPU / 寻路的关系**：它不是寻路定时器，而是「这户人家多久
> 尝试组建一支新队伍」的间隔。它本身不会让已有单位重算路径；真正烧 CPU 的是
> 队伍数量——每支新队伍都要凑单位、出队、下移动命令，单位一多，寻路、
> 目标扫描和团队脚本的执行次数就跟着涨。所以把间隔从 3 秒放宽到 20–40 秒、
> 再把每户队伍上限压到 10，等于同时削掉了「组队频率」和「常备兵力」这两个源头。
> 想更省可以继续加大 `TeamDelays`；想更热闹就动 `TotalAITeamCap`，别去动间隔。

## 3. 队伍层（`aimd.ini`）

### 3.1 编制保持原版

2.0 起不再放大编制：65 支进攻队的 TaskForce 沿用原版人数
（苏联装甲 7、天启 4、盟军超硬 13），配合 `TotalAITeamCap=10`，
每户常备兵力约 60–130 个单位，比 1.9 的「45 队 ×2 编制」低一个数量级。

兵力少下来，基地里的空地才留给建筑：电脑不会再把出生点铺满坦克。
与防御队/特种队共用的 TaskForce 会跳过，避免把工程师队也放大。

### 3.2 不集结脚本

原版进攻脚本普遍是：

```ini
0=54,0     ; 在基地重新集结
1=63,0
2=53,0     ; 到敌方基地外 AISafeDistance 格集结
3=0,6      ; 才开始攻击
```

大编制 + 45 支队伍上限时，`54` 会让部队全部回基地等齐人，结果就是「家里堵车」。

模组新增脚本：

```ini
[ZAIATK01-G]
Name=SuperAI Charge
0=0,6      ; 用 quarry 6 选目标并进攻
1=49,0     ; 立即推进到下一步
2=0,2
3=0,1
4=0,5
```

- `0` 是 `team_action_attack_quarry`，参数是 threat quarry 选择器，不需要预先集结。
- `49` 是「直接推进」动作，用来把攻击步骤串起来。
- **160 支队伍**改成这个脚本，`Aggressive=yes`、`IsBaseDefense=no`。
- 只有 **3 支 MCV 队伍**保留原版 `043F23CC-G` 部署脚本，否则 AI 永远不会展开分基地。

### 3.3 触发器权重

**2.4 起不再调整进攻触发器**：67 条进攻触发器的权重与难度位全部回到原版
（`70` / 下限原版值 / 原版难度位），出手频率交由三个难度自己决定。
2.0–2.3 曾把它们抬到 250 并三难度全开，2.4 认为这属于「调参」，撤掉。

唯一仍然动权重的是 MCV 触发器，一共 **6 条**（2.5 起）：

| 触发器 | 条件 | 权重 | 作用 |
| --- | --- | --- | --- |
| 3 条零售 `… MCV - H` | 建造厂 **== 0** | `5000` | 救急：厂全没了 → 只造基地车 |
| 3 条新增 `… MCV - Expand` | 建造厂 **< 3** | `5000` | 扩建：不满 3 座就补基地车去展开 |

3 支 MCV 队伍的 `Max` 从零售 `1` 改成 **`2`**，所以可以同时有两台基地车在编。
每户因此会稳定铺到 **3 个基地**，任意一座被拆都会重新补齐 —— 扩建就这样长期转着。

`5000` 就是引擎的 `PRIORITY_WEIGHT`：一旦命中，**清空该次抽签里的其它所有触发器**。
用在这里正是「立刻只造基地车」的意思，是这套机制能成立的关键。
代价是：不满 3 座基地期间该户暂停组建新的进攻队（已在场的部队不受影响）。

> **但它是双刃的**，2.2 就被它割过：维修厂当时不可建，MCV 队伍永远凑不齐，
> 结果这支 AI 长时间一支队伍都组不出来 —— 表现是「中后期完全不进攻」。
> 现在维修厂可建（`AIBuildThis=yes`），这条权重才安全。
> `tools/build_mod.py` 的 `assert_mcv_recovery_fillable` 强制两者必须同时成立：
> 用了 5000 就必须三个维修厂都可建，否则构建直接失败。
> 掩码写法与收敛过程见 [playbook §9.2](ai-tuning-playbook.md#92-基地车救急-扩建共-6-条触发器)。

### 3.4 超级武器自动发射

零售的 12 个超武段**一条 `SW.*`（Ares 超武扩展）都没有**，AI 于是停在默认瞄准状态：
ForceShield 这类自施放超武照常工作，核弹/闪电风暴/心灵控制器这类**带目标**的从不发射。
2.7 起给 AI 能造出来的 6 个带目标超武显式写上：

```ini
SW.AllowPlayer=yes
SW.AllowAI=yes
SW.AutoFire=yes        ; 关键：AI 没有「玩家点击」这条路径，只能走自动发射
SW.UseAITargeting=yes
SW.RequiresTarget=yes
SW.AITargeting=offensive_cell_clear   ; 打敌人的用这个
SW.AffectsHouse=yes                   ; 只加给「作用于自家单位」的铁幕/超时空
```

| 超武 | 建筑 | `SW.AITargeting` | 说明 |
| --- | --- | --- | --- |
| `NukeSpecial` | `NAMISL` | `offensive_cell_clear` | 实测可用 |
| `LightningStormSpecial` | `GAWEAT` | `offensive_cell_clear` | 实测可用 |
| `PsychicDominatorSpecial` | `YAPPET` | `offensive_cell_clear` | 同族 |
| `GeneticConverterSpecial` | `YAGNTC` | `offensive_cell_clear` | 同族 |
| `ChronoSphereSpecial` | `GACSPH` | **`offensive_cell_set`** | 传送自家部队到敌方**有东西**的格子 |
| `IronCurtainSpecial` | `NAIRON` | **`defensive_cell_set`** | 罩住自家**有部队**的格子 |

> **`cell_clear` 是「空格子」，`cell_set` 是「格子里有东西」**；`offensive` 指敌方地盘，
> `defensive` 指自家地盘。铁幕要罩自己人 → `defensive_cell_set`；
> 2.7 误写成 `defensive_cell_clear`（在自家找**空地**罩），于是它一发都不放 ——
> 这正是「核弹闪电正常、铁幕超时空不动」的原因。详见
> [playbook §13.1.1](ai-tuning-playbook.md#1311-最容易搞错的一点cell_clear-还是-cell_set)。

`ForceShield`/`ParaDrop`/`SpyPlane`/`PsychicReveal`/`ChronoWarp` 不动 ——
前四个本来正常，最后一个的 `GADUMY` 是 `AIBuildThis=no`，AI 造不出来。
`assert_superweapon_autofire` 会校验键是否齐全、`SW.AITargeting` 的每个词是否都在引擎认识的
词表里（拼错会被**静默丢弃**；支持逗号分隔多个词），并禁止把 `SW.*` 写进那 5 个不该动的段。

> 证据等级：核弹/闪电**已由实测确认**（用户观察到它们正常开火）；铁幕/超时空是 2.8 按
> `cell_clear`/`cell_set` 的语义修正的，**仍待实测**。若仍不放，按
> [playbook §13.1](ai-tuning-playbook.md#131-结论核弹闪电已实测确认铁幕超时空待确认) 的回退阶梯
> 一次改一个值。

## 4. 地图层：All to Hunt

即使脚本不集结，中后期仍会有单位因为失去目标、卡路径、刚生产出来而留在基地。
原版有一个正好解决这个问题的动作：**All to Hunt（动作 6）**。

```ini
[Triggers]
02000000=<none>,<none>,AIHuntAll,0,1,1,1,0
[Events]
02000000=1,13,0,20
[Actions]
02000000=7,6,0,4476,0,0,0,0,A,6,0,4477,...
[Tags]
02000001=2,AIHuntAll,02000000
```

- `All_To_Hunt` 遍历该房屋的每个单位：`leave_team`，然后排入 `Hunt` 任务。
- `Hunt` 的索敌扫描没有距离上限（只受移动区域限制），所以角落里的单位也会自己找目标。
- 每 20 秒执行一次，`repeat=2` 让计时器循环。
- 动作参数 `0x117B + slot` 是 Ares 的 `Player @ X` 选择器：`4476..4482` = 1–7 号位。
  **0 号位（玩家）永远不会被清**。
- 30/120 人图按 10 个动作一条触发器拆分，避开 `[Actions]` 单值 512 字节上限。

> 不要用 `StupidHunt=yes`：它会跳过索敌，单位反而原地待命。

## 5. 观战者的保护

- `RevealAll`：动作 16，开局 1 秒揭开全图。
- `IronCurtain`：动作 109，每 10 秒在 0 号位施放。铁幕持续 750 帧（50 秒），
  所以永久覆盖；范围是 0 号位周围 3×3，**不要把 MCV 开走**。
- 建造厂自带 `SpySat=yes`，换别的地图也能展开即全图。

> 地图上给玩家预置间谍卫星是无效的：引擎会跳过 `owner == 本地玩家` 的地图建筑
> （日志：`Skipping map Techno SPYSATX owned by Americans`）。触发器方案不受影响。

## 6. 调参

想更温和：

```ini
TeamDelays=90,120,180            ; 组队慢一倍
BuildSpeed=.07                   ; 10 倍而不是 28 倍
MultiplayerAICM=10000,10000,10000 ; 开局 ×101
AlliedBaseDefenseCounts=10,10,10
```

想更疯（基地更饱满就只加防御节点，别动 AIBuildCounts）：

```ini
TeamDelays=20,30,45
BuildSpeed=.015
MultiplayerAICM=200000,200000,200000
AlliedBaseDefenseCounts=60,60,60
```

改完必须重启游戏。`tools/build_mod.py` 里的常量是这些值的唯一来源，
直接改发布版 `rulesmd.ini` 也可以，但下次重建会被覆盖。

**调之前先读 [ai-tuning-playbook.md](ai-tuning-playbook.md)**：那里列了死键清单、
`AIBuildCounts` 的真实语义、以及改动后必须走的标准验证流程。

## 7. 撞到的引擎限制

这些都已经实测确认，不是猜测：

| 限制 | 现象 | 结论 |
| --- | --- | --- |
| 基地计划整局只生成一次 | 计划里没有的东西这一局永远不会出现 | 只能在生成时把计划表做对 |
| 基地规模没有硬上限 | 单户实测 370 栋 | 规模由计划节点数决定；想更大**只调 `*BaseDefenseCounts`** |
| 计划节点用尽后基地静止 | 有平地也不再往外铺 | 节点数就是建造预算；2.4 靠「打掉就重建」补充，见 [playbook §7.12](ai-tuning-playbook.md#712-ai-不扩张其实是计划节点用完了) |
| 周长没有可用格时停止 | `ordinary_site` 返回 (0,0)，放置失败 | 这是「没空地就不长」的正常行为 |
| `AIBaseSpacing=2` | 约 70 栋后大量选址失败 | 必须保持 1 |
| 基地车展开需要空地 | 日志 `MCV deploy blocked at origin` | 基地越挤越难展开；这是独立于「造不造」的问题 |
| 类型注册表固定 | 新增 `[VehicleTypes]` 不生效（日志仍 85 项） | 不新增单位，只改既有数据 |
| 本地玩家地图建筑被跳过 | 预置的卫星/基地被删除 | 用触发器，不用地图建筑 |
| `[AI]` 比例/上限键是死键 | 改了 `WarRatio`/`DefenseLimit` 等毫无反应 | 见 [playbook §1.5](ai-tuning-playbook.md#15-死键清单) |
| `AIBuildCounts` 是随机撒点 | 高计数让后期建筑被挤到队尾 | 2.6 起只给 6 个生产建筑（兵营/战车工厂），其余不写 |
| **触发器不能下建造令** | `[AITriggerTypes]` 只能组队 | 想让 AI 造建筑只有「计划节点」一条路，配置层面无解 |

> 已经**不再是**限制的一条：曾经写在本文里的「AI 不会造 MCV，只能改引擎源码」。
> 实际原因是原版把三个维修厂的 `AIBuildThis` 设成了 `no`，掐断了基地车的前置。
> 详见 [ai-tuning-playbook.md §3](ai-tuning-playbook.md#3-为什么基地车没了也迟迟不建原版死锁不是引擎限制)。

## 8. 参考

- 操作手册（怎么调、怎么验证、踩过哪些坑）：[ai-tuning-playbook.md](ai-tuning-playbook.md)
- VERA20k 源码：`src/sim/ai_team_creation.rs`、`ai_base_building.rs`、
  `base_plan_generation.rs`、`ai_build_need.rs`、`ai_unit_choice.rs`、
  `team_script_vm/actions.rs`、`house_strategy.rs`、
  `scenario_bootstrap/launch_houses.rs`、`world/world_spawn.rs`。
- 日志判读工具：`tools/analyze_log.py`（按房主统计实际落地，判 A1–A5 闸门）。
- 地图格式与触发器细节见 [map-format.md](map-format.md)。
