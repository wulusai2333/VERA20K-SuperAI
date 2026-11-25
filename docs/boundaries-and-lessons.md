# 边界手册：今天踩过的坑与确认过的正确路径

> 用途：下次做地图/单位改动前，先读这一页。
> 版本基线：mod 3.11.x（VERA20k 0.4.0）。

---

## 零、总原则：默认「只增不改」（additive-only）

> **除非你明确点名要改某个原版单位/原版行为，否则一律新建条目，原版段一行都不动。**

### 0.0 「原版」到底指什么（定义，先看这条）

> **原版 = 官方《红色警诘2：尤里的复仇》的零售数据**
> （`F:\Games\red2\rulesmd.ini` / `artmd.ini` / `aimd.ini`，以及官方地图）。
>
> **不是**我们 mod 的上一个版本，**也不是**我们自己新增的 `ZAI*` 条目。

由此有三条推论：

1. **我们自己的东西可以随便改**：`ZAI*` 段、追加到列表的行、给零售段追加的键，
   都属于 mod 自有内容 —— 改名、改数值、删掉重做都行，不受"只增不改"约束；
2. **受保护的是零售数据本身**：零售段里**已有键的值**被改、被删，才算"改了原版"，
   必须登记 + 断言 + 写影响面；
3. **自检要比的是"零售 vs 构建产物"，不是 `git diff`**（后者比较的是我们自己的上一版，
   对这条规则没有意义）。

这条优先级最高，前面所有"边界"判断都在它之下。展开成可执行的规则：

### 0.1 什么必须新建

| 对象 | 做法 |
| --- | --- |
| 单位 / 载具 / 步兵 / 建筑 | 复制原版段为新 ID（`ZAI...`），改副本；原版段不动 |
| 武器 / 弹丸 / 弹头 | 一律新建（`ZAI...`），不要改 `[Cannon]`、`[NUKE]`、`[MechTusk]` 之类 |
| art / 模型 / 图标 | 新建 art 段，或用 **rules 里的 `Image=`** 借用；不改原版 art 段 |
| 超武 | 新建类型并**追加**到 `[SuperWeaponTypes]` 末尾（保持既有序号不变） |
| 地图 | 新增自己的触发器/单位，不改地图既有逻辑（除非你点名） |

### 0.2 什么允许"追加"、什么禁止"改动"

- **允许追加**：`[VehicleTypes]` / `[InfantryTypes]` / `[SuperWeaponTypes]` 等**列表**末尾加新行
  （不能插在中间，否则既有序号整体位移）；
- **禁止改动**：任何**已有行**的键值 —— 尤其是 `[General]`、`[CombatDamage]`、
  `[NukeSpecial]` 这类"别人也在用"的段。
- **本 mod 的例外**：AI 调优类的全局参数（`[General]` / `[AI]` / 各建筑段）是本 mod 的**核心目的**，
  允许改，但必须**逐条登记**在 CHANGELOG 里，并为每条配一个构建期断言。

### 0.3 需要复用行为时：用"引用"而不是"改原版"

- 想沿用外观 → rules 的 `Image=`（例：`[ZAINukeGunship] Image=ZEP`）；
- 想沿用武器 → 新建武器段 + `Primary=` 指过去；
- 想沿用弹头 → 复制成新段再改（例：`[ZAINukeWH]` 从 `[DMISLEWH]` 复制）。

### 0.4 确实要改原版时（你点名的情况）

四件事必须同时做：① 记下原值；② 写进 CHANGELOG 的"原版改动"；③ 加一条构建期断言防回退；
④ 在文档里写清"影响面"（谁会受这条改动影响）。

### 0.5 提交前自检

1. **跑一次零售守卫**（已接进构建，构建失败即越界）：
   `python tools/check_retail.py --retail-dir "F:/Games/red2" --mod-dir mod/SuperAI`
   —— 它比较的是**零售 rulesmd 与构建产物**，不是 `git diff`；
2. 新增条目是否都在列表**末尾**、没打乱既有序号？
3. 有没有新条目依赖了公共表却没登记"这是例外"？
4. 所有"写错不报错"的点（缺 art、缺载荷键、`RechargeTime=0`）是否已有断言？

### 0.6 当前 mod 的「原版改动登记表」（唯一既定的例外：AI 调优）

> 机器可读版本在 `tools/check_retail.py` 的 `RETAIL_VALUE_EDITS` / `RETAIL_KEY_ADDITIONS`
> 两张白名单里；**构建会强制校验**，任何未登记的原版改动都会让构建失败。
> 当前实测：**20 个键被改值（5 个段）、69 个键被追加、17 个新增段、0 个删除**。

