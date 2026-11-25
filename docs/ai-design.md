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
5. 计划表里要**包含整棵 AI 可建科技树**（电厂、矿场、兵营、战车工厂、雷达、维修厂、高科、防御）。
   落地顺序由引擎按 `Prerequisite` 拓扑一次性排好（大致：电厂 → 兵营 → 矿场 → 战车工厂 → 雷达 →
   维修厂 / 高科同层，先后看 `[BuildingTypes]` 顺序）。**这不是「前一栋建完才允许建下一栋」的
   门槛**：`choose_building` 只取第一个未满足的节点，建筑生产不检查前置（单位与队伍才检查）。
   维修厂不能缺失，也不该被人为压后（MCV 的前置链）；防御是 `-1` 占位节点，随机插在计划里，
   选到时就地选型、选不出就删，**不设「最后」**。详见 §7。
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
| `Allied/Soviet/ThirdBaseDefenseCounts` | **原版 `25/20/6`（苏、尤里 `25/22/6`）** | 2.4 起回原版：三个难度各自决定防御规模。想扩容**只调这里**（防御节点沿周长向外找位置，不破坏建造顺序） |
| 空军队伍 `Max` / 每队飞机数 / 空军触发器权重 | `6`（机场队 `3`、基洛夫队 `3`）/ 机场 `4`、基洛夫 `3/4`、火箭兵 `6` / **×3** | 零售 11 支空军队伍全部 `Max=1`、每队 1–4 架、权重 40–70，所以一个 AI 同时最多只有一支空军；见 [playbook §15](ai-tuning-playbook.md#15-空军与防空部队为什么看不到以及怎么加32) |
| 防空触发器权重 | **×2** | 只有 46/165 条触发器带防空单位；×2 后带防空队伍在抽签中的权重占比约 28% → 44% |
| `[NASAM]` / `[NAFLAK]` 的防空值 | 零售 `0/0/25`（3.11.6 已回退） | 防御选型**先选类别再选建筑**：零售把盟/苏防空炮的地面值设为 0，使它们**只在 air 类别**里是候选；air 类别要求敌方空中占比超过我方防空覆盖，而 AI 之间几乎没有空军，所以它们几乎不会被选。3.10.x 曾给它们加地面值（25/10）让三类都候选，3.11.6 已回退——那是 hack，会让 AI 为打不到的地面威胁买防空；`assert_aa_defenses_competitive` 现在钉住零售 `0/0/25` |
| **`AIPickWallDefensePercent`** | **`0,0,0`** | 原版 `50,25,10`。**完全关闭围墙**：每格墙都是一个计划节点，跟真防御抢预算，`ProtectWithWall=` 的环还会堵自己的路。这是引擎里**唯一**的造墙入口，0 = 永不掷出围墙，防御抽签 100% 落到真枪 |
| `AIExtraRefineries` | `0,0,0` | 原版 `2,1,0`。额外矿场会占掉规划位 |
| `AISlaveMinerNumber` | `2,2,2` | 原版 `4,3,2`。**对 Yuri 它就是矿场复制数**（Yuri 没有矿车），同时决定丢失的矿场能否立刻原地重建 |
| `AIBaseSpacing` | `1` | **不要调大**。设 2 会让选址失败，基地卡在约 70 栋 |
| **`AIRestrictReplaceTime`** | **`0`** | **「被打掉就重建」的总开关**。0 = 不限制，任何建筑丢失后立刻可重规划；原版 `400`（约 27 秒）只允许先补墙/防御/电厂 |
| `[GACNST]/[NACNST]/[YACNST]` | `SpySat=yes` | 展开基地即全图，不耗电 |

> 计划里的防御数 ≠ 实际建成的防御数：`choose_building` 拿到防御节点后，
> 若找不到前置已满足的防御类型，会**直接删掉这个节点**（不是延后）。
> 验收只看日志里的实际落地数。
> 2.6 起围墙已完全关闭，所以这 25/20/6（苏/尤里 25/22/6）个节点**全部**会变成真正的防御建筑。

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
| `TeamDelays` | 2000/2500/3500 | `300,450,600` | 逻辑帧（15 帧/秒）：困难 20 秒、中等 30 秒、简单 40 秒才尝试组一支新队（引擎以冷酷为 0 号档） |
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
| `DissolveUnfilledTeamDelay` | 5000 | `2400` | 凑不齐的队伍 160 秒（15 帧/秒）后解散，腾出编制 |
| `[AI] Paranoid` | yes | `no` | 电脑不抱团针对玩家 |
| `AINearestEnemy`（VERA 扩展） | 否 | `yes` | 电脑选最近的敌人，FFA 会互殴 |
| `TargetDistanceCoefficientDefault` | `-10` | `-0.4` | AI 威胁评分里的距离惩罚。原版约 **39 格外**评分被 `max(1)` 钳成 1 分，而 `keep` 只在「严格大于」时替换，于是「最近」退化为「遍历顺序第一个 = 最老的敌方工厂」；`-0.4` 把钳制点推到约 **977 格**（大于交付地图最大战场 500×500 的 707 格对角），每远 10 格少 1024 分，距离项上最近者严格胜出（最终评分仍叠加 A–D 四项）。机制与局限见 §3.2 |

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

模组新增脚本（先走到敌方基地外，再按原顺序进攻）：

```ini
[ZAIATK01-G]
Name=SuperAI Charge
0=53,0      ; 到敌方基地外 AISafeDistance=12 格（Move，途中可被动索敌）
1=0,6      ; 用 quarry 6 选目标并进攻
2=49,0     ; 立即推进到下一步
3=0,2
4=0,1
5=0,5
```

- `53` 是 `team_action_gather_at_enemy_base`：把队伍移动到「敌方基地中心朝向我方
  12 格（`AISafeDistance`）」的可通行格；这一段是 `Mission::Move`。电脑队伍只要
  `Aggressive=yes` 且 `Suicide=no`，就会在 Move 上运行被动索敌（引擎
  `target_scan.rs`），所以行军途中会向进入射程的敌人开火并继续前进。
  原版 `20` 是从**敌方**基地中心量的，双方基地靠近时这个点会落进自家基地，
  队伍等于在家门口集结 → 新基地堵车；`8` 又太贴，三座厂的敌方基地半径常大于
  8 格，会落进敌墙；`12` 是墙外的折中。扩张 MCV 的 `54`（回自家基地）单独用
  `[General] AIFriendlyDistance=20`，不再被 `53` 的键带走。
- `0` 是 `team_action_attack_quarry`，参数是 threat quarry 选择器；它用**队长当前
  位置**重新选点（`direct_greatest_threat` 的距离基准 D0 = 队长坐标），不需要预先集结。
- `49` 是「直接推进」动作，用来把攻击步骤串起来。

**为什么只加 `53` 还不够**：`greatest_threat` 在给定坐标的分支里把距离算成
**lepton**、射程算成 **格**（零售遗留混算）；`TargetDistanceCoefficientDefault=-10`
时约 **39 格外**的候选评分归零，`finish_score` 再把它钳成 1，而 `keep` 只在严格大于
时替换 → 所有远点同分，胜者退化为 stable_id 最小的**最老**敌方工厂。改成 `-0.4`
（§2 表）后钳制点约 **977 格**，超过最大对角 707 格，每个候选都是正分，每远 10 格
少 1024 分，距离项上最近者严格胜出；最终评分仍会叠加 A–D 四项，所以不是「绝对最近
优先」，但不会再退化成「最老工厂」。

**局限（数据层近似的边界）**：`53` 的目的地是敌方**基地中心**外 12 格，不是最近的
工厂；途中索敌半径仍由 `GuardRange=` / 武器射程决定（犀牛没有 `GuardRange`，只有约
5.75 格），所以是「打到枪口上的敌人」而不是全图追敌；没有交战后回到原路径的
attack-move 语义（那需要引擎改动，本次不做）；被动索敌会多抽 `RandomRanged(0,2)`，
旧存档/回放不再保证一致。

**实机验收（无头探针只能证明加载成功）**：8 人图与 120 人图各开 1 局观战，确认
① 出征队伍朝**最近的**敌方工厂方向走，而不是固定去地图另一侧；
② 行军途中进入武器射程的敌人会被开火（不是全图追敌）；
③ 到达后照常打工厂，并继续 quarry 2/1/5；
④ `ra2.log` 没有队伍脚本/动作报错。旧存档/回放不作为验收基线。

- **151 支队伍**改成这个脚本，`Aggressive=yes`、`IsBaseDefense=no`。
- **3 支 MCV 队伍**保留原版 `043F23CC-G` 部署脚本，否则 AI 永远不会展开分基地。
  该脚本的 `0=54,0` 回**自家**基地中心展开；Ares 下用 `[General] AIFriendlyDistance=20`
  单独控制，避免被 `53` 的 `AISafeDistance=12` 一起拖近。
- **9 支带超武动作的队伍保留零售脚本**（3.0 起）：这些脚本里有
  `53`（集结到敌方基地）、`55`（放铁幕）、`57`（超时空传送），
  是 AI 使用铁幕/超时空的**唯一**代码路径。2.4 曾把它们一并覆盖掉，
  结果是 AI 造了铁幕/超时空却永远不放，且日志里毫无痕迹。
  详见 [playbook §13.1.4](ai-tuning-playbook.md#1314-根因24-把放超武的队伍脚本一起覆盖掉了)。

> 这三类例外现在都有构建期断言守着：MCV 队伍必须 `Max=1` 且仍用部署脚本
> （`assert_mcv_team_max`），超武队伍必须仍用含 55/56/57 的脚本
> （`assert_superweapon_teams_intact`）；另 `assert_attack_script` 钉住
> `[General] TargetDistanceCoefficientDefault=-0.4`、`AISafeDistance=12`、
> `AIFriendlyDistance=20` 与 `ZAIATK01-G` 的六步（含 `0=53,0`）。

### 3.3 触发器权重

**2.4 起不再调整进攻触发器**：67 条进攻触发器的权重与难度位全部回到原版
（`70` / 下限原版值 / 原版难度位），出手频率交由三个难度自己决定。
2.0–2.3 曾把它们抬到 250 并三难度全开，2.4 认为这属于「调参」，撤掉。

唯一仍然动权重的是 MCV 触发器，一共 **6 条**（2.5 起）：

| 触发器 | 条件 | 权重 | 作用 |
| --- | --- | --- | --- |
| 3 条零售 `… MCV - H` | 建造厂 **== 0** | `5000` | 救急：厂全没了 → 只造基地车 |
| 3 条新增 `… MCV - Expand` | 建造厂 **< 3** | `5000` | 扩建：不满 3 座就补基地车去展开 |

3 支 MCV 队伍的 `Max` **保持零售的 `1`**：同一户同时只跑 1 台扩张基地车。
（2.5–3.13.10 曾改成 `2`；两台车同时上路会奔向同一块空地、互相挡住部署
（日志 `MCV deploy blocked`），这是新基地堵车的一部分，现已改回 `1`。）
每户仍会稳定铺到 **3 个基地**：`< 3` 触发器在当前车展开后再抽下一台，
任意一座被拆都会重新补齐 —— 扩建就这样长期转着，只是串行而不是并行。

`5000` 就是引擎的 `PRIORITY_WEIGHT`：一旦命中，**清空该次抽签里的其它所有触发器**。
用在这里正是「立刻只造基地车」的意思，是这套机制能成立的关键。
代价是：不满 3 座基地期间该户暂停组建新的进攻队（已在场的部队不受影响）。

> **但它是双刃的**，2.2 就被它割过：维修厂当时不可建，MCV 队伍永远凑不齐，
> 结果这支 AI 长时间一支队伍都组不出来 —— 表现是「中后期完全不进攻」。
> 现在维修厂可建（`AIBuildThis=yes`），这条权重才安全。
> `tools/build_mod.py` 的 `assert_mcv_recovery_fillable` 强制两者必须同时成立：
> 用了 5000 就必须三个维修厂都可建，否则构建直接失败。
> 掩码写法与收敛过程见 [playbook §9.2](ai-tuning-playbook.md#92-基地车救急-扩建共-6-条触发器)。

**3.3.1 保底进攻：修死条 + 抬下限 + 3 条 always（3.14 起）**

2.4 的「出手频率交给三个难度」不变，但它依赖的触发器数据里有三处**与难度无关**的
结构性缺陷，3.14 只修这三处：

| 改动 | 数量 | 说明 |
| --- | --- | --- |
| 修 `d000` 死条 | 7 | 三个难度位全关 = **永不可命中**。按名字声明的难度恢复：`Allied Bombard - E1` / `Soviet Bombard Easy` → `100`；`Allied Spy vs Allied Tech` / `Allied IFV Rush ×2` / `Soviet Siege Bunker ×2` → `011` |
| 抬权重下限 | 46 | 全部是 condition 4（对象 `>= 0`，即敌方可用资金，实际恒真）。零售下限在 10–60：每支队伍死亡（未走到动作 49）扣 `AITriggerFailureWeightDelta=-50`，面对强玩家会一路掉到下限 → 体感「越打越软」。现在 `下限 = 起始值`，上限与 +20 成功反馈保留（仍可向上学习，但不会跌破出手基线） |
| 新增 always 触发器 | 3 | 盟/苏/尤各 1 条：`condition=-1`、`object=<none>`、`64 hex` 掩码、`d111`、权重 `30`（三槽恒定）、复用 `Max≥2` 的现有队伍。是「无论如何都会出点兵」的地板 |

权重 `30` 刻意低于 5000 接管触发器（MCV/超武/反渗透）与 1000 防空触发器，所以
**反制优先、进攻只补底**。3 条新条插在 `[AITriggerTypes]` 末尾、`[Digest]` 之前
（`ZAIALW01-G`/`02-G`/`03-G`），回滚只需删 3 行再重建。

**与 2.4 的取向差异**：2.0–2.3 做的是「67 条进攻触发器权重 250 + 三难度全开」，
2.4 整批撤回；本次**没有**恢复那套 —— 没有 250 权重、没有把 45 条 cond 4 的难度位
全开、没有把 42 条反制/任务条件解耦成 `-1`、反渗透与 MCV/超武的 5000 一律未动。
7 条死条只补回名字声明的难度（Easy +2、Normal/Hard 各 +5），可命中数
Easy/Normal/Hard 由 `30/103/122` 变为 **`35/111/130`**，节奏仍主要由三个难度决定。

守卫：`assert_attack_triggers_boosted` 钉住 171 条 / 每条 18 token / 掩码 64 hex /
无 `d000` / 46 条下限=起始 / 3 条新条的形状与队伍 `Max≥2` / condition 直方图与
关键反制条目（反核、反天气、防空、反渗透 5000）。

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
02000000=1,13,0,60
[Actions]
02000000=7,6,0,4476,0,0,0,0,A,6,0,4477,...
[Tags]
02000001=2,AIHuntAll,02000000
```

- `All_To_Hunt` 遍历该房屋的每个单位：`leave_team`，然后排入 `Hunt` 任务。
- `Hunt` 的索敌扫描没有距离上限（只受移动区域限制），所以角落里的单位也会自己找目标。
- 每 60 秒执行一次，`repeat=2` 让计时器循环。
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
| **建造顺序不是闸门** | 计划整局只生成一次，并已按 `Prerequisite` 拓扑排好；`choose_building` 只取「第一个未满足的节点」，AI **造建筑不检查前置**（`factory_lifecycle.rs`：建筑生产不问前置；`production::can_build` 只用于单位和队伍） | 别把「顺序建全」做成硬门槛：数据层没有「等待」入口，压后/删类型只会永久生效；维修厂（MCV 前置）被压后会让基地车链更晚可用；防御 `-1` 随机散布、筛不出就删，做不到「最后再建」 |

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