> 3.11.6 起 `[NASAM]` / `[NAFLAK]` **已还原为零售的 `0/0/25`**（原先给它们加地面分数，
> 只是让 AI 拿打不到地面的房子去应付地面威胁）。AI 的防空数量因此回落到零售水平 ——
> 这是"让引擎按设计工作"的代价，不是 bug：类别选择由**敌方三类造价份额**（各加 3000 底盘、
> 再按 `AIForcePredictionFudge` 浮动）决定，配置单方面扭不动它。

> 这张表是**唯一允许出现"改原版"的地方**。以后任何新的原版改动都必须先登记在此，
> 否则视为越界。

**改值的原版段（5 个）**

| 段 | 改动内容 | 性质 |
| --- | --- | --- |
| `[General]` | 14 个值 + 新增 `AIFriendlyDistance`（Ares 键）（`BuildSpeed`、`TeamDelays`、`MultiplayerAICM`、`AISlaveMinerNumber`、`AIRestrictReplaceTime`、`DissolveUnfilledTeamDelay`、`TargetDistanceCoefficientDefault`、`AISafeDistance` 等） | AI 调优 |
| `[AI]` | 4 个键（`AirstripRatio`、`AirstripLimit`、`ComputerBaseDefenseResponse`、`Paranoid`） | AI 调优 |
| `[GADEPT]` / `[NADEPT]` / `[YADEPT]` | 各 1 键（`AIBuildThis`） | **改原版单位数值**（保留，用户确认需要） |

（`[NASAM]` / `[NAFLAK]` 的 4 个键已于 **3.11.6 还原**，不再出现在本表。）

**`TargetDistanceCoefficientDefault` 的影响面（12→13 键）**：

- 作用范围：`[General]` 的全局威胁评分，**所有电脑户**的 `Greatest_Threat` 都读它；
  目标在武器射程外时每远 1 格（256 lepton）少 `0.4 × 256 ≈ 102.4` 分，约 977 格后才可能归零。
- 不改的东西：单位/武器/建筑数值、段结构、地图、存档格式；无随机数，同状态同选择。
- 行为变化：距离项从「最先遍历到的敌方工厂（≈最老）」改为「队长坐标最近优先」；
  最终评分仍叠加 A–D 四项，所以不是绝对最近优先。旧版本的回放/存档不再保证一致，这是预期。
- 验证：`tools/build_mod.py` 的 `assert_attack_script` 钉住 `-0.4` 与
  `[ZAIATK01-G]` 六步；`docs/ai-design.md` §3.2 写明机制与局限。
- 回滚：删掉 `RULES_EDITS` 里这一条（或把新值改回 `-10`）并重建，同时删掉
  `tools/check_retail.py` 的对应白名单项；`[ZAIATK01-G]` 的 `0=53,0` 也是单行回滚。

**`AISafeDistance=12` 与 `AIFriendlyDistance=20` 的影响面**：

- 作用范围：动作 `53`（`team_action_gather_at_enemy_base`）的集结点，值是「离**敌方**
  基地中心多少格」。所有用 `53` 的队伍都读它：`[ZAIATK01-G]`（151 支进攻队）与
  9 支保留零售脚本的超武队伍。
- 动作 `54`（`team_action_gather_at_friendly_base`）回**自家**基地中心；本模组 Ares=yes，
  54 读 `AIFriendlyDistance=`，未设时**回落**读 `AISafeDistance=`（`ares_rules_ext.rs:243-248`）。
  扩张 MCV 的脚本 `043F23CC-G` 正是 `0=54,0`，所以只改 53 会连带改 MCV 展开点。
- 原值 `20` 的问题：量的是**敌方**基地中心，而本模组每户铺 3 座基地、双方基地常常
  只隔十几格，20 格会落回**自家基地内部**，出征队伍等于在家门口集结 → 新基地堵车。
- `8` 的问题：三座厂的敌方基地半径常大于 8 格，8 格会落进**敌墙内**，队伍在敌基地里
  集结；`12` 是墙外折中。
- `AIFriendlyDistance=20`：把 54 单独拉回零售 20 格，扩张 MCV 不会因为 53=12 而把新
  基地种在旧基地旁边；53 仍为 12。
- 不改的东西：单位/武器/建筑数值、触发器、脚本步骤；无随机数，同状态同选择。
- 验证：`tools/build_mod.py` 的 `assert_attack_script` 钉住 `[General] AISafeDistance=12`、
  `AIFriendlyDistance=20` 与 `[ZAIATK01-G]` 六步；`docs/ai-design.md` §3.2 写明机制与局限。
- 回滚：删掉 `RULES_EDITS` 里 `AISafeDistance` 这一条（或改回 `20`）并重建，同时删掉
  `check_retail.py` 的 `aisafedistance` 白名单项；删掉插入 `AIFriendlyDistance` 的代码并
  移除 `check_retail.py` 的 `aifriendlydistance` 新增键项。

**`ComputerBaseDefenseResponse` 的影响面（[AI] 3→4 键）**：

- 作用范围：`TechnoClass::RespondToBaseAttack`（`sim/combat/base_defense_response.rs`）。
  建筑挨打时，受害 House 会把附近**无队伍、武装**的 Infantry/Unit 拉走，给它们
  `Rescue`/`AreaGuard` + `ArchiveTarget=Entity(victim)`；`AreaGuard + ArchiveTarget`
  就是引擎唯一的“护卫/跟随”语义。新扩建的建造厂一挨打，正在前线交战的散兵就会被
  抽回来围住它，看起来像“MCV 护卫”。
- 原值 `3`：预算 = `ThreatPosed × 3`，会扫描并改写附近单位的 mission。
- 新值 `0`：预算 = `ThreatPosed × 0 = 0`，`can_scan()` 恒假，不扫描、不抽 RNG、不写
  `ArchiveTarget`、不给攻击者冷却；AITrigger 组队不受影响。
- **代价（全 House 级）**：建筑被攻击时不再拉散兵回防；`ToProtect=yes` 的
  HARV/SMIN/DRED/AEGIS 等也不再被救。要“只关新基地护卫、保留矿车救援”需要引擎级区分，
  本次不做。
- 验证：`tools/build_mod.py` 的 `SECTION_KEY_EDITS` 强制写 `0`；`tools/check_retail.py`
  白名单含 `computerbasedefenseresponse`；实机打新建造厂（不要打 MCV）观察是否还有散兵掉头。
- 回滚：删掉 `SECTION_KEY_EDITS` 的 `"AI"` 项（或把值改回 `3`）并重建，同时删掉
  `check_retail.py` 的对应白名单项。

**给原版段追加键（12 个段，只加不改）**：
`[General] AINearestEnemy`；`[GACNST]/[NACNST]/[YACNST] SpySat`；
`[GAPILE]/[GAWEAP]/[NAHAND]/[NAWEAP]/[YABRCK]/[YAWEAP] AIBuildCounts`；
`[GAREFN]/[NAREFN]/[YAREFN] ProduceCashDelay/Amount`。

**列表末尾追加（不改既有序号）**：
`[VehicleTypes] 85/86`；`[SuperWeaponTypes] 13/14/15`。

### 0.7 新增 or 修改？判定流程

```
要加一个东西
   ├─ 只是"想要一个行为/单位/超武"？ → 新建条目（复制原版段改名）      ← 默认
   ├─ 需要沿用原版的模型/图标？       → 用 rules 的 Image= 引用           ← 不算改原版
   ├─ 需要沿用原版的武器/弹头？       → 新建段 + Primary=/复制后修改      ← 不算改原版
   ├─ 必须在某个列表注册？           → 只在末尾追加                       ← 允许
   └─ 必须改原版某段的键值？
          ├─ 用户点名要改？           → 改 + 登记 + 断言 + 写明影响面
          └─ 没点名？                 → 停下来问，或者找"新建副本"的替代方案
```

## 一、动手前的三个问题（顺序不能反）

1. **这东西属于哪一级？**
   - **地图级**（`.yrm`）：只影响那一张图；
   - **玩家级**（超武）：靠 `SW.AlwaysGranted` + `SW.AllowAI` 控制归属；
   - **全局级**（`rulesmd.ini` / `aimd.ini` 的公共表）：**所有地图、所有电脑**都受影响。
2. **验证信号是什么？** 必须是能看见的东西：日志行（`SuperWeaponTypes: N loaded`）、
   游戏内现象（有没有模型、炸多大、会不会开火），而不是"配置看起来对"。
3. **失败怎么退？** 每次改动前先想好"回滚是改哪一行"。

**铁律**：想让某个东西"只给人类玩家"，就走**新超武类型**，不要改公共表。
公共表的"唯一合法例外"是：改完之后**明确知道还有谁在用它**，并且把那些使用者一起隔离
（例如把 `[CombatDamage]` 调大后必须关掉零售高炮的散布）。
——但按第零节的总原则，**优先选"新建条目"而不是"改公共表再隔离"**：
后者是补救手段，前者才是默认做法。

---

## 二、确认过、可以直接复用的正确路径

### 2.1 给玩家一个专属超武（最干净的"只给人类"载体）

```ini
[SuperWeaponTypes]
13=ZAIUnlimitedNuke

[ZAIUnlimitedNuke]
Type=MultiMissile
RechargeTime=0.01        ; 注意：写 0 会被当成"未设置"，回落到 10 分钟
SW.Shots=1000
SW.AllowPlayer=yes
SW.AllowAI=no            ; ← 电脑拿不到
SW.AlwaysGranted=yes     ; ← 不需要建筑，开局就有
SW.RequiresTarget=yes
```

实测有效、全局生效、不依赖国家选择。

### 2.2 用超武把**自建单位**投给玩家

```ini
[SuperWeaponTypes]
14=ZAINukeGunshipDrop

[ZAINukeGunshipDrop]
Type=UnitDelivery        ; 引擎里真实存在的实现（sim/superweapon/unit_delivery.rs）
Action=Nuke
RechargeTime=0.01
SW.AllowPlayer=yes
SW.AllowAI=no
SW.AlwaysGranted=yes
SW.InitialReady=yes      ; 开局即可用
SW.RequiresTarget=yes
Deliver.Types=ZAINukeGunship    ; ← 载荷键是 Deliver.Types，不是 UnitDelivery.Types
```

配套事实：`Type=PlaceUnits` **无效**；`UnitDelivery.Types` **无效**（写错就"点了没反应"）。

### 2.3 新单位要有模型：`Image=` 写在 **rulesmd**

```ini
; rulesmd.ini
[ZAINukeGunship]
Image=ZEP          ; 借用基洛夫的 art/voxel（零售同款： [JUMPJET] Image=ROCK）
```

**反例**：在 `artmd.ini` 里新建 `[ZAINukeGunship] Image=ZEP` —— **仍然隐形**，
因为引擎按对象 ID 去找 `ZAINukeGunship.vxl`，找不到就不画。

### 2.4 让核弹弹丸"乱飞"：散布是**弹丸级**的

```ini
[ZAINukeRifleProj]
Arcing=true            ; 弹道弹
Ranged=yes             ; 非追踪（追踪弹永远精确）
Inaccurate=yes         ; 不吸附目标点
FlakScatter=yes        ; 会散
BallisticScatter.Min=50    ; ← 武器专属散布下限（格），实测生效
BallisticScatter.Max=200   ; ← 武器专属散布上限（格），实测生效
AG=yes                 ; 要打地面就必须 AG=yes
```

要点：
- **半径用 `BallisticScatter.Min/Max` 写在弹丸段里**（实测有效，公共表不用动）；
- `[CombatDamage] BallisticScatter` 是**全局唯一段**，改它会波及所有弹道/高炮使用者
  （零售注释：`maximum scatter distance (cells) for inaccurate ballistic projectiles`）；
- **追踪弹（有 `Arm`/`ROT`）永远不会散**，必须有 `FlakScatter` + 非追踪 + 弹道。

### 2.5 伤害与爆炸范围：克隆现成弹头

```ini
[ZAINukeWH]            ; 3 星（精英）无畏导弹弹头
CellSpread=3
PercentAtMax=.5
AnimList=MININUKE      ; 小蘑菇云
Verses=100%,90%,80%,100%,80%,80%,85%,65%,28%,80%,0%
```

命名规律：**精英版 = 同名 + `E`**（`[DMISLWH]` 1.5 格 → `[DMISLEWH]` 3 格）。
三档参照：普通导弹 1.5 格 / 3 星无畏 3 格 / 零售核弹 10 格（`[NUKE]`，别动）。

### 2.6 自动开火与射程

```ini
GuardRange=20          ; 真正的"自动索敌半径"，必须等于武器 Range
CanPassiveAquire=yes   ; 自己找目标
OpportunityFire=yes    ; 边飞边打
CanRetaliate=yes       ; 挨打还手
```

**坑**：只改武器 `Range` 不会让它主动开火；`GuardRange` 大于 `Range` 会让它追着打不到的目标转。

### 2.7 打不死、不被瞄

```ini
Strength=100000
Insignificant=yes      ; AI 的防空不把它当目标
```

### 2.8 基洛夫机体（不需要停机位）

```ini
BalloonHover=yes
Locomotor={92612C46-F71F-11d1-AC9F-006008055BB5}
MovementZone=Fly
ConsideredAircraft=yes
```

### 2.9 给自建超武/单位一个自己的显示名：`UIName` 是 **CSF 标签**

`UIName=` 不是文字，是字符串表里的标签；`Name=` 只是内部名，游戏不显示。标签查不到时引擎
**不回退**，而是照字面画 `MISSING:'NAME:…'`（`src/assets/csf_file.rs::text`，单元测试钉死）。
所以自建条目要显示自己的名字，就得把标签**装进模组**：

```ini
; rulesmd.ini
[ZAINukeGunshipDrop]
UIName=Name:ZAINukeGunshipDrop
Name=Nuclear Gunship (drop)      ; 只是内部名
```

```
mod/SuperAI/ares.csf             ; 由 tools/csf.py 生成
Name:ZAINukeGunshipDrop=核弹炮艇
```

- Ares 表单下引擎在 `ra2md.csf` 之后追加 `ares.csf`（**与语言无关**）→ `ares_<语言>.csf`
  → `stringtableNN.csf`，后加载的同名标签覆盖先前的；
- 启动日志 `Loaded CSF string table: ra2md.csf; supplements=["ares.csf"]` 是硬证据（空数组 =
  没读到 = 游戏里必然 `MISSING:'…'`）；
- **用通用 `ares.csf`，别用 `ares_ch.csf`**：带语言后缀的表语言码不匹配就静默丢弃；
- 想沿用零售文字就直接指零售标签（`Name:Nuke` / `Name:ZEP`），不要新建重复行。

### 2.10 想要核弹的蘑菇云、但不要闪白和全局光照：克隆 `[NUKE]` 换个名字

引擎的核弹命中特判是按**弹头名字** `strcmpi(warhead, "NUKE")` 进的
（`src/sim/projectile.rs::nuke_impact`）：进去之后闪白屏 + 整张地图光照重算 + 雷达事件 +
等 `NUKEBALL` 才引爆。把同一张伤害表**换段名**就绕开整个特判：

```ini
[ZAINukeMissileWH]     ; 零售 [NUKE] 的 9 个键一字不改，只换段名
CellSpread=10
PercentAtMax=.02
WallAbsoluteDestroyer=yes
Wood=yes
Verses=100%,100%,100%,200%,100%,100%,60%,100%,8%,100%,100%
InfDeath=7
Sparky=no
Tiberium=yes
AnimList=NUKEANIM      ; artmd 注释：nuke mushroom cloud explosion
```

结果：蘑菇云还在、伤害半径不变，屏幕不闪、地图光照不动。
`assert_nuke_warhead_clone` 拿零售 `[NUKE]` 逐键比对（多键也报错），
`assert_nuke_gunship` 断言弹头**不得叫 `NUKE`**。

### 2.11 子母弹：`Airburst=` 是分支开关，**颗数**只有 `Splits=` + `Cluster=` 能点名

> 本模组的集束炮艇从 3.13.7 起**不再使用这条链**（原因见 §2.12）；下面仍是这台引擎的完整规则，留档。

```ini
[ZAINukeClusterProj]
Arcing=true
Ranged=yes
Inaccurate=yes                 ; 落点不吸附目标 → 母弹在自己的落点爆
FlakScatter=no                 ; ★ 开着会走 flak 支路，散布按「距离/射程」缩水
BallisticScatter.Min=50        ; 母弹落在瞄准点外 50-100 格 —— "大范围"只能靠这里
BallisticScatter.Max=100
Airburst=yes                   ; 命中后进入分裂（弹丸键，零售 [V3AirburstP] 就在用）
AirburstWeapon=ZAINukeClusterChild   ; ★ 缺它整段静默不分裂
Splits=yes                     ; ★ 计数支路；AirburstSpread= 在这个支路里是死键
Cluster=8                      ; ★ 唯一能点名「正好 N 颗」的键
AroundTarget=yes               ; 分裂中心 = 瞄准点（否则 = 母弹落点）
RetargetAccuracy=0             ; 每颗子弹取不同的目标（写 1 会全扑同一个格）
RetargetSelf=no
```

- **颗数**：不带 `Splits=` 时，子弹数 = 落点半径内的**地图格数**（`sim/combat/airburst.rs::cell_range`，
  一格一颗），只可能是 1/5/9/13/21/29/37/49…，**没有 8**；`Cluster=` 只在 `Splits=yes` 支路里被读，
  而且该支路的目标池 = 5 格内的敌方 Techno + **±3 格**随机格，所以"正好 8 颗"与"落点铺很开"
  在引擎里不可兼得：8 颗落在瞄准点 ±3 格内。**飞 50–100 格**由母弹的 `BallisticScatter` 提供；
- **`BallisticScatter` 的坑**：`Inaccurate=yes` + `Arcing=true` 会选中 flak 散布支路，
  幅度 = `random(min,max) × 实际距离 ÷ 武器射程`（`launch.rs::flak_magnitude`）。射程 200、在 100 格
  开火时 50–100 的抽签只剩 25–50 格。写 `FlakScatter=no` 切到普通支路，值原样使用（3.13.6）；
- **子武器必须再用某个 TechnoType 武器槽登记一次**（`Primary`/`Secondary`/`Elite*`/`DeathWeapon`）。
  只被 `AirburstWeapon=` 命名的武器，引擎会在 **Bullet 扫描**里才分配
  （`native_processing/pass_families.rs:337-341`），而 Weapon 扫描已经跑完 → **段永不读取**：
  `damage=0`、`projectile=None` → `ares_emit` 直接 return，一颗子弹都不出（3.13.2 的实锤；
  证据见 `native_processing_tests.rs::airburst_reference_retains_rebinds_and_keeps_native_factory_timing`，
  零售 `rulesmd.ini:6559` 的 `Secondary=V3Cluster ;gs Looks like hack is weapons must be represented once`
  就是同一个坑）。本模组：`[ZAINukeGunship3] Secondary=ZAINukeClusterChild` + 子武器 `Range=0`；
  运行期证据：日志 `RuleSet loaded` 的 projectile 数 **42 → 43**；
- **`spawn_ares_child` 不读 `BallisticScatter`**：子子弹没有自己的散布，落点就是它被指派的那个格
  （或那个单位），所以"子弹散在 50–100 格范围里"做不到（半径 50 格 = 317 颗、100 格 = 3 万+ 颗）；
- **`ROT>0` 的子弹出膛速度是 1 雷普顿/帧**（`bullet_fire_homing_velocity` = `scale_to_speed(v,1,..)`），
  靠 `Acceleration=` 逐帧爬到武器 `Speed=`；但 **`Acceleration` 只能小（1..17）**：第一步
  `advance(old, velocity, 1)` 先按"竖直向下"的当前速度直走 `1+Acceleration` 雷普顿，转向在之后；
  子弹出生被 `bullet_unlimbo_coord` 抬到地面+1，地形跟随块每帧只补 **18**，第一步超过 18 就钻进地下，
  第二帧 `old_height <= 0` 判触地 → 在爆点自爆（3.13.4/3.13.5 的 `Acceleration=250` 就是这样）；
  本模组 10（下沉 11，净 +7），爬升到离地约 2 格后平飞；
- **`Arm=` 是子弹的免疫窗口**：`ROT>0` 必开近炸引信，但引信只在 `Arm=` 到期后检查；
  要"散布途中不被引爆"就把 `Arm=` 设得比飞行时间长（本模组 45 帧/3 秒）；
- **分裂中心由 `AroundTarget=` 决定**：默认取母弹落点，`yes` 取瞄准点。想让子弹飞出落点必须开它
  （3.13.4）；
- **`Sight` 必须 ≥ `GuardRange`**：玩家单位只打自己看得见的目标，`Range=200` + `Sight=20` 实际就是
  20 格射程（3.13.3）；
- **子子弹丸必须是追踪弹（`ROT > 0`）**，零售 `[V3AirburstP]` 的子武器用的就是
  `[ClusterBits]`（`Arm=2` + `ROT=60`）。原因：空气爆给的出膛速度几乎是**正下方**，原生引擎靠
  随后的 `MoveTo` 把子弹重新指向目标格；VERA 这条链没有 `MoveTo`，只有
  `FiredBullet::launched` 在 `rot > 0` 时才重算朝向，而 `ProjectileTrajectory::Ballistic`
  只做重力积分、永不重瞄 → `ROT=0` 的子子弹全部在母弹落点原地炸（3.13.0 的"看不到子弹"）；
- 追踪弹不会散，所以子子弹丸写 `Inaccurate`/`FlakScatter`/`BallisticScatter` 都是废键；
- **子弹只从子武器读 `Damage`/`Warhead`/`Projectile`/`Speed`**（`ROF`/`Range` 是炮塔冷却，用不上），
  且子武器**必须有 `Projectile=`**，否则引擎连一颗都不发；
- **子级绝对不能再写 `Airburst`/`Splits`/`ShrapnelCount`**，否则一炮变指数级（构建期断言拦）；
- **别用零售 `[NUKE]` 当子弹弹头**：每颗子弹都会触发核弹特判（见 §2.10），闪白 + 全图光照重算；
- **`DetonationAltitude=` 与"半空开爆"无关**：该键只服务 `Vertical=yes` 的上升弹道
  （`projectile_delivery.rs`：`vertical.then_some(detonation_altitude)`），`Arcing` 炸弹上它是死键；
  给母弹写 `Vertical=yes` 会让它从发射点往上飞，不是在空中拦截（3.13.6 查源）。

### 2.12 为什么最后放弃子母弹：±3 格是硬边界，改引擎又太脆

需求是「一颗母弹炸开，8 个落点散在母弹周围 0–100 格」。这台引擎给不了：

- `Splits=` 支路的随机格写死 `RandomRanged(-3, 3)`，且 `spawn_ares_child` 不读任何散布键；
- `AirburstSpread=` 支路一格一颗，颗数只能是 1/5/9/13/21/29…，没有 8，半径拉到 100 就是 3 万颗；
- 改引擎（加 `ClusterSpread=`）确实能做到，但每次游戏更新都要重新编译、重新打补丁——不可接受。

最终结构：**一次开火 8 发，每发自己抽 0–100 格的 `BallisticScatter`**。最终落点集合与需求一致
（8 个点散在 100 格内、彼此独立），而且纯 INI、不依赖任何非官方键。代价是失去「母弹→子弹」这一层；
两段 0–100 相加的真实支撑是 0–200，纯 INI 只能二选一（`Max=100` 或 `Max=200`）。

## 三、黑名单（试过、无效或有害，别再试）

| 做法 | 结果 |
| --- | --- |
| `[General] ParaDrop.Types=<载具>` | 投出来是普通伞兵（引擎只读四张按阵营的**步兵**表） |
| 改 `AmerParaDropInf` 等四张表 | **玩家与电脑共用** → 电脑也投同样的东西，属于越权，已回滚 |
| `Type=DropPod` + `DropPod.Types` | 点击毫无反应 |
| `Type=SpyPlane` + `SpyPlane.Type/Count/Mission` | 飞机横穿但不使用武器、航线写死、还会被打掉 |
| `Type=MultiMissile` + `Range/LineMultiplier` 想散射 | 只有一发普通核弹（弹头来自全局 `[General] Nuke.Payload`） |
| `Type=Battery` + `SW.MaxCount` | 无效 |
| `Type=PlaceUnits` | 无效 |
| `artmd.ini` 里写 `Image=` | 无效（单位隐形） |
| `[CombatDamage]` 想"给某个单位单独一份" | 全局唯一段，写两个只会覆盖 |
| `Airburst=yes` 只写在弹丸上、不配 `AirburstWeapon=` | **静默不分裂**（引擎整段 return）。`Airburst` 本身是**真弹丸键**（零售 `[V3AirburstP]` 在用）；3.11 那次"无效"的结论是漏了 `AirburstWeapon=`，已改正，见 §2.11 |
| 靠 `Cluster=` 数子母弹的颗数 | 不带 `Splits=yes` 时引擎**根本不读** `Cluster=`；颗数由 `AirburstSpread=` 的格数决定（一个格一颗） |
| `Airburst` 的子子弹丸写成 `Arcing` / `ROT=0` | 子子弹保留空气爆的**竖直向下**出膛速度，而引擎只对 `ROT>0` 的弹体重瞄、弹道轨迹永不重瞄 → 全部在母弹落点原地炸，看起来"没有子弹"（3.13.0 实录）。子子弹丸必须追踪（`ROT=60`，见 §2.11） |
| 子武器只写 `AirburstWeapon=`、不挂任何单位槽位 | 武器在 Weapon 扫描之后才被分配，**段永不读取**（`projectile=None`）→ 一颗子弹都不出（3.13.2 实录）。必须再用 `Secondary=`/`DeathWeapon=` 之类登记一次（见 §2.11） |
| `RechargeTime=0` | 被当成"未设置"，回落 10 分钟 |
| 追踪弹想靠 `HomingScatter` 散 | 追踪弹永远咬住目标，照样精确命中 |
| `UIName=NOSTR:内联文字` | **VERA20k 没实现** Ares 的 `NOSTR:` 前缀：引擎里没有任何 `NOSTR` 解析，Ares 的 `Misc/CSFLoader.cpp` 钩子是 Deferred。游戏会把整个 `NOSTR:…` 当成一个查不到的标签，画成 `MISSING:'NOSTR:…'` |
| `UIName=` 指向 CSF 里没有的标签 | **不回退**，照字面画 `MISSING:'NAME:…'`；自建条目要把标签装进模组的 `ares.csf`（见 §2.9） |
| 自建武器挂零售 `Warhead=NUKE` | 每次命中都触发核弹特判：闪白屏 + 整张地图光照重算 + 雷达事件 + 等 `NUKEBALL` 才引爆。要蘑菇云就克隆该弹头**换个段名**（见 §2.10） |

---

## 四、方法论（下次照这个流程走）

1. **先分类，再动手**：新键/新段属于哪一类（Projectile / Weapon / Warhead / VoxelAnim /
   General / Art / Map）？—— **查二进制字段表 + 查读者**，不要信教程措辞。
   反例就在本手册里：`Airburst` 曾被判成"VoxelAnim 键"（其实它是弹丸键，只是缺
   `AirburstWeapon=` 时静默不生效），`Cluster=` 看着像"子母弹颗数"（其实只有 `Splits=yes`
   支路才读它）—— 两个都是"看名字猜语义"猜错的。
2. **一次只变一个变量**，并给用户一个明确的验证动作（"打一梭子看落点"）。
3. **静默失败要变断言**：凡是"写错不报错、只是不生效"的（缺 art → 隐形、缺 `Deliver.Types`
   → 点了没反应、`RechargeTime=0` → 回落），构建期就断言掉。
4. **改公共表前先列出所有使用者**，能隔离就隔离，不能隔离就问用户要不要承担。
5. **发现方向错了就整体回滚**，不要"顺手把对方也关了"（那是越权，不是修复）。

---

## 五、今日版本轨迹（供回溯）

| 版本 | 内容 | 结果 |
| --- | --- | --- |
| 3.9.x | 试图用超武一次撒满全图（`MultiMissile`/`Battery`/`SpyPlane`/`DropPod`） | ✗ 全部无效 |
| 3.10.0–3.10.6 | 改为空投核弹兵，逐步修好武器/弹道/弹头 | ✗ 空投表是公共的，且只能投步兵 |
| 3.10.7–3.10.8 | 试图关电脑空投 → 越权 → **整体回滚** | — |
| 3.10.9–3.10.10 | 发现 `UnitDelivery` + 找到正确键 `Deliver.Types` | ✓ 投放成功 |
| 3.10.11–3.10.12 | 修模型：`Image=` 要写在 rulesmd | ✓ 有基洛夫外形 |
| 3.11.0–3.11.2 | 两艘飞艇（20 格追踪弹 / 200 格弹道核弹）+ 武器级散布 | ✓ 确认可用 |
| 3.12.0 | 三个超武分名（`UIName` 是 CSF 标签 → 模组自带 `ares.csf`）；第二艘 200 索敌；弹头换名去掉闪白/全局光照 | ✓ 构建断言 + 无头日志 `supplements=["ares.csf"]` |
| 3.13.0 | 第四个超武「集束炮艇」：`Airburst=` 子母弹（颗数由 `AirburstSpread` 决定） | ✓ 13 颗/发，负向测试 6 项 |
| 3.13.1 | 子子弹丸改追踪（`ROT=60`）修"看不到子弹"；母/子弹头互换；三艘炮艇定价 | ✓ 13 项负向测试 |
| 3.13.2 | **真根因**：只被 `AirburstWeapon=` 命名的子武器在读段之前就被扫过 → 用 `Secondary=` 登记；日志 `42 → 43 projectiles` | ✓ 4 项新负向测试 |
| 3.13.3 | 29 颗子弹（`AirburstSpread=3`）、母弹散布 50–100、`Sight=200`；确认"子弹散布 50–100 格"在引擎里不可行 | ✓ 4 项新负向测试 |
| 3.13.5 | 子弹散布途中免疫引爆（`Arm=45` + `Proximity=no`）；母武器 `Burst=3` 让 3 个落点各自铺开 | ✓ 6 项负向测试 |
| 3.13.6 | 集束炮艇定稿：`Burst=1`、`Splits=+Cluster=8`（`AirburstSpread` 数不出 8）、`FlakScatter=no` 让 50–100 格不随射程缩水 | ✓ 9 项负向测试 |
| 3.13.4 | 子弹真的飞出去了：`AroundTarget=yes` + 子武器 `Speed=800` + 子弹丸 `Acceleration=250`（出膛速度被归一化成 1、靠加速度爬升） | ✓ 4 项新负向测试 |
