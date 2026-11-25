# Changelog

本项目在 2026-11-22 从零迭代到 2.0，同日继续到 3.7；以下是可复现的功能节点。

## Unreleased — 53 集结点 8→12；54 展开点用 AIFriendlyDistance=20

- **动作 53**（到敌方基地外集结）的 `[General] AISafeDistance` 由 `8` 改为 **`12`**：
  8 会落进三座厂敌基地的墙内，12 在敌墙外，同时不像 20 那样在敌我基地靠近时落回自家。
- **动作 54**（回自家基地/扩张 MCV 展开点）新增 **`[General] AIFriendlyDistance=20`**
  （Ares 键）：Ares 下 54 读它，未设时回落 `AISafeDistance`；这样 53=12 不再把 MCV
  展开点一起拖到 12，扩张基地仍按零售 20 格展开。
- 落盘：`build_mod.py` 的 `RULES_EDITS` 改 12，并在 `AISafeDistance=` 后插入
  `AIFriendlyDistance=20`；`assert_attack_script` 同时钉 12/20/六步；`check_retail.py`
  的 `[General]` 新增键白名单加 `aifriendlydistance`；文档同步。
- 残余“向新基地聚集”的主因仍是引擎 `MoveGroundForcesToBase`（每次建造厂展开把全户
  地面部队发到新基地旁同一个格），数据层无关闭键；本次只把新基地拉回 20 格，不承诺消除。

## Unreleased — 关闭基地防御响应：MCV 扩张不再拉护卫

- `[AI] ComputerBaseDefenseResponse` 由 `3` 改为 **`0`**：`RespondToBaseAttack` 的预算
  变成 `ThreatPosed × 0 = 0`，建筑挨打时不再扫描/改写附近单位的 mission，不再出现
  `AreaGuard + ArchiveTarget` 的“护卫/跟随”。
- 现象根因：新扩建的建造厂被攻击时，附近**无队伍、武装**的散兵（常是正在前线交战的）
  被拉去围新基地，看起来像在护卫 MCV；MCV 本身无 `ToProtect`、无武器，不会叫援。
  MCV 的 TeamType/TaskForce/Script 与零售零差异，改它们无效。
- 代价（全 House 级，已接受）：建筑被攻击时不再拉散兵回防；`ToProtect=yes` 的
  矿车/采矿车/无畏舰等也不再被救援。只想关“新基地护卫”而保留矿车救援需要引擎改动，
  本次不做。
- 落盘：`build_mod.py` 的 `SECTION_KEY_EDITS["AI"]` 写 `0`；`check_retail.py` 的
  `[AI]` 白名单加 `computerbasedefenseresponse`；`docs/boundaries-and-lessons.md` 登记影响面。

## Unreleased — AITrigger 积极发展：修死条 + 抬下限 + 3 条保底进攻

- **修死数据**：7 条零售触发器三难度位全关（`d000`，永不可命中），按名字声明的
  难度恢复：`Allied Bombard - E1` / `Soviet Bombard Easy` → `100`；
  `Allied Spy vs Allied Tech` / `Allied IFV Rush ×2` / `Soviet Siege Bunker ×2` → `011`。
- **抬权重下限**：46 条 condition 4 攻击触发器的 `下限` 抬到 `起始值`（44 条实际变化），
  上限与 `AITriggerSuccess/FailureWeightDelta`（+20/−50）保留 —— 失败最多掉回起始值，
  不再掉到 10，修「面对强玩家越打越软」。
- **3 条保底进攻**：盟/苏/尤各 1 条 `condition=-1`、`d111`、权重 `30/30/30`
  （`ZAIALW01-G…03-G`），复用 `Max≥2` 的现有队伍；低于 5000 接管与 1000 防空，
  只是一个「无论如何都会出点兵」的地板。
- **与 2.4 的差异**：2.4 曾把「250 权重 + 三难度全开」整批撤回；本次**没有**恢复那套，
  没有解耦 42 条反制/任务条件，反渗透/MCV/超武的 5000 未动。可命中数
  Easy/Normal/Hard `30/103/122 → 35/111/130`。
- **守卫**：新增 `assert_attack_triggers_boosted`（171 条 / 18 token / 64 hex /
  无 `d000` / 46 条下限=起始 / 新条形状与队伍 `Max≥2` / condition 直方图与关键反制
  条目）；重建仍走 `tools/build_mod.py`，`docs/ai-design.md` §3.3 与
  `docs/ai-tuning-playbook.md` §10.4 同步。

## Unreleased — 全模式放开：7 张自建图支持全部过滤名

- 7 张 `SuperAI-*.yrm` 的 `[Basic] GameMode=` 从 `standard`（部分图还带无效的
  `nukewar`）改为 `standard, teamgame, megawealth, duel, meatgrind, navalwar`；
  `tools/build_maps.py` 增加 `GAME_MODES`、`flat --game-modes`、`ice/ice120` 的
  `ensure_value` 与 `modes` 断言，重建不会回退。
- 新增 `mod/SuperAI/mpmodesmd.ini`，把 4/5/6/7/8 行放进 `[Battle]` 类，并在
  `mod.ini` 的 `[Files]` 设 `Modes=mpmodesmd.ini`；离线 Skirmish 下拉从 3 个模式
  变为 8 个（Battle、Unholy、Megawealth、Duel、MeatGrind、NavalWar、TeamGame、
  FreeForAll）。
- 代价（已接受）：Unholy（邪恶联盟）移入 Battle 类后失去双 MCV 专属规则；
  Cooperative 仍不列出（2 人上限，不适配 120 人图）。

## Unreleased — All to Hunt 60 秒、机场编队 4 架

7 张 SuperAI 地图的 `AIHunt*` 事件从 20 秒改为 60 秒；`tools/veramap.py` 的默认值同步。
`RevealAll`（1 秒）与 `IronCurtain`（10 秒）不变，规则/AI INI 不变。

- 机场型飞机（`ORCA`/`BEAG`，即入侵者/黑鹰）编队 3 → 4 架；`Max=3` 不变，
  4 架正好一座空指部的 4 个停机位。

**AI 进攻：移动到敌方基地外 + 就近选点（数据层近似）**

- **原版改动**：`[General] TargetDistanceCoefficientDefault` 由 `-10` 改为 `-0.4`。
  原版在约 **39 格外**把威胁分钳成 1 分（同分不替换），AI 实际总挑**最老**的敌方工厂；
  `-0.4` 让距离项在整张地图（最大对角 707 格）上单调，距离项最近者严格胜出
  （最终评分仍叠加 A–D 四项）。
- **新行为**：`[ZAIATK01-G]` 从 5 步变 6 步——`0=53,0` 先到敌方基地外
  `AISafeDistance=8` 格（本版由 20 调到 8，见下；`Mission::Move`；其中 **123 支**
  `Suicide=no` 队伍会途中
  被动索敌并开火，**28 支** `Suicide=yes` 特种队只行军不开火），`1=0,6` 起保持
  原攻击序列。仍是 **151 支队伍**，MCV/超武队伍脚本不变。
- **守卫/文档**：`tools/build_mod.py` 新增 `assert_attack_script`（钉住系数与六步），
  `tools/check_retail.py` 登记该键；`docs/ai-design.md` §3.2 与
  `docs/boundaries-and-lessons.md` 同步；`mod.ini` 版本未动。
- **局限**：数据层近似——`53` 只到敌方基地中心外 8 格，不是最近工厂；途中索敌半径
  仍是 `GuardRange=`/武器射程（犀牛约 5.75 格）；不是真正的 attack-move（交战后不回
  原路径）；旧存档/回放会分歧。

**新基地堵车：集结点 20→8 格、扩张 MCV 同时 1 台**

- **原版改动**：`[General] AISafeDistance` 由 `20` 改为 `8`。动作 `53` 的集结点是
  「离**敌方**基地中心多少格」，原版 20 在双方基地靠近时会落回自家基地，出征队伍在
  家门口集结 → 新基地堵车；`8` 仍在敌方基地墙外。
- **数据改动**：3 支 MCV 队伍的 `Max` 由 `2` 改回零售的 `1`，同一户同时只跑 1 台
  扩张基地车（两台同时上路会奔向同一块空地、互相挡住部署，日志 `MCV deploy blocked`）。
  扩建仍按「建造厂 < 3」触发器逐台补齐到 3 座，只是串行而不是并行。
- **守卫**：`assert_attack_script` 新增 `AISafeDistance=8` 断言；新增
  `assert_mcv_team_max`（3 支 MCV 队伍 `Max=1` 且仍用 `043F23CC-G`）；
  `tools/check_retail.py` 登记 `aisafedistance`。
- **文档**：`docs/ai-design.md` §3.2/§3.3、`docs/boundaries-and-lessons.md` 登记表、
  `docs/ai-tuning-playbook.md` §9.2 与 `README.md` 的基地数量说明同步。

## 3.13.10 — 集束炮艇：每发母弹只裂 1 颗，4 母 + 4 子 = 8 个弹头

`Cluster=2` → **`Cluster=1`**。一发的结果：

- 4 发母弹各自落在点击点外 0–200 格，各自是一颗 10 格核爆（4 个坑）；
- 每发母弹裂 **1 颗**子弹，4 颗全部飞回点击点 ±3 格炸开（第 5 个点）；
- 弹头总数 **8**（4 母 + 4 子），落点 **5 个**。

比 3.13.9 少 4 个弹头，目标点也没那么拥挤。`assert_nuke_gunship3` 的 `Cluster` 断言同步改成 1
（写回 2 会被拒绝）。


## 3.13.9 — 母弹也是核爆，子弹集中回点击点：4+1 个落点

| 项 | 3.13.8 | 3.13.9 |
| --- | --- | --- |
| 母弹弹头 | `ZAINukeWH`（3 格小爆） | **`ZAINukeMissileWH`**（10 格核爆 + `NUKEANIM`） |
| 分裂中心 | `AroundTarget=no`（母弹落点） | **`AroundTarget=yes`**（点击点） |
| 子弹 `Arm` | 60 | **120**（母弹最远落 200 格外，子弹要飞 ~6.7 秒） |

一发的结果：**4 个随机核爆**（母弹落在点击点外 0–200 格）+ **1 个被集火的点**
（8 颗子弹全部飞回点击点 ±3 格）＝ 5 个落点。

**为什么这样更划算**：`Splits` 的第二层随机只有 ±3 格，8 颗摊在四颗母弹周围只会糊成 4 团；
集中回点击点，反而把"4 团"变成"4 团 + 1 个被砸烂的目标"。

**代价**：弹头总数是 12（4 母 + 8 子），不是 8；目标点的 8 颗子弹依然重叠成一团，
看不出 8 个坑。想减负就把 `Cluster=2` 改成 `1`（4 母 + 4 子 = 8 个弹头，落点还是 5 个）。

**守卫更新**：母武器 `Warhead` 必须等于子武器的 `ZAINukeMissileWH`（旧的小爆会被拒绝）；
`AroundTarget` 必须 `yes`；子子弹 `Arm≥45`。负向测试：换成小爆、改回 `AroundTarget=no`、
`Burst=8`、子 `Arm=30` 全部按预期拒绝。


## 3.13.8 — 集束炮艇：4 发齐射 × 每发 2 颗 = 8 颗核弹

**思路**：`Burst` 每 tick 只打一发、默认间隔 3–5 帧，而且单位只有 4 个 `BurstDelay0..3` 槽，
所以 8 发必然拖成 1.4–2.3 秒的排队。改成 **4 发**（四个延迟全 0，约 0.27 秒，和精英天启同款），
每发母弹再分裂 **2 颗**子弹，数量凑回 8。

| 项 | 值 |
| --- | --- |
| 齐射发数 | **`Burst=4`** + `BurstDelay0..3=0`（约 0.27 秒） |
| 每发母弹 | `BallisticScatter 0/200` + `FlakScatter=no`，落点击点外 0–200 格，只有 3 格小爆（`ZAINukeWH`） |
| 分裂 | `Airburst=yes` + `AirburstWeapon=ZAINukeClusterChild` + `Splits=yes` + `Cluster=2` |
| 子弹落点 | **`AroundTarget=no`** → 以母弹落点为心，±3 格内随机取格（每颗各抽各的） |
| 子弹弹头 | `ZAINukeMissileWH`（10 格、`NUKEANIM`、不闪白） |
| 合计 | **4 × 2 = 8 颗核弹**，4 组落点铺在 0–200 格 |

**换回的子链**（3.13.7 曾删除）：`Secondary=ZAINukeClusterChild`（武器登记，否则读段太晚）、
子武器 `Range=0`、子弹丸 `ROT=60` / `Acceleration=10` / `Arm=60` / `Proximity=no`。
`Acceleration` 仍然必须小：第一步下沉 `1+Acceleration`，地形跟随每帧只补 18。

**代价（必须知道）**：一组里的 2 颗子弹相距 ≤6 格，而弹头是 10 格，所以屏幕上看到的是
**4 团**核爆（每团带一次母弹小爆），不是 8 个分开的坑。要 8 个可分辨的坑，第二层散布就得
几十格——那是引擎改动，已经否掉。

**新增守卫**（8 项负向测试全过）：`Burst` 字面量 4；四个 `BurstDelay` 必须 0；`Cluster` 字面量 2；
`AroundTarget` 必须 no；`Secondary` 必须是子武器；子子弹 `ROT>0`、`Arm≥45`、`Acceleration 1..17`；
`FlakScatter` 必须 no。


## 3.13.7 — 集束炮艇改成 8 发齐射：不再依赖子母弹，落点 0–100 格全随机

**触发这一版的是两条硬约束**：① 你要的「8 个落点散在 0–100 格」在 `Splits=` 支路里写死为 ±3 格
（`airburst.rs`: `RandomRanged(-3, 3)`），`AirburstSpread=` 的颗数又只能是 1/5/9/13/21/29…；
② 改引擎虽然能做到，但每次游戏更新都要重新编译、重新打补丁——不可接受。

**新结构**：一次开火 **8 发**，每发都是独立的一次 `FireAt`，各自抽自己的 `BallisticScatter`：

| 键 | 值 | 作用 |
| --- | --- | --- |
| `Burst` | **8** | 一次扳机 8 发（每发独立抽签，不累积） |
| `Warhead` | `ZAINukeMissileWH` | 每发直接是 10 格核爆（不再分成母弹/子弹两层） |
| `BallisticScatter.Min/Max` | **0 / 200** | 每发落在点击点外 0–200 格任意处 |
| `FlakScatter` | **no** | 否则按「实际距离 ÷ 射程」缩水，半程只剩 0–50 |

**删掉的东西**：`Airburst=`/`AirburstWeapon=`/`Splits=`/`Cluster=`/`AroundTarget=` 以及
`ZAINukeClusterChild`、`ZAINukeClusterChildProj` 两段和 `Secondary=` 登记槽。少一条链，就少一处
引擎实现差异带来的风险（这条链在 3.13.0–3.13.6 里踩过 4 个坑：追踪弹、武器登记顺序、出膛速度归一化、
第一帧下沉）。纯 INI，引擎更新不用重编。

**关于「母弹 0–100 + 子弹 0–100」**：两段独立偏置相加，支撑范围是 **0–200**、密度峰值在 70–130，
不是 0–100。纯 INI 只有一次抽签，所以只能在两者里选一个：

- `BallisticScatter.Max=200`（本版）：支撑范围与两段相加一致，约一半落点在 100 格内、一半在 100–200；
- `BallisticScatter.Max=100`：8 发全部落在 100 格内，打击区收一半、更容易砸到目标区。

**新守卫**（8 项负向测试全过）：`Burst` 必须字面量 8；`Warhead` 必须是 `ZAINukeMissileWH`（不得是
`NUKE`，也不得退回 3 格小爆）；弹丸**不得**出现任何 airburst/split 键（出现即报错，防止有人把
±3 的旧链加回来）；`FlakScatter` 必须 `no`；`Arcing` 必须 true；`BallisticScatter` 必须字面量 0/100；
不得有 `ROT`/`Arm`；`Secondary` 必须为空。


## 3.13.6 — 集束炮艇定稿：一次 1 颗母弹、正好 8 颗子弹、母弹真的落在 50–100 格外

三条需求逐条落地，其中两条改了机制，第三条查出的是**散布键被引擎按射程缩水**：

| # | 需求 | 旧 | 新 |
| --- | --- | --- | --- |
| 1 | 母弹一次只发一颗 | `Burst=3` | **`Burst=1`** |
| 2 | 每颗母弹正好 8 颗子弹 | `AirburstSpread=3` → 29 颗 | **`Splits=yes` + `Cluster=8`** |
| 3 | 子弹从落点飞 50–100 格再炸 | 母弹实际只散 25–50 格（半程） | **`FlakScatter=no`**，任意距离都散 50–100 格 |

### ① 为什么 8 颗必须走 `Splits=`——`AirburstSpread` 的颗数是格点，不是数字

`sim/combat/airburst.rs::cell_range` 的算法是「以落点为中心的方格，保留欧氏距离 ≤ 半径的格，一格一颗」：

```rust
let half = (radius + 0.99).floor();          // 方格半边
if dx * dx + dy * dy > radius * radius { continue; }   // 只留圆内的格
```

颗数因此只能是**整点格数**：1（0 格）、5（1.0）、9（1.42/1.5）、13（2.0）、21（2.24/2.5）、
29（3.0）、37、45、49……**没有 8，也没有任何半径能凑出 8**。`build_mod.py::airburst_child_count()`
把这个公式实现了一遍，构建期还会跑一遍 0–4 格（1/4 格步长）的半径，确认 8 不在结果里。

`Cluster=` 是引擎里**唯一**能点名颗数的键，而它只在 `Splits=yes` 支路里被读：

```rust
let cluster = if !splits {
    targets = cell_range(world, center, airburst_spread);   // 一格一颗
    targets.len()
} else {
    ... 附近 Techno + ±3 格随机格，补到 kind.cluster ...
    usize::try_from(kind.cluster).unwrap_or(0)              // 正好 Cluster 颗
};
```

所以 8 颗 = `Splits=yes` + `Cluster=8`，不是"换个半径"。

`Splits=` 支路的目标池是：**距分裂中心 1280 雷普顿（5 格）内的 Techno**，然后**±3 格的随机格**，
补满 `Cluster` 个；`RetargetAccuracy=0`（Ares 默认）让每颗子弹从池里取一个**不同**的目标
（写 1 会让 8 颗全扑同一个格）。`RetargetSelf=no` 把炮艇自己排除出池子。

### ② 50–100 格的落点：`FlakScatter=yes` 一直在偷偷缩水

`Inaccurate=yes` + `Arcing=true` 会选中 **flak 散布支路**（`projectile_delivery.rs`：
`launch_scatter_is_flak = inaccurate && arcing` → `flak_scatter && !inviso`），而这条支路的幅度是

```rust
// launch.rs::flak_magnitude
random_ranged(min, max).wrapping_mul(distance).checked_div(weapon_range)
```

即 **按「实际距离 ÷ 武器射程」缩放**。射程 200 格、在 100 格处开火时，50–100 格的抽签只剩
25–50 格。`FlakScatter=no` 会切到普通支路（`launch_scatter_with` 的 `else`），抽签值**原样**使用，
于是任何距离都是 50–100 格。非 `Inviso` 的炸弹没有别的地方用这个键。

### ③ 子弹仍然是从落点飞回瞄准点

`AroundTarget=yes` → `destination = target_get_coords(live.target)`（母弹瞄准的格），
子弹在**母弹落点**生成、朝瞄准点 ±3 格飞；母弹被 `BallisticScatter` 甩到 50–100 格外，
于是这段飞行就是 50–100 格。子弹自己拿不到散布：`spawn_ares_child` 只把目标格交给
`FiredBullet::launched`，全程不读 `BallisticScatter`。

### ④ 真正的"不飞"根因：子子弹第一帧就被埋进地里（`Acceleration` 必须小）

`admit_projectile` 会用 `bullet_unlimbo_coord` 把任何"在地面或地下"的子弹抬到 **地面 + 1 雷普顿**；
而 `homing::track` 的第一步是 `advance(old, velocity, 1)`——**照当前速度直走**，转向在这一步之后才发生。
Ares 分裂给的出膛速度是**竖直向下**的 1 雷普顿/帧，`homing::ramp` 先加 `Acceleration`：

| `Acceleration` | 第一步下沉 | 地形跟随补 18 | 结果 |
| --- | --- | --- | --- |
| **250**（3.13.4/3.13.5） | 251 | -233 | **第二帧 `old_height <= 0` → 在爆点自爆**，一颗子弹都看不到 |
| 10 | 11 | **+7** | 存活，随后按 18/帧爬到离地约 2 格再平飞 |

因此 `Acceleration` 只能是 **1..17**：地形跟随块（`homing::track` 里 `candidate.z += 18`）每帧只抬
18 雷普顿，第一步比它深就会被埋。`Speed=800` 仍是上限，慢慢爬上去就行；`Arm=60`（4 秒）覆盖整段
爬升 + 飞行，近炸引信不会在途中响。

> 这也解释了为什么之前调 `ROT`、`Arm`、`Speed` 都没用：那三项都作用在"子弹已经在飞"之后，
> 而子弹在第二帧就已经没了。

其余保持不变：`ROT=60`（`ROT>0` 才会被重瞄）、`Speed=800`、`Arm=60` + `Proximity=no`、子武器
`Range=0` 且用 `Secondary=` 登记（否则读段太晚，一颗都不出）。

### 构建期守卫（负向测试 9 项全过）

`assert_nuke_gunship3` 新增/改写的硬断言：`Burst` 必须字面量 `1`；`Splits` 必须 `yes`；
`Cluster` 必须字面量 `8`；`FlakScatter` 必须 `no`；`RetargetAccuracy` 必须 `0`；
`RetargetSelf` 必须 `no`；`AirburstSpread` 出现即报错（`Splits=` 下它是死键）；
`AroundTarget` 必须 `yes`；子子弹 `ROT>0`、`Arm≥45`、`Proximity=no`、`Acceleration` 必须落在
**1..17**（新增，越大越致命）、`Speed=800` 不变。
负向用例：`Burst=2` / `Cluster=9` / 删 `Splits` / `FlakScatter=yes` / `RetargetAccuracy=1` /
加回 `AirburstSpread=3` / 删 `AroundTarget` / 子 `ROT=0` / 子 `Arm=2` / 子 `Acceleration=250`，
全部按预期拒绝。

## 3.13.5 — 子弹散布途中免疫引爆；一次 3 颗母弹让落点自己铺开

**你的判断方向对了：子子弹会被"提前引爆"。** 但机制不是"被爆炸波炸掉"，而是它自己的近炸引信：

- `ROT>0` 的子弹**被强制**打开近炸引信（`ranged_fuse = tracks_target || Ranged`），写
  `Proximity=no` 也关不掉；
- 引信只在 **`Arm=` 计时器到期后**才逐帧检查（`projectile.rs`：`arm_timer.expired(...)`）；
- 检查点是**目标格**，只有已经贴近目标（≤2 格）且开始"越过"时才判定爆炸
  （`ranged_fuse_distance_step`）。

所以旧配置（`Arm=2` = 2 帧）等于**出膛 0.13 秒后引信就上线**，子弹在母弹爆点附近就被判掉，
自然"只在母弹范围内炸"。

**改动**：

| 段 | 键 | 旧 → 新 |
| --- | --- | --- |
| `[ZAINukeClusterChildProj]` | `Arm` | `2` → **`45`**（3 秒免疫窗口） |
| `[ZAINukeClusterChildProj]` | `Proximity` | `yes` → **`no`** |
| `[ZAINukeCluster]` | `Burst` | `1` → **`3`**（一次 3 颗母弹，各自散布 50–100 格） |

`Arm=45` 覆盖整段 50–100 格飞行（约 1–2 秒），子弹到达目标格时由 `homing::step` 的**到达判定**
引爆——那条路径与引信无关，所以"免疫"不影响命中。

`Burst=3` 是第二道保险：**落点本身**就铺开 50–100 格。即使某个环节让子弹不飞，屏幕上也不再是
"所有东西堆在一个点"，而是 3 个相隔很远的落点、每个一小爆加一圈核爆。

**新守卫**：子弹丸 `Arm` 必须 ≥30、`Proximity` 必须 `no`、母武器 `Burst` 必须 `3`（字面量）。
负向测试 6 项全过：`Arm=2` / `Proximity=yes` / `Burst=1` / 去掉 `AroundTarget` / `Speed=20` /
`Acceleration=3`。

## 3.13.4 — 子弹终于真的"从母弹落点弹射出去"（两个隐藏机制）

3.13.3 的子弹根本没有离开母弹落点，看到的那团核爆就是它们。两个原因都在引擎里：

**① `ROT>0` 的子子弹出膛速度被归一化成 1 雷普顿/帧。**
`FiredBullet::launched` 对 `rot > 0` 的弹体调 `bullet_fire_homing_velocity`，而它的实现是
`scale_to_speed(v, 1, ..)`（`sim/projectile/launch.rs`）——**只保留方向，速度压成 1**。
真正的速度靠 `homing::ramp` 每帧加 `Acceleration=`（弹丸键，默认 **3**）爬到武器 `Speed=`（= 上限）。
所以 `Speed=20` + 默认 `Acceleration=3` 的子弹等于"80 多秒走 1 格"，视觉上就是"原地爆"。
**修**：子武器 `Speed=800`、子弹丸 `Acceleration=250`（4 帧爬到 800 ≈ 3.1 格/帧 → 50 格约 1.1 秒、
100 格约 2.2 秒）。

**② 分裂中心默认是母弹的落点，不是它瞄准的点。**
`airburst.rs`：`destination = if around_target { 目标点 } else { 落点 }`，而 `AroundTarget=`
（Ares 弹丸键）默认取 `Splits=`（我们没开）= false。所以不管母弹落在哪，子弹都只在**落点周围**炸。
**修**：`[ZAINukeClusterProj] AroundTarget=yes` —— 分裂中心改成"母弹瞄准的那个点"。
配合母弹 `BallisticScatter=50/100`（母弹落在瞄准点外 50–100 格），效果才是：
**母弹落在随机远处 → 那里只有一团 3 格 `MININUKE` 小爆 → 29 颗子弹从那个落点朝瞄准点飞
50–100 格 → 在目标区炸成一片 10 格核爆**。

顺带确认（避免再走弯路）：近炸引信的参考点是**目标格**（`projectile.rs:2147`
`proximity_reference = spawn.initial_target_position`），所以子弹朝目标飞时**不会**被提前引爆；
子弹丸 `Ranged=yes` 的 Ares 射程按**飞行距离**扣（`ProjectileRange` 默认 100000 雷普顿 ≈ 390 格），
飞 50–100 格不会中途引爆。

**新守卫**：`AroundTarget` 必须是 `yes`、子武器 `Speed` 必须是 `800`、子弹丸 `Acceleration` 必须是
`250`（全部字面量比对）。负向测试 4 项全过：去掉 `AroundTarget` / `Speed=20` / 去掉
`Acceleration` / `Acceleration=3`。

## 3.13.3 — 集束炮艇：29 颗子弹、母弹散布 50–100 格、`Sight=200`

按需求把「B 方案」+ 射程 200 + 散布 50–100 落下去：

| 键 | 旧 | 新 |
| --- | --- | --- |
| `AirburstSpread`（`[ZAINukeClusterProj]`） | `2`（13 颗） | **`3`（29 颗）** |
| `BallisticScatter.Min/Max`（母弹） | `50/200` | **`50/100`**（母弹落在瞄准点外 50–100 格） |
| `Sight`（`[ZAINukeGunship3]`） | `20` | **`200`** |

`Range=200` 和 `GuardRange=200` 本来就是 200，但**视野只有 20 格时 200 格射程是摆设**——
玩家单位只打自己看得见的目标，所以这次真正让它能打 200 的是 `Sight`。
副作用：它在 200 格半径内开图（随身全图视野）。不想这样的话把 `Sight` 设成 40。

**「子弹落点散布 50–100 格」为什么改成落在母弹身上**：引擎里子弹落点只能是母弹落点周围
`AirburstSpread` 格内的**地图格，一格一颗**（`airburst.rs::cell_range`）；`Splits=` 支路的随机格
写死 `±3`；而 `spawn_ares_child` **完全不读 `BallisticScatter`**。所以半径 50 格 = 317 颗、
100 格 = 3 万+ 颗，必然卡死。大范围只能由母弹的 `BallisticScatter` 提供。

**新守卫**：母弹 `BallisticScatter` 按字面量钉成 `50/100`（改常量骗不过去）、
`Sight` 必须 ≥ `GuardRange`（"看不见就别说自己能打 200"）、`AirburstSpread` 仍限 1.0–3.0 且派生颗数 ≤ 49。
负向测试 4 项全过：`AirburstSpread=4` / `Sight=20` / `BallisticScatter=50/200` / `.Min=5`。

**性能预警**：29 颗 × 10 格核爆 × `ROF=9` ≈ 每秒 48 次核爆结算 + 48 个 `NUKEANIM`，卡的话降到 `2.5`（21 颗）。

## 3.13.2 — 集束炮艇的真根因：子武器在 Weapon 扫描之后才被分配（一颗子弹都不出的原因）

3.13.0/3.13.1 两次都没打中要害，真因在引擎的**读取顺序**：

- `AirburstWeapon=` 是在 **Bullet 扫描**里解析的（`native_processing/pass_families.rs:337-341`），
  而引擎的 **Weapon 扫描**早已跑完；只被 `AirburstWeapon=` 命名的武器会被"构造但从不读段"：
  `damage=0`、`projectile=None`；
- 引擎自己的测试钉死了这件事：
  `native_processing_tests.rs::airburst_reference_retains_rebinds_and_keeps_native_factory_timing`
  —— `AirburstWeapon=LATE` 时断言 `damage == 0` 且 **`projectile.is_none()`**；
- 于是 `ares_emit` 第一道门就 `return`：
  `let Some(child) = weapon.projectile.as_deref().and_then(|id| rules.projectile(id)) else { return; };`
  → **一颗子子弹都不发**，所以只看到母弹爆炸；
- 零售数据自己就踩过这个坑：`rulesmd.ini:6559`
  `Secondary=V3Cluster ;gs Looks like hack is weapons must be represented once`；
- 只有 TechnoType 武器槽（`pass_techno.rs:973-988`，`Primary`/`Secondary`/`Elite*`）里的武器
  才会在 Weapon 扫描**之前**登记并读取。

**修**：`[ZAINukeGunship3] Secondary=ZAINukeClusterChild`（登记用），子武器补 `Range=0`
（0 格射程让它永远不会被选去开火；空气爆子子弹只读 `Damage`/`Warhead`/`Projectile`/`Speed`，
不读 `Range`，所以对子弹毫无影响）。

**可判定的运行期证据**：启动日志 `RuleSet loaded: ... 42 projectiles` → 修后 **`43 projectiles`**
（`ZAINukeClusterChildProj` 第一次被真正读入规则集）。这次不是"看起来应该行"，是计数变了。

**新守卫**：`assert_nuke_gunship3` 现在要求
①`AirburstWeapon=` 指向的武器**必须被某个 TechnoType 武器槽登记过**（扫描全部段，错误信息引用上面的
引擎测试与零售注释）；②子武器 `Range` 必须为 `0`；③该单位 `Secondary` 必须等于子武器。
负向测试 4 项全过：删掉 `Secondary` / `Secondary` 指错武器 / 子武器 `Range=200` / 子子弹 `ROT=0`。

## 3.13.1 — 集束炮艇：修掉「看不到子弹」的真因；母/子弹头互换；三艘炮艇定价

**为什么看不到子子弹**：不是"没分裂"，是"分裂出来的没飞"。

- Ares 支路给每颗子子弹的出膛速度几乎是**正下方**（`ares_airburst_launch_velocity`：水平分量
  `cos(1.5π·1.00001)` ≈ -2.4e-16，垂直 `-Speed`），注释写明"which **`MoveTo`** takes"——
  原生引擎随后用 `MoveTo` 把它们重新指向目标格；
- VERA 的 `spawn_ares_child` **没有 `MoveTo`**；唯一的重新瞄准在 `FiredBullet::launched`
  里，且**只在 `rot > 0`** 时调 `bullet_fire_homing_velocity`；
- 而 `ProjectileTrajectory::Ballistic` 只做重力积分、**永不重瞄**。

所以 `ROT=0`（弹道 `Arcing`）的子子弹保留"竖直向下"的速度，全部在母弹落点原地炸掉，
正好埋进母弹的 10 格核爆里 —— 看起来一颗子弹都没有。

**修**：子子弹丸改成零售 `[ClusterBits]` 的形状（`Arm=2` + `ROT=60` + `Proximity=yes` +
`Ranged=yes` + `Image=DRAGON`），它才会被重新瞄准、真的飞向自己的格；子武器 `Speed=20`。
追踪弹不会散，所以子子弹丸上的 `Inaccurate`/`FlakScatter`/`BallisticScatter` 一并删掉
（写了也是废键）。

**按需求换弹头**：

| 位置 | 3.13.0 | 3.13.1 |
| --- | --- | --- |
| 母弹 `[ZAINukeCluster]` | `ZAINukeMissileWH`（10 格核爆） | **`ZAINukeWH`**（空中炮艇那套：3 格、`MININUKE`） |
| 子弹 `[ZAINukeClusterChild]` | `ZAINukeClusterChildWH`（2 格、`MININUKE`） | **`ZAINukeMissileWH`**（核弹炮艇那套：`CellSpread=10`、`NUKEANIM`） |

两者都不是字面 `NUKE`，所以仍然不闪白、不动全局光照。删掉不再引用的 `[ZAINukeClusterChildWH]`。

**三艘炮艇的 `Cost`**：`ZAINukeGunship`（核弹炮艇）**1000000**、`ZAINukeGunship2`（空中炮艇）
**100000**、`ZAINukeGunship3`（集束炮艇）**10000000**。本模组 `[General] BuildSpeed=.025` 是
全局的，建造时间 ≈ `Cost × .025 × .9` 帧 → 150 秒 / 25 分钟 / ~4.2 小时，所以这三档价格实际
等于"只能靠投放超武拿"；投放超武不看 `Cost=`。`Points=`（击杀得分）仍是 100，未动。

**新守卫**（`assert_nuke_gunship3`）：子子弹丸 `ROT` 必须 `>0` 且不得 `Arcing`（把这次的 bug
变成构建失败）、母弹弹头必须是 `ZAINukeWH`、子弹弹头必须是 `ZAINukeMissileWH`、两者都不得是
字面 `NUKE`、三个 `Cost` 用**字面量**精确比对（比对常量的话，改常量会"自己对自己"通过）。
负向测试 13 项全过：去掉 `ROT` / 改成 `Arcing` / 子弹 `Warhead=NUKE` / 母弹 `Warhead=NUKE` /
三个价格各写错 / 子弹再带 `Airburst` 或 `ShrapnelCount` / `AirburstSpread=9` /
`AirburstWeapon` 指向不存在 / `Splits=yes` / `Cluster=`。

## 3.13.0 — 第四个超武「集束炮艇」：`Airburst=` 子母弹

目标：一艘"一发一发往外随机丢母弹、母弹落地又随机抛射子弹"的炮艇 —— 射速照空中炮艇、爆炸照
核弹炮艇，再加子母弹。

**先钉死三个引擎事实**（查的是 VERA20k 0.4.1 源码，不是教程）：

1. `Airburst=yes` 是**弹丸**键，零售 `[V3AirburstP]` 就在用（`Airburst=yes` + `AirburstWeapon=V3Cluster`
   + `Cluster=9`）。边界手册里"它是 VoxelAnim 键、挂弹丸无效"那条**是错的**：真正的失败原因是
   **没配 `AirburstWeapon=`** —— 缺它引擎整段直接 return（`sim/combat/airburst.rs`）。
2. 不带 `Splits=` 时 **`Cluster=` 根本不读**：子弹数 = 命中格周围 `AirburstSpread=` 格内的**地图格数**
   （一格一颗，`floor(r+0.99)*2+1` 方格内、欧氏距离 ≤ r）。`Cluster=` 只在 `Splits=yes` 支路里数，
   而那条支路把子弹全压在 ±3 格内，做不到"大范围"。半径-数量对照：
   1.0→5、1.5→9、2.0→13、2.5→21、3.0→29、3.5→37、4.0→49、4.5→69、5.0→81。
3. 引擎对 `AirburstSpread` **没有**上限（只有 `Cluster`/`ShrapnelCount` 限 256），所以由构建期断言兜底。

**新内容**：单位 `ZAINukeGunship3`（`[VehicleTypes]` 末尾 87，基洛夫机体、战车工厂可造）+ 玩家投放超武
`ZAINukeGunship3Drop`（`[SuperWeaponTypes]` 末尾 16，按钮「集束炮艇」）+ 5 个新段：

| 段 | 作用 |
| --- | --- |
| `ZAINukeCluster`（武器） | `ROF=9`、`Burst=1`、`Range=200`、`Warhead=ZAINukeMissileWH`（10 格核弹克隆） |
| `ZAINukeClusterProj`（母弹丸） | `BallisticScatter.Min/Max=50/200` 乱丢 + `Airburst=yes` + `AirburstWeapon=ZAINukeClusterChild` + `AirburstSpread=2` |
| `ZAINukeClusterChild`（子武器） | 只提供 `Damage=200` / `Warhead` / `Projectile` / `Speed`（子弹只读这几项） |
| `ZAINukeClusterChildProj`（子弹丸） | 在指定格上再叠 `BallisticScatter.Min/Max=4/10` 的二次散布，**不带任何分裂键** |
| `ZAINukeClusterChildWH`（子弹头） | `CellSpread=2`、`MININUKE`、`Bright=yes`（局部爆光，不是核弹闪白） |

单发 = 1 颗 10 格母弹 + **13 颗** 2 格子弹，节奏 0.6 秒；`≈22 颗子弹出膛/秒`。
界面名走 3.12.0 的机制：`ares.csf` 增加 `Name:ZAINukeGunship3Drop=集束炮艇`。

**两道防回归**：

- **防递归**：子弹丸不许有 `Airburst` / `Splits` / `ShrapnelCount` / `SpawnsNumber`（否则一炮变指数级）；
- **防闪白**：母弹与子弹都**不用**零售 `[NUKE]` 这个名字（母用 `ZAINukeMissileWH`，子用
  `ZAINukeClusterChildWH`），否则每颗子弹都会触发核弹特判（闪白 + 全图光照重算）。

`assert_nuke_gunship3` 检查：单位可造/不被瞄/`GuardRange==Range==200`、武器节奏与弹头、
母弹丸 `Airburst=yes` 且 `AirburstWeapon` 指向**存在且带 Projectile/Warhead 的武器**、
`AirburstSpread` 在 `1.0..3.0` 且派生子弹数 ≤ 49、**不得有 `Splits=yes`**、不得写 `Cluster=`、
母弹 `Inaccurate`/`AG`/二次散布、子弹无分裂键、子弹头 `MININUKE`+`CellSpread 1..3`、
三条投放超武都 `Type/Deliver.Types/AllowAI/AlwaysGranted/RechargeTime` 正确且界面标签互不相同。

负向测试 6 项全过（改回 `Warhead=NUKE` / `AirburstSpread=9` / 给子弹加 `Airburst` /
`AirburstWeapon` 指向不存在的段 / 加 `Splits=yes` / 加 `Cluster=15`）。
零售 `[NUKE]`、`[V3AirburstP]`、`[V3Cluster]` 一行未动（构建期零售守卫 + 独立复核）。

## 3.12.0 — 三个核弹超武分名；第二个飞艇 200 索敌；去掉核弹落点的全局光照

**为什么三个按钮都叫「核弹攻击」**：`UIName=` 是 **CSF 标签**而不是文字。两个投放超武都写着
`UIName=Name:Nuke`，于是和零售核弹共用同一行中文；`Name=` 只是内部名，游戏不显示它。
反过来，写一个 CSF 里没有的标签，游戏会**照字面**画 `MISSING:'NAME:…'`（引擎
`CsfFile::text` 的返回值就是这样，它自己的单元测试钉住了这一点）。所以"改显示名" =
**提供新的 CSF 行**。

- **新机制：模组自带 `ares.csf`。** Ares 表单下引擎在 `ra2md.csf` 之后依次追加
  `ares.csf`（**与语言无关**）、`ares_<语言>.csf`、`stringtableNN.csf`，后加载的同名标签
  覆盖先前的；启动日志会打 `Loaded CSF string table: ra2md.csf; supplements=["ares.csf"]`。
  本项目用**通用** `ares.csf` 而不是 `ares_ch.csf`：带语言后缀的表只有在语言 dword 与基表
  一致时才被接纳，不一致就**静默丢弃**；通用表在任何界面语言下都生效（本地是中文界面）。
- 新增 `tools/csf.py`（CSF 写/读，格式与引擎自己的测试夹具 `build_test_csf` 一致），
  由 `build_mod.py` 生成两张表：
  `Name:ZAINukeGunshipDrop=核弹炮艇`、`Name:ZAINukeGunship2Drop=空中炮艇`。
- **黑名单一笔**：Ares 的 `NOSTR:` 前缀（把 `UIName=` 写成内联文字）在 VERA20k 里**没有实现**
  —— 引擎代码里没有任何 `NOSTR` 解析，Ares 的 `Misc/CSFLoader.cpp` 钩子在
  `docs/ares-remaining.md` 里标为 Deferred，CSF 加载是 VERA 自己的一套。写了只会让
  `NOSTR:…` 整个字符串被当成一个查不到的标签。
- **第二个飞艇索敌 20 → 200**（`GuardRange` 与武器 `Range` 一起改；只改一个会变成"追着打不到
  的目标转"，构建期断言 `guard == reach` 防的就是这个）。
- **第二个飞艇的弹头换名**：`Warhead=NUKE` → 新段 `ZAINukeMissileWH`（零售 `[NUKE]`
  的 9 个键一字不改）。原因：引擎的核弹特判不看"是不是核弹"，只看
  **`strcmpi(warhead, "NUKE")`** —— 命中时闪白屏 + 把整张地图的光照重算一遍 + 打雷达事件 +
  等 `NUKEBALL` 动画才真正引爆。换成本段后这些都不发生，只剩
  `AnimList=NUKEANIM`（artmd 注释原文 "nuke mushroom cloud explosion"）的蘑菇云，
  `Burst=8` 一梭子不再闪 8 次；伤害与爆炸半径仍与零售核弹一致。
- 构建期守卫：`assert_nuke_warhead_clone`（克隆段必须与零售 `[NUKE]` 逐键相同、且不多键）、
  `assert_ui_labels`（两条标签必须在 `ares.csf` 里；模组自建段的 `UIName` 不得指向查不到的
  标签）、`assert_unit_delivery`（两个投放超武的 `UIName` 必须互不相同且不是 `Name:Nuke`）、
  `assert_nuke_gunship`（`Range == GuardRange == 200`、弹头不得叫 `NUKE`）。
- `tools/check.py` 增加 `sidebar names` 一项：比对**已安装**的 `ares.csf` 与仓库里的一致。
- 零售 `[NUKE]`、`[NukeSpecial]`、`NukePayload`、电脑的核弹、`#1` 无限核弹：**一行未动**。

## 3.11.6 — 还原 `[NASAM]` / `[NAFLAK]`：不再给防空建筑加地面分数

3.10.x 为了让 AI 会造防空，把爱国者/高射炮改成 `AntiInfantryValue=25 / AntiArmorValue=10`。
查清 AI 的选法后确认这是个 hack：

- 威胁按**造价**算（敌方三类单位的 `Cost_Of` 之和，各 +3000 底盘、再按
  `AIForcePredictionFudge` 浮动，取份额）；
- AI **先选类别**（air/armor/infantry，取"敌方份额 − 自己最弱象限覆盖份额"的最大者），
  **再**在 `[AI] *BaseDefenses=` 里按"该类别值 > 0"过滤、按值加权随机；
- 零售 `0/0/25` 让它们只在 air 类别里可选；加地面分数只是让 AI 拿**打不到地面**的楼
  去应付地面威胁。

本次还原为零售 `0/0/25`，并改写守卫：
`assert_aa_defenses_competitive` 现在只要求 `AntiAirValue > 0`，
同时**锁死地面值必须等于零售**（NASAM/NAFLAK = 0/0，YAGGUN = 25/10），防止这个 hack 再被加回来。

`check_retail` 白名单同步收回：值改动从 **22 键/7 段** 降到 **18 键/5 段**。
代价：AI 的防空数量会回落到零售水平（air 类别很少胜出），这是引擎行为而非配置问题。

## 3.11.5 — 明确定义「原版」= 官方零售数据，并把规则做成构建期强制检查

**定义**（写进手册 §0.0）：

> 原版 = 官方《红色警戒2：尤里的复仇》的零售数据（`F:\Games\red2\rulesmd.ini` 等），
> **不是**我们 mod 的上一版，**也不是**我们自己新增的 `ZAI*` 条目。

三条推论：① 我们自己的 `ZAI*` 段/追加行/追加键可以随意改删（属 mod 自有内容）；
② 只有"零售段已有键被改值/删除"才算改原版；③ 自检要比**零售 vs 构建产物**，不是 `git diff`。

新增 `tools/check_retail.py` 并**接进构建**：

- 白名单：`RETAIL_VALUE_EDITS`（22 个键 / 7 个段）+ `RETAIL_KEY_ADDITIONS`
  （67 个键 / 21 个段）+ 注册表末尾追加（`VehicleTypes` 85/86、`SuperWeaponTypes` 13/14/15）；
- 任何白名单外的"零售键改值/删除/新增"→ **构建失败并点名**；
- 自测：正常构建输出
  `retail diff OK: 22 allowed value edits, 67 allowed key additions, 10 new sections, 0 removals`；
  把 `[ZEP] Strength=2000` 改成 9999 → 立即报 `ZEP: retail key 'strength' was changed`。

## 3.11.4 — 总原则入库：默认「只增不改」+ 原版改动登记表

在边界手册里补上最高优先级的一条：

> **除非明确点名要改某个原版单位/行为，否则一律新建条目，原版段一行都不动。**

配了 5 条可执行细则（必须新建的对象、允许追加禁止改动、用引用代替修改、
确需改原版时的四件事、提交前自检），以及：

- **原版改动登记表**：当前只有 7 个段被改值（`[General]`/`[AI]` 的 AI 调优、
  `[NASAM]`/`[NAFLAK]`/三个 `*DEPT` 的单位数值），12 个段只**追加**键，
  三张列表只在**末尾**追加（85/86、13/14/15）；
- **"新增 or 修改"判定流程图**，把"停下来问"这一步写进流程。

## 3.11.3 — 武器级散布验收通过 + 新增边界手册

**验收结论（你实测）**：弹丸段里的 `BallisticScatter.Min=50` / `BallisticScatter.Max=200`
**确实生效** —— 第二艘飞艇的弹道弹大范围散开，而 `[CombatDamage]` 仍是零售 `1.0`、
零售高炮弹丸也保持原样。也就是说**散布可以做到武器专属，公共表零改动**。

新增 **[`docs/boundaries-and-lessons.md`](docs/boundaries-and-lessons.md)**：

- 动手前必答的三个问题（属于哪一级 / 验证信号 / 回滚方式）；
- 已确认可复用的正确路径（专属超武、`UnitDelivery`、`Image=` 写 rules、弹丸级散布、
  无畏弹头克隆、自动开火三键、基洛夫机体）；
- 黑名单（`ParaDrop.Types`、改 `*ParaDropInf`、`DropPod.Types`、`SpyPlane.*`、
  `MultiMissile` 散射、`Battery`、`PlaceUnits`、artmd 写 `Image=`、按单位拆 `[CombatDamage]`、
  `Airburst` 挂弹丸、`RechargeTime=0`、追踪弹靠 `HomingScatter`）；
- 方法论（先查二进制字段表归类 → 单变量 → 静默失败变断言 → 改公共表前列使用者 → 错了整体回滚）；
- 今日版本轨迹，方便回溯。

文档同步：playbook 里"`BallisticScatter.Min/Max` 未证实"改为"实测生效"，
§18.1 的"散布会比当时小"替换为武器专属散布的结论。

## 3.11.2 — 试「武器级」散布：把 BallisticScatter.Min/Max 写进弹丸段（公共表回零售）

先纠正一个常见误解（我按二进制字段表逐条核对）：

- `Inaccurate` / `FlakScatter` 确实是**抛射体**键，但只是**开关**，不提供半径；
- **半径**只在 `[CombatDamage] BallisticScatter`（全局，单位格）；
- `Airburst` 是 **VoxelAnimType** 的键（和 `AnimLow/AnimHigh/Degenerates` 同列），**不是**抛射体键；
- `Cluster` / `ShrapnelCount` 确实在抛射体字段表里。

本版做一次**武器级**散布实验，并把公共表全部还原：

- `[CombatDamage] BallisticScatter` 回 **1.0**、`HomingScatter` 回 2.0；
- 零售 `[FlakProj]`/`[FlakTProj]` 恢复 `FlakScatter=yes`/`Inaccurate=yes`；
- 只在 `[ZAINukeRifleProj]` 里加 `BallisticScatter.Min=50` / `BallisticScatter.Max=200`。

守卫：公共表回到"必须等于零售值"的严格检查；`[ZAINukeRifleProj]` 必须带这两个键（≥50）。

若实测无效（落点仍聚在一起），说明 VERA 只认全局值，下一版回到
"全局 200 + 关掉零售高炮散布"的受控方案（3.11.1 的做法，效果等价）。

## 3.11.1 — 第二艘飞艇的散布：走 `[CombatDamage]`（全局唯一段）+ 关掉零售高炮的散布

`[CombatDamage]` **没有"按单位一份"这种东西** —— 引擎只读一个全局段。所以：

```ini
[CombatDamage]
BallisticScatter=200     ; 全局散布半径（格）

[FlakProj]  FlakScatter=no  Inaccurate=no     ; 零售高炮弹丸：关掉散布
[FlakTProj] FlakScatter=no  Inaccurate=no
```

效果：只有第二艘飞艇的弹道弹撒 200 格，AI 的高射炮恢复精确、不会跟着乱撒。
`[ZAINukeWH]` 上的弹头级 `BallisticScatter=200` 保留，两道保险。

守卫把这条固化成"受控例外"：`BallisticScatter>=100` **且**两枚高炮弹丸已关散布，
缺一即构建失败（实测 `BallisticScatter=1.0`、`FlakScatter=yes` 都会被拦）。

## 3.11.0 — 两艘核弹飞艇：短程版 + 复用「核弹火箭飞行兵」武器版

**边界（都已核对）**：两艘都是**全局、打包进 mod** 的新类型（`rulesmd.ini` 的
`[VehicleTypes] 85/86` + `Image=ZEP`），**不涉及任何地图数据**；玩家侧靠
`SW.AlwaysGranted=yes` + `SW.AllowAI=no` 的 `UnitDelivery` 超武拿到（电脑拿不到），
同时保留战车工厂建造。

| | `ZAINukeGunship` | `ZAINukeGunship2` |
| --- | --- | --- |
| 武器 | `ZAINukeMissile`（追踪弹、`Burst=8`、`Warhead=NUKE`） | `ZAINukeRifle`（**原核弹火箭飞行兵**武器） |
| 射程 | **20**（`GuardRange` 同步 20） | 200（沿用飞行兵原值） |
| 弹丸 | `ZAINukeMissileProj`（AA+AG 追踪） | `ZAINukeRifleProj`（弹道弹，`Arcing`+`Inaccurate`+`FlakScatter`） |
| 弹头 | `[NUKE]`（未改） | `ZAINukeWH`（3 星无畏 `[DMISLEWH]` 克隆：`CellSpread=3`、`MININUKE`） |

- 新增 `[VehicleTypes] 86=ZAINukeGunship2`、`[SuperWeaponTypes] 15=ZAINukeGunship2Drop`；
- 飞行兵素材按 **3.10.6 最终版**原样恢复（`[ZAINukeRifle]`/`[ZAINukeRifleProj]`/`[ZAINukeWH]`），
  但当时依赖的全局 `[CombatDamage] BallisticScatter=200` 仍保持撤回，散布只来自
  弹丸与弹头级设置，因此会比当时小；
- 守卫新增 `assert_nuke_gunship2`（武器/弹丸/弹头/血量/不进 TaskForce/不进超武注册表），
  并把第一艘的断言改为 `Range==20` 且 `GuardRange==Range`。

## 3.10.12 — 飞艇隐形的原因：`Image=` 要写在 rules 里，不是 art 里

3.10.11 在 `artmd.ini` 里新建了 `[ZAINukeGunship] Image=ZEP`，实测**仍然隐形** ——
引擎是按**对象 ID** 去找 `ZAINukeGunship.vxl` 的，art 段里的 `Image=` 不参与这个查找。

正确做法是把 `Image=ZEP` 写在 **`rulesmd.ini`** 的对象段（零售同款用法：
`[JUMPJET] Image=ROCK`）：

```ini
[ZAINukeGunship]
Image=ZEP      ; 借用 [ZEP] 的 art/voxel
```

- 删掉 `build_mod.py` 里写 art 段的那套逻辑（含 `assert_unit_art`）；
- `assert_nuke_gunship` 改为断言 rules 段里 `Image=ZEP`（缺了会隐形，必须拦）。

## 3.10.11 — 投放定案 + 给飞艇补模型（之前是隐形的）

- **确认**：`Type=UnitDelivery` + **`Deliver.Types`** 生效（点地面即投下飞艇）；
  `Type=PlaceUnits` 无效，已删除（注册表回到 14 项）；
- **隐形的原因**：只加了 rules 的 `[ZAINukeGunship]`，但图形是按 ID 去 `artmd.ini` 查的，
  没有 art 段 → 单位存在但看不见。补上：

  ```ini
  [ZAINukeGunship] ; SuperAI nuclear gunship
  Image=ZEP  Cameo=ZEPICON  AltCameo=ZEPUICO  Voxel=yes  PrimaryFireFLH=-50,0,-140
  ```

  复用基洛夫的模型与图标，不需要新素材；`PrimaryFireFLH` 让导弹从艇体正确位置射出；
- `build_mod.py` 现在会在复制 `artmd.ini` 后追加该段，并断言它存在（`Image=ZEP`）。

守卫新增：art 段必须存在且 `Image=ZEP`；注册表里不得残留 `ZAINukeGunshipDrop2`。

## 3.10.10 — 载荷键改为 `Deliver.Types`

`UnitDelivery.Types` / `UnitDelivery.Num` 是错的（引擎读的是 `Deliver.Types`），
写错时点击**毫无反应**。同步把两种候选 Type（`UnitDelivery` / `PlaceUnits`）各做一个按钮
用于一次试出真名 —— 结论是同文件 3.10.11：只有 `UnitDelivery` 有效。

## 3.10.9 — 用 `UnitDelivery` 超武投放核弹飞艇（玩家专属）

查二进制发现 VERA **真的实现了** `UnitDelivery`（`src/sim/superweapon/unit_delivery.rs`、
`UnitDeliveryRules`、`DeliveryOwner`），这是之前漏掉的一条正路。

```ini
[SuperWeaponTypes] 14=ZAINukeGunshipDrop
[ZAINukeGunshipDrop]
Type=UnitDelivery   Action=Nuke
RechargeTime=0.01   SW.Shots=1000
SW.AllowPlayer=yes  SW.AllowAI=no  SW.AlwaysGranted=yes
SW.InitialReady=yes SW.RequiresTarget=yes SW.FireIntoShroud=yes
UnitDelivery.Types=ZAINukeGunship   UnitDelivery.Num=1
```

- 投的是**我们自建的** `ZAINukeGunship`，不碰 `[General] *ParaDropInf` 等公共表；
- `SW.AllowAI=no` + 该机型不在任何 `TaskForce` → 电脑拿不到；
- 顺带发现 `SW.InitialReady`、`SW.RequiredHouses`/`SW.ForbiddenHouses` 三个可用键。

新增 `assert_unit_delivery`，并含"公共表零改动"抽查；实测 `AllowAI=yes`、
`Type=ParaDrop`、`UnitDelivery.Types=E1` 均被拦。
另修构建脚本真 bug：`build_rules` 被重复定义两份（前一份死代码），已删除。

## 3.10.8 — 撤回所有公共表改动（空投方案作废）

做"专属核弹兵空投"时改了 `[General]` 的四张阵营空投表，导致**电脑也开始投核弹兵** ——
这四张表玩家与电脑共用。按要求整体撤回：

- `AmerParaDropInf/AllyParaDropInf/SovParaDropInf/YuriParaDropInf` 及 `*ParaDropNum`
  回到零售值（`E1/8`、`E1/6`、`E2/9`、`INIT/6`）；
- `[ParaDropSpecial]` / `[AmericanParaDropSpecial]` 去掉 `SW.AllowAI=no`；
- `[CombatDamage] BallisticScatter/HomingScatter` 回到 `1.0` / `2.0`；
- `[FlakProj]` / `[FlakTProj]` 恢复 `FlakScatter=yes`、`Inaccurate=yes`；
- 删除 `ZAIWorldNuke`/`ZAINukeTrooper`/`ZAINukeRifle`/`ZAINukeRifleProj`/`ZAINukeWH`。

保留：`ZAIUnlimitedNuke`（玩家无限核弹）、`ZAINukeGunship`（核弹飞艇）。
另附 `docs/prompt-for-gemini.md`。

## 3.10.7 — 曾试图用 SW.AllowAI=no 关掉电脑空投（已被 3.10.8 撤回）

那一版给 `[ParaDropSpecial]`/`[AmericanParaDropSpecial]` 加了 `SW.AllowAI=no`，
等于改动了 AI 的空投能力，属于越权，3.10.8 已整体回滚。

## 3.10.6 — 更正：3 星无畏用的是 `[DMISLEWH]`（3 格 + `MININUKE` 小蘑菇云）

3.10.5 我拿错了弹头 —— 无畏导弹在零售里有**两个**：

| 弹头 | `CellSpread` | `AnimList` | 用于 |
| --- | --- | --- | --- |
| `[DMISLWH]` | 1.5 | `XGRYSML1,...,TWLT070` | 普通无畏 |
| `[DMISLEWH]` | **3** | **`MININUKE`**（小蘑菇云） | **3 星无敌** |

- `[ZAINukeWH]` 改为 `[DMISLEWH]` 的克隆：`CellSpread=3`、`PercentAtMax=.5`、
  `AnimList=MININUKE`，其余（`Wall/Wood/Verses/Conventional/InfDeath/ProneDamage`）同无畏；
- 伤害仍 600 = `[General] DMislEliteDamage`；`BallisticScatter=200` 保留；
- `[NUKE]` 依旧未改动。

命名规律记进 playbook：**精英版 = 同名 + `E`**。
守卫改为 `CellSpread` 必须在 2.5–4、`AnimList` 必须含 `MININUKE` 且不得是 `NUKEANIM`
（`CellSpread=1.5`、`XGRY` 列表、`NUKEANIM` 三种退化实测全部被拦）。

## 3.10.5 — 弹头换成 3 星无畏导弹（范围/特效/伤害）

原核弹头 `CellSpread=10` + `NUKEANIM` 太大、没意思。换成零售无畏导弹的弹头：

| | `[NUKE]` | `[DMislWH]`（无畏） |
| --- | --- | --- |
| `CellSpread` | 10 | **1.5** |
| `PercentAtMax` | .02 | .25 |
| 拆墙 | `WallAbsoluteDestroyer=yes` | 无 |
| 特效 | `NUKEANIM` | `XGRYSML1,XGRYSML2,EXPLOSML,...` |
| 3 星伤害 | — | `[General] DMislEliteDamage=600` |

- `[ZAINukeWH]` 改为 `[DMislWH]` 的克隆（范围/`Verses`/特效/`Deform` 全同无畏），
  保留弹头级 `BallisticScatter=200`；
- 武器 `Damage=600` 正好等于 3 星无畏（`DMislEliteDamage=600`）；
- `[NUKE]` 依旧未改动。

守卫新增：`[ZAINukeWH] CellSpread` 在 (0,2] 内、不得有 `WallAbsoluteDestroyer`、
`AnimList` 不得含 `NUKEANIM`、`BallisticScatter>=100`、武器 `Damage<=600`；
实测 `CellSpread=10`、`AnimList=NUKEANIM`、`BallisticScatter=0` 全被拦。

## 3.10.4 — 核弹兵改单发，射速对齐 3 星神盾

射速换算（记进 playbook）：

```
3 星间隔 = 武器 ROF × [General] VeteranROF
神盾 [Medusa] ROF=15 × 0.6 = 9 帧  （15 帧/秒 → 约 1.7 发/秒）
```

- `[ZAINukeRifle]`：`ROF` 80 → **9**，`Burst` 2 → **1**（单发）；
- 弹丸/弹头/散布全部不变（`Arcing=true`、`FlakScatter=yes`、`Inaccurate=yes`、
  `[CombatDamage] BallisticScatter=200`、`Warhead=ZAINukeWH`）。

守卫改成：`Burst == 1`、`1 <= ROF <= 15`（不许退回慢节奏，也不许 0）；
实测 `Burst=2`、`ROF=80`、`ROF=0` 全部被拦。

## 3.10.3 — 弹丸改成高炮式弹道弹，散布才真的生效

实测发现：**追踪弹永远不会撒** —— `FlakScatter` 只对非追踪弹生效，追踪弹最后一定咬住目标点，
所以 `HomingScatter=200` 也照样精确命中。

- `[ZAINukeRifleProj]` 改成参照零售 `[FlakTProj]` 的弹道弹：`Arcing=true`、`Ranged=yes`、
  `Inaccurate=yes`、`FlakScatter=yes`、`AA=yes/AG=yes`，**去掉 `Arm`/`ROT`**（追踪会抵消散布）；
- `[CombatDamage] BallisticScatter` 1.0 → **200**（格），`HomingScatter` 保持 200；
- 为不让 AI 高炮一起乱撒，把零售 `[FlakProj]`/`[FlakTProj]` 的 `FlakScatter`/`Inaccurate` 改为 `no`
  （它们只是变准，不会变弱）；
- 新增 `[ZAINukeWH]`（`[NUKE]` 克隆 + 弹头级 `BallisticScatter=200`），武器 `Warhead=ZAINukeWH`，
  `[NUKE]` 本身仍未被改动；
- 顺带修掉构建脚本的一个真 bug：**段头带注释**（`[FlakProj]	; ...`）时正则匹配不到，
  导致改不到这些段 —— 现在段头正则允许尾随注释。

守卫新增：`BallisticScatter>=100`、零售高炮弹丸必须 `FlakScatter=no`+`Inaccurate=no`、
弹丸不得有 `Arm`/`ROT`、武器必须用 `[ZAINukeWH]`；三种退化实测被拦。

## 3.10.2 — 散布拉满：`[CombatDamage] HomingScatter=200`（格）

零售注释写明了这两个键的位置和单位：

```ini
[CombatDamage]
BallisticScatter=1.0 ; maximum scatter distance (cells) for inaccurate ballistic projectiles
HomingScatter=2.0    ; maximum scatter distance (cells) for inaccurate homing projectiles
```

- **单位是格**；追踪弹看 `HomingScatter`，弹道弹（AI 高射炮）看 `BallisticScatter`；
- **`Inaccurate=yes` 是弹丸键**（零售写在 `[FlakProj]`/`[FlakTProj]`），
  之前写在武器上等于没生效 —— 这是"散不开"的真正原因。

改动：

- `[CombatDamage] HomingScatter=200`（0→200 格随机落点）、`BallisticScatter=1.0` 保持不动
  （否则 AI 高射炮会全部打空）；
- `Inaccurate=yes` 从 `[ZAINukeRifle]` 挪到 `[ZAINukeRifleProj]`；
- 配合原有的 `ROT=10`（慢转向）与 `FlakScatter=yes`，落点遍布全图。

守卫新增：`HomingScatter>=100`、`BallisticScatter` 必须仍是 1.0、弹丸必须 `Inaccurate=yes`、
武器上不得再出现 `Inaccurate`；实测三种退化全部被拦。

⚠️ 散布 200 格会砸到自己人（含自家基地），这是"最大散布"的必然结果；
想收一点把 `HomingScatter` 调到 60–80 即可。

## 3.10.1 — 空投机加固、核弹兵改天启导弹、弹道随机

- **运输机加固**：`[PDPLANE]` 零售 `Strength=400/Armor=light` → `100000/heavy` +
  `Insignificant=yes`（防空不再瞄它），空投不会半路被打下来；
- **核弹兵加固**：`[ZAINukeTrooper] Strength` 5000 → `100000`；
- **武器换天启导弹**：`[ZAINukeRifle]` 克隆天启副武器 `[MammothTusk]` ——
  `ROF=80`（火箭飞行兵 20mm 的 ROF 30 太快）、`Burst=2`、`Range=200`、`Speed=20`；
- **布朗弹道/随机落点**：`[Weapon] Inaccurate=yes`（不吸附目标点）+
  `[Projectile] FlakScatter=yes`（落点随机）+ `ROT=10`（慢转向、一路歪）；
- **坑**：天启自己的弹丸 `[AAHeatSeeker]` 是 `AA=yes/AG=no`，打不了地面，
  所以 `[ZAINukeRifleProj]` 克隆 `[AAHeatSeeker2]`（`AA+AG`），只保留 `DRAGON` 外观。

守卫新增：`[PDPLANE] Strength>=10000` + `Insignificant=yes`、核弹兵 `Strength>=10000`、
`ROF>=60`、`Inaccurate=yes`、弹丸 `FlakScatter=yes` + `AG=yes`；
实测 7 种退化（ROF=30、Inaccurate=no、FlakScatter=no、AG=no、飞机 400、飞机 Insignificant=no、
兵 125）全部被拦。

## 3.10.0 — 空投定论：只有按阵营的步兵列表生效，改投「核弹兵」

三次实测：

| 做法 | 结果 |
| --- | --- |
| `ParaDrop.Types=<载具>` | 投出**普通伞兵**（回退 `AllyParaDropInf=E1`） |
| `Type=DropPod` + `DropPod.Types` | **毫无反应** |
| 改 `*ParaDropInf` 四个列表 | ✅ 生效 |

VERA 的 paradrop 只有 `GeneralTypeLists { paradrop_infantry: [Vec<String>; 4] }`，
即四个按阵营的**步兵**列表。所以交付物改成步兵：

- `[InfantryTypes] 66=ZAINukeTrooper`，克隆 `[JUMPJET]` 火箭飞行兵：
  `JumpJet=yes`、`BalloonHover=yes`、`Strength=5000`、`GuardRange=200`、`CanPassiveAquire=yes`；
- `[ZAINukeRifle]`：`Damage=600 / ROF=30 / Range=200 / Burst=8 / OmniFire=yes / Warhead=NUKE`；
- `[General]` 四个 `*ParaDropInf=ZAINukeTrooper`、`*ParaDropNum=1`；
- 超武回到 `Type=ParaDrop`（唯一实测会真的投下来的类型）。

`ParaDrop.*` / `DropPod.*` 失败尝试的键每次构建自动清除，守卫会拦残留。
守卫新增：四个 `*ParaDropInf` 必须指向核弹兵、核弹兵必须 `JumpJet=yes`、
`ZAINukeRifle Warhead=NUKE`、`[InfantryTypes]` 已注册；实测 `AllyParaDropInf=E1`、
`JumpJet=no`、`Warhead=SAMWH` 全被拦。

## 3.9.9 — 空投实测：`ParaDrop.Types` 不生效，改走 `DropPod`

3.9.7 的 `[General] ParaDrop.Aircraft/Types/Num` 实测**投出来的是普通伞兵**（盟军 `E1`），
而且运输机是零售 `PDPLANE`，被防空打掉。

原因：VERA 的 paradrop 只保留**按阵营的步兵列表**
（`GeneralTypeLists { paradrop_infantry: [...] }`，键 `*ParaDropInf`），`ParaDrop.Types` 未被使用。

改走 `Type=DropPod`（类型表里有 `DropPod`、有 `sim/superweapon/drop_pod.rs` 实现、
有 `AresDropPodRules` 结构体、有 `[General] DropPod.Types` 键，零售本身也有
`DropPodWeapon/Height/Speed/Angle` 配置）：

```ini
[General] DropPod.Types=ZAINukeGunship   MinimumDropPod=1   MaximumDropPod=1
[ZAIWorldNuke] Type=DropPod  Action=DropPod  RechargeTime=0.01
               SW.AlwaysGranted=yes  SW.AllowAI=no  SW.RequiresTarget=yes
```

**不再有运输机** → 被防空打掉的问题消失。`ParaDrop.*` 必须删干净，守卫会检查残留。

## 3.9.8 — 飞艇自动开火、200 格射程、依次连投

之前只改武器 `Range` 是不够的 —— 二进制里这几个键各管一段：

| 键 | 位置 | 管什么 |
| --- | --- | --- |
| `GuardRange=` | 单位 | **待机时自动索敌的半径**（真正的自动开火距离） |
| `CanPassiveAquire=` / `OpportunityFire=` / `CanRetaliate=` | 单位 | 主动索敌 / 边飞边打 / 还手 |
| `Range=` / `Burst=` / `OmniFire=` | 武器 | 射程 / 一次连发 N 发（逐发投出）/ 任意角度开火 |

- `[ZAINukeGunship]`：`GuardRange=200`、`OpportunityFire=yes`、`CanPassiveAquire=yes`、
  `CanRetaliate=yes`、`Ammo=200`；
- `[ZAINukeMissile]`：`Range=200`、`Burst=8`、`OmniFire=yes`、`ROF=40`、`Warhead=NUKE`。

守卫新增：`Range>=100`、`Burst>=2`、`OmniFire=yes`、`GuardRange>=100`、
`CanPassiveAquire=yes`、`OpportunityFire=yes`；实测 `Range=20`、`Burst=1`、`GuardRange=12`、
`CanPassiveAquire=no`、`OpportunityFire=no` 全部被拦。

## 3.9.7 — 空投投送核弹飞艇（`ParaDrop.Types` 能投载具）

之前判断"没法把单位送给玩家"是**调查不够**：零售的 `AmerParaDropInf / AllyParaDropInf /
SovParaDropInf / YuriParaDropInf` 只是**按阵营的步兵列表**，而 Ares 提供了
`[General] ParaDrop.Aircraft / ParaDrop.Types / ParaDrop.Num` ——
`ParaDrop.Types` 接受任意 ObjectType，不看玩家阵营。

```ini
[General]
ParaDrop.Aircraft=PDPLANE
ParaDrop.Types=ZAINukeGunship
ParaDrop.Num=1

[SuperWeaponTypes]
14=ZAIWorldNuke
[ZAIWorldNuke]
Type=ParaDrop  Action=ParaDrop  RechargeTime=0.01
SW.AlwaysGranted=yes  SW.AllowAI=no  SW.RequiresTarget=yes
```

点一次 → 运输机飞过 → 指定位置投下 `ZAINukeGunship`，之后玩家指挥。
飞艇保留战车工厂建造作为保险。

**为什么安全**：电脑没有空投的使用路径（零售 `[ParaDropSpecial]`/`[AmericanParaDropSpecial]`
都没有 `SW.AutoFire`，电脑也不能点按钮），所以这三个全局键实际只对玩家生效。

守卫新增：`ParaDrop.Types` 必须等于飞艇（写 `E1` 会被拦）、`ParaDrop.Num>=1`、
`ParaDrop.Aircraft` 非空、`[ZAIWorldNuke] Type=ParaDrop` 且 `SW.AllowAI=no`。

## 3.9.6 — 核弹飞艇：基洛夫机体 + 神盾式追踪导弹 + 核弹头

飞机版还是"普通飞机"（依赖空指部、要停机位、会被防空打掉）。改成**基洛夫机体**：

- `[VehicleTypes] 85=ZAINukeGunship`，克隆 `[ZEP]`：`BalloonHover=yes` 永不落地、
  `MovementZone=Fly`、`Strength=100000`（打不死）、`Insignificant=yes`（防空不瞄）、
  `Prerequisite=GAWEAP` + `TechLevel=1` + `Cost=2000`（战车工厂可造）；
- `[ZAINukeMissile]`：`Damage=600 / ROF=40 / Range=20 / Speed=120 / OmniFire=yes`，
  `Warhead=NUKE`（零售弹头，不改）；
- `[ZAINukeMissileProj]`：克隆 `[AAHeatSeeker2]`（`AA=yes` + **`AG=yes`**，`Image=DRAGON`，`ROT=60`）。
  **神盾的 `[MedusaProjectile]` 是 `AG=no`，只能打空中**，直接拿来打地面不会命中；
- 旧的飞机 `[ZAINukePlane]` / `[ZAINukeBomb]` 与 `[AircraftTypes]` 条目全部删除。

**为什么不做"传送事件"**：能生成单位的触发器动作（4 创建队伍、7/80 空投、107 超时空传送）
房子都取自**触发器所属国家**，而玩家在国家界面自选，地图无法预知 → 地图侧无法把单位送给玩家；
因此投送方式用战车工厂建造（依赖最少）。

`assert_nuke_gunship` 检查：可造、打不死、不被瞄、`BalloonHover=yes`、`Warhead=NUKE`、
**弹丸 `AG=yes`**、`[VehicleTypes]` 已注册、旧飞机段已删除、不进任何 TaskForce。
实测 `AG=no`、`Warhead=SAMWH`、`Strength=2000`、`TechLevel=-1`、`Insignificant=no` 全部被拦。

## 3.9.5 — 核弹炮艇改成玩家可造（`Type=SpyPlane` 走不通）

3.9.4 的 spy-plane 方案实测三个问题：**被防空打掉**（`Strength=800`）、**不投弹**
（`Mission_SpyplaneApproach`/`Overfly` 不看武器）、**航线不对**（航路引擎写死）。

改成普通可造单位：

- `[ZAINukePlane]`：`Spawned=no`、`Selectable=yes`、`TechLevel=1`、`Prerequisite=GAAIRC`、
  `Cost=1500`、`Strength=100000`（打不死）、`Insignificant=yes`（防空不瞄）、`Ammo=100`、
  `Fighter=no`、`AirportBound=no`（不需要停机位）；
- 武器 `[ZAINukeBomb]` 不变：`Damage=600 / ROF=45 / Range=25 / Warhead=NUKE`；
- **删除** `[ZAIWorldNuke]`（`Type=SpyPlane`）与 `[General] SpyPlane.Type/Count/Mission`
  三个全局覆盖（会改到所有侦察机，包括电脑的）。

玩家自己造、自己指挥航线，因此"打不掉 / 会投弹 / 路径自己定"三个问题一次解决。
`assert_nuke_gunship` 检查：可造、打不死、不被瞄、弹头是 `NUKE`、不进任何 TaskForce、
无 `SpyPlane.*` 残留；实测 `Spawned=yes`、`Strength=800`、`Insignificant=no`、`TechLevel=-1`、
spy-plane 残留五种退化全部被拦。

## 3.9.4 — 全图核弹改走「核弹炮艇」：`Type=SpyPlane` + 自定义机型

3.9.2/3.9.3 的三种"一次撒满全图"全部失败（`MultiMissile`+`Range`/`LineMultiplier`、
`Type=Battery`+`SW.MaxCount`、`MultiMissile`+`SW.MaxCount`），实测都是一发普通核弹 ——
核弹弹头由**全局** `[General] Nuke.Payload` 决定，单个超武换 `WeaponType` 改不了它。
三个失败类型已删除。

改成"派一架飞机横穿地图沿途投弹"：

- 新机型 `ZAINukePlane`（`[AircraftTypes]` 第 13 项，克隆 `[BPLN]`，`Fighter=yes`、
  `Spawned=yes`、`Ammo=10`、`Speed=14`）；
- 新武器 `ZAINukeBomb`：`Damage=600`、`ROF=45`、`Range=25`、`Warhead=NUKE`（弹头不改）；
- `[General] SpyPlane.Type=ZAINukePlane`、`SpyPlane.Count=1`、`SpyPlane.Mission=Attack`；
- 玩家超武 `ZAIWorldNuke` 改成 `Type=SpyPlane`，免发射井、0.01 冷却、`SW.AllowAI=no`。

**电脑不受影响**：`SpyPlane.*` 是全局键但电脑没有 spy-plane 使用路径；飞机 `Spawned=yes`
且不进任何 TaskForce（`assert_nuke_gunship` 检查）。

**验证信号**：日志 `RuleSet loaded: … (… air …)` 的 `air` 应从 12 → **13**；
游戏里点一次按钮应看到飞机掠过并投下 10 发核弹。若掠过不开火，先试
`SpyPlane.Mission=Move/Guard/Hunt`，再退回"玩家可造的炮艇"（`Spawned=no` + `TechLevel=1`）。

## 3.9.2 — 新增「全图核弹」玩家超武

第 14 个超武类型 `ZAIWorldNuke`，一次发射把核弹撒满全图：

```ini
Type=MultiMissile          ; 一次发射多枚，环形散布
Range=200                  ; 散布环半径（本图 300×300，200 覆盖全图）
LineMultiplier=40          ; 每行 40 发
WeaponType=NukeCarrier     ; 复用零售核弹武器链
RechargeTime=0.01  SW.Shots=1000
SW.AllowPlayer=yes  SW.AllowAI=no  SW.AlwaysGranted=yes  SW.RequiresTarget=yes
```

**依据（二进制，非推测）**：`LineMultiplier` 在超武字段名表里，引擎带校验字符串
`positive LineMultiplier` 与 `finite superweapon ring radius`；`Type` 合法值含 `MultiMissile`；
零售 `[NukeSpecial]` 本身即 `Type=MultiMissile` + `Range=7` + `LineMultiplier=2`。

守卫扩展为同时校验两个玩家类型（注册、`0<RechargeTime<=0.05`、`SW.Shots>=100`、
`AlwaysGranted/AllowAI/AllowPlayer`），并额外要求全图核弹 `Type=MultiMissile`、
`Range>=100`、`LineMultiplier>=10`；反向仍检查 `[NukeSpecial]` 未被改动。
实测四种退化（`Range=7`、`LineMultiplier=1`、`Type=Nuke`、`AllowAI=yes`）全部被拦。

## 3.9.1 — 新核弹冷却太长：`RechargeTime=0` 被引擎当成"没写"

症状：独立类型的核弹能放，但**冷却还是很久**。

原因：`src__rules__ini_value.rs` 的 `read_double_with` 文档写明这类读取器的语义是
"**a zero that keeps the field**" —— **读到 0 就保留字段原值**（等于没写），
所以 `RechargeTime=0` 回落到默认的 10 分钟。`RechargeTime` 是浮点（零售有 `8.5`），
最短可用的正数是 **`0.01` 分钟 ≈ 0.6 秒**（约 9 个逻辑帧）。

改动：

```ini
RechargeTime=0.01     ; 最短正数，0 会被忽略
SW.Shots=1000         ; 双保险：一次充能 1000 发
IsPowered=true        ; 补回零售 [NukeSpecial] 就有的这一行
```

守卫同步收紧：`0 < RechargeTime <= 0.05`、`SW.Shots >= 100`，
实测 `RechargeTime=0`（旧 bug）、`RechargeTime=1`、`SW.Shots=1` 三种都会被拦。

## 3.9 — 换实现：玩家的无限核弹改成独立超武类型，电脑的核弹不动

3.8 直接改 `[NukeSpecial]`（`RechargeTime=0` + `SW.AllowAI=no`）是错的：
**`RechargeTime` 和 `SW.AllowAI` 都是「超武类型」的属性**，改它必然波及 119 家电脑 ——
不关 AI 就每 tick 刷核弹，关 AI 就把电脑的核弹删了。

3.9 的做法：

- `[NukeSpecial]` **完全还原**（`RechargeTime=10`、`SW.AllowAI=yes`、无 `AlwaysGranted`），
  `[NAMISL] SuperWeapon=NukeSpecial` 也不动 → **电脑照旧 10 分钟一发**；
- 新增第 13 个超武类型 `ZAIUnlimitedNuke`（`[SuperWeaponTypes]` **末尾**追加，
  避免既有索引位移），克隆自 `[NukeSpecial]`，但：
  `RechargeTime=0`、`SW.AlwaysGranted=yes`（免发射井）、`SW.AllowAI=no`、`SW.AllowPlayer=yes`；
- 玩家因此多一个独立核弹按钮，零冷却、无限次。

**验证**：引擎加载规则时会打 `SuperWeaponTypes: N loaded`（`ra2.log.1` 里有 60 条，改动前是 12）。
启动一次后日志必须是 **`13 loaded`**，否则说明注册表硬上限是 12，需要走退路。

**防回归** `assert_player_nuke_section` 双向检查：玩家类型四项必须满足；
同时 `[NukeSpecial]` 必须仍是 `RechargeTime=10` / `SW.AllowAI=yes` / 无 `AlwaysGranted`。
实测四种退化（玩家 `RechargeTime=10`、玩家 `AllowAI=yes`、电脑 `RechargeTime=0`、
电脑 `AllowAI=no`）全部被拦。

## 3.8 — 0 号位玩家的无限核弹

```ini
[NukeSpecial]
SW.AlwaysGranted=yes   ; 不需要发射井，开局就有核弹按钮
RechargeTime=0         ; 发射后立刻再次就绪（零冷却）
SW.AllowAI=no          ; 必须：RechargeTime 属于超武类型，电脑会一起继承
SW.AllowPlayer=yes
```

- **为什么必须关掉 AI 的核弹**：`RechargeTime` 是超武**类型**的属性而不是玩家的属性，
  不改 `SW.AllowAI` 的话 119 家电脑会一起零冷却，变成每 tick 扔核弹。核弹因此变成玩家专属；
  电脑仍保留闪电风暴 / 铁幕 / 超时空 / 心灵控制器 / 基因突变器。
- **为什么不在 `[SuperWeaponTypes]` 里加第 13 个类型**：`--probe` 的输出里没有超武类型列表，
  新增类型**无法验证是否被引擎接受**，而单位类型注册表在原版是固定数量的 —— 宁可改现成的
  `[NukeSpecial]`，至少可验证。
- 新增 `assert_player_nuke_unlimited`：四项（`RechargeTime=0` / `AlwaysGranted=yes` /
  `AllowAI=no` / `AllowPlayer=yes`）任一不满足就构建失败；实测能拦住
  `RechargeTime=10`、`AllowAI=yes`、`AlwaysGranted=no` 三种退化。

## 3.7.1 — 修 bug：新图有一个电脑和玩家挤在 3 格内

症状：`Flat Snow 120 Center` 进游戏后，**有一个电脑出生点紧贴玩家**（(151,152)，离玩家 3 格）。

当时的错误结论：以为"电脑之间最近邻 22–30 格"就说明布局没问题 ——
断言只查了电脑之间的间距，**没查玩家到电脑的距离**。

实际原因：`spread_points` 的最远点采样只把**已选中的电脑点**当作"已知距离"，
玩家的格子虽然从候选里剔除了，但**玩家周围那片区域没有被标记为已占用**。
算法收尾时去填补"最大的空洞"，而玩家身边正是那个空洞 → 最后一个点落在玩家旁边。

修法：

- `spread_points` 把玩家当作**距离场的第一个固定点**（`nearest[c] = dist(c, 玩家)`），
  并且只在"离玩家 ≥ `PLAYER_CLEARANCE`（12 格）"的格子里选点；
- `assert_flat120` 与 `assert_ice120` 都增加 **玩家 → 最近电脑 ≥ 12 格** 的检查，
  实测能报出 `a computer starts 3 cells from the player (floor 12)`；
- 重建后：玩家 (150,150)，**最近电脑 23 格**，电脑之间 22–33 格，
  43080 格全雪地、无物件、120 起点、连建两次逐字节相同（257371 bytes）。

## 3.7 — 新地图：纯平雪地 120 人，玩家居中罩铁幕

以 `SuperAI-IceLake-120-NoOre.yrm` 为蓝本（43080 格、`Size=0,0,180,120`、`Theater=SNOW`），
用 `build_maps.py flat` 的两个新参数生成：

```bash
python tools/build_maps.py flat \
    --src maps/SuperAI-IceLake-120-NoOre.yrm \
    --out maps/SuperAI-FlatSnow-120-Center.yrm \
    --name "Super AI Flat Snow 120 Center" \
    --players 120 --tile 696 --sub 0 --height 1 --terrain-newline crlf \
    --player-center --spread 119
```

- `--player-center`：wp0 放在**地形包围盒中心** `(150,150)`（该格在记录里存在，已核）；
  铁幕触发器就是打在 waypoint 0 上的，所以"居中 + 罩铁幕"是同一件事；
- `--spread N`：**最远点采样**在全图铺 N 个电脑点，并重建 `[Header]` 的 120 个起点；
- 地形：43080 格**全部**改成雪地砖 `696/0/1`；
- 物件：`OverlayPack`/`OverlayDataPack`/`Terrain`/`Structures`/`Units`/`Infantry`/
  `Aircraft`/`Smudge`/`CellTags`/`Preview`/`PreviewPack` 全部清空；
- 触发器：`IronCurtainStart`（开局立刻罩）+ `IronCurtain`（每 10 秒）+ `RevealAll` +
  12 段 `AIHunt`（槽位 1–119 每 20 秒 All to Hunt）。

实测：119 个电脑点**最近邻间距 22–30 格**（`min 22 / median 29 / max 30`），
连建两次逐字节相同（257373 bytes）。

新增 `assert_flat120`：每次构建都复核「每格都是 `696/0/1`」「物件段一个不剩」
「起点数与 header 一致」「起点都落在地形上」「最近邻 ≥8 格」「铁幕/揭图/猎杀触发器齐全」，
任一不满足就拒绝写盘。

## 3.6 — 飞机起飞就坠毁：停机位是硬约束，`AirstripLimit=0` 让 AI 永远只有一座空指部

零售数据里写得明白：

```ini
[ORCA] AirportBound=yes ; If I ever need to land and there are no airports I crash
       Dock=GAAIRC,AMRADR  Ammo=1      ; 打一发就必须降落补给
[GAAIRC] NumberOfDocks=4               ; 一座空指部 = 4 个停机位
[AI] BuildRadar=GAAIRC,...             ; 盟军"雷达"槽位就是空指部 → 只造 1 座
     AirstripLimit=0                   ; 额外机库上限 0：永远不造第二座
```

3.3–3.5 给了盟军**每队 10 架、上限 6 队 = 单户 60 架**，却只有 **4 个停机位** →
打一发没地方落 → 盘旋到燃料耗尽 → **坠毁**。
基洛夫 `ZEP` 没有 `AirportBound`（不需要停机位），所以它一直正常 ——
这正是"基洛夫飞到脸上、飞机却全在坠毁"的原因。

改动：

| 项 | 旧 | 3.6 |
| --- | --- | --- |
| `[AI] AirstripLimit` | `0` | **`4`**（1 雷达位 + 4 机库 = 20 个停机位） |
| `[AI] AirstripRatio` | `.12` | **`.25`** |
| 机场型飞机（`ORCA`/`BEAG`）每队 | 6–10 | **`3`** |
| 机场型空军队伍 `Max` | `6` | **`3`**（3×3=9 架 ≤ 12 停机位） |
| 火箭飞行兵每队 | 12 | **`6`**（40 秒解散窗口内能补齐，才真的会出现） |
| 基洛夫 `ZEP` | 6–8 | **不变** |

不变量：**每户机场型飞机数 ≤ 空指部数 × 4**。
守卫新增：机场型飞机每队 ≤4 架（否则报 `ORCA team holds 10 aircraft but an airfield has only 4 pads`）、
机场型队伍 `Max ≤3`、`JUMPJET` 每队 4–8 人。

## 3.5 — 火箭飞行兵稀少：`JUMPJET` 被错分到防空分支

零售数据里基洛夫和火箭飞行兵的差距**并不大**（两边都是 `Max=1`：基洛夫 3 支队伍 1–3 架，
火箭兵 2 支队伍 4–5 人）。真正的差距来自分类：

```python
AIR_UNITS = {"ORCA","BEAG","ZEP",...}                      # 只有飞机
AA_UNITS  = {"FV","FLAKT","YTNK","APOC","TELE","HIND","AEGIS","JUMPJET","GGI"}
if units & AIR_UNITS: team_air
elif units & AA_UNITS: team_aa        # 火箭兵会飞、也能对空 → 落到这里
```

火箭飞行兵同时"会飞"和"能对空"，于是被 `elif` 归进了防空，3.2–3.4 的空军强化
（`Max`→6、数量翻倍、权重 ×3 并钉死）**一条都没落到它身上**，只拿到防空的 ×2，
权重还继续按"失败 −50"往 20 的地板掉。

| 队伍 | 3.4 | 3.5 |
| --- | --- | --- |
| `Allied Rocketeer - H1` | `Max=1`、5 人、`100/20/100`（会衰减） | **`Max=6`、12 人、`150/150/150`** |
| `Allied Grizzly Attack - H3`（6 灰熊+4 火箭兵） | `Max=1`、4 人、`100/60/100` | **`Max=6`、10 人、`150/150/150`** |
| `Allied Anit-Grand Cannon` | `Max=1`、5 人、`140/20/140` | **`Max=6`、12 人、`210/210/210`** |

- 把 `JUMPJET` 加进 `AIR_UNITS`；分支 `if air / elif aa` 保证飞行单位**优先按空军**处理；
- 守卫新增两条：必须存在 `JUMPJET` 编队条目、且每条 ≥6 人
  （实测改回 5 人会报 `air task force entry JUMPJET has only 5 aircraft`，
  整条删掉会报 `no JUMPJET task-force entry`）。

## 3.4 — 空军「打完一批很久不造」：触发器的胜率反馈把权重压到了地板

**原版没有空军冷却时间。** 真因在 `AiTriggerTrackRecord`
（`team_script_vm.rs`，`RegisterSuccess @ 0x0041FD60` / `RegisterFailure @ 0x0041FE20`）：

- 每条 AI 触发器有运行时权重，初始 = `weights[0]`（hard 档）；
- 队伍**被摧毁时**结算：达成脚本动作 `49`（进攻）算成功，否则算**失败**；
- 失败 `-= AITriggerFailureWeightDelta`（零售 **−50**），成功 `+= 20`；
- 结果**钳制在 `[weights[1], weights[2]]`**（中档 / 简单档权重）。

飞机是最容易在「进攻」之前就被打掉的东西 → 空军触发器几乎每次都被判失败：

| 触发器（3.3 之后） | 初始 | 地板 | 几次失败到底 |
| --- | --- | --- | --- |
| `Allied Harrier - H1` | 150 | **30** | 3 次 |
| `Soviet Kirov Medium` | 210 | **30** | 4 次 |
| `Nation Korea` / `Kirov Hard` | 1500 | **30** | 30 次 |

砸到 30 就停在地板（普通进攻触发器是 40–70），于是「再也抽不到」。
我们的进攻队不受影响：`ZAIATK01-G` 第二步就是 `49`，基本都算成功。

**叠加因素**：`DissolveUnfilledTeamDelay` 曾是 900（15 秒），
10 架飞机的队伍第一架还没下线就被判「空队伍解散」，**也算一次失败**。

改动：

1. **空军触发器权重钉死** —— 三个槽全设成三者最大值，钳制区间退化为一点，
   权重恒定：`210/210/210`、`1500/1500/1500`；
2. `DissolveUnfilledTeamDelay` **900 → 2400**（40 秒），让慢队伍有机会出现第一个成员；
3. `assert_air_and_aa_boosted` 增加要求：每条空军触发器的 `weights[1] == weights[2]`，
   否则构建失败（实测能报出 `210/30/210` 这种会重新衰减的形状）。

## 3.3 — 空军队伍数量 ×2、队伍规模 ×2

在 3.2 的基础上按"数量翻倍、规模翻倍"再推一档：

| 常量 | 3.2 | 3.3 |
| --- | --- | --- |
| `AIR_TEAM_MAX`（同户可同时存在的空军队伍数） | 3 | **6** |
| `AIR_SIZE_FACTOR`（队伍规模倍率） | —（无） | **2** |
| `AIR_UNIT_CAP`（单队飞机上限） | 8 | **16** |
| 单队飞机数 | `max(零售+1, 3)` | `max(零售+1, 3) × 2` |

实际数值（零售 → 3.2 → 3.3）：

| 空军队伍 | 零售 | 3.2 | 3.3 |
| --- | --- | --- | --- |
| `Max`（9 支队伍） | 1 | 3 | **6** |
| 黑鹰 `BEAG` | 4 | 5 | **10** |
| 入侵者 `ORCA` | 4 | 5 | **10** |
| 入侵者 `ORCA`（支援） | 2 | 3 | **6** |
| 基洛夫 `ZEP`（硬） | 3 | 4 | **8** |
| 基洛夫 `ZEP`（中） | 2 | 3 | **6** |
| 基洛夫 `ZEP`（反巨炮） | 1 | 3 | **6** |

守卫门槛同步提到"每条空军条目 ≥6 架"，零售 aimd 依然会被拦住。

> **规模提醒**：6 队 × 10 架 = 单户理论峰值 60 架，单位数明显上升，可能影响帧率；
> 超编飞机还会在空中排队待降。回退只需 `AIR_SIZE_FACTOR=1`、`AIR_TEAM_MAX=3`。

## 3.2 — 空军和防空部队太少：加队伍上限、加数量、加权

单位生产**不写日志**，所以这一轮靠的是 aimd 数据本身。两个结构性事实：

- **空军**：132 支 TaskForce 里只有 **7 支**带飞行单位，用它们的 **11 支队伍全部 `Max=1`**
  —— 一个 AI 同一时刻最多只有一支空军队伍在场，其中还有一支只有 1 架基洛夫；
  对应触发器的权重只有 20–70，抽中概率和普通进攻队一样。
- **防空**：只有 **46/165** 条触发器带防空单位，其余 119 条组出来的队伍没有防空。

改动（`boost_air_and_aa`）：

| 项 | 零售 → 模组 |
| --- | --- |
| 空军队伍上限 `Max` | `1` → **`3`**（9 支队伍） |
| 每支空军队伍的飞机数 | 至少 **3 架**，已更多的 +1（上限 8） |
| 空军触发器权重 | **×3**（上限 1500） |
| 防空触发器权重 | **×2**（上限 1500） |

- 权重按难度三档同时乘，难度间的相对关系不变；上限 1500 不会盖过 5000 权重的接管触发器；
- 没有新增队伍类型，兵种搭配不变；
- 效果：空军从「同时最多 1 支、1–4 架」变成「最多 3 支、每支 3–5 架」；
  带防空的队伍在抽签中的权重占比从约 28% 提到约 44%。

新增 `assert_air_and_aa_boosted`：产物里必须有 ≥5 条空军 TaskForce 条目且每支空军队伍 ≥3 架，
否则构建失败（对着零售 aimd 跑会报 `air task force entry ORCA has only 2 aircraft`）。
可调旋钮：`AIR_TEAM_MAX`、`AIR_UNIT_MIN`、`AIR_WEIGHT_FACTOR`、`AA_WEIGHT_FACTOR`。

## 3.1 — AI 防空造得太少：问题在防御「选型」，不在产量

现象：AI 的防空建筑明显偏少。**这和"打掉才重建"无关** —— 重建只管"节点空了要不要再建一栋"，
"建哪一种防御"由 `AI_ChooseNextProduction` 决定，而它是**先选类别、再选建筑**：

1. 把本户每栋建筑的 `AntiAirValue/AntiArmorValue/AntiInfantryValue` 按象限累加，
   取总量最小象限的**占比**；
2. 取**指定敌人**的兵力构成（air/vehicles/infantry），按 `AIForcePredictionFudge=` 加噪声；
3. **类别 =（敌人占比 − 我方占比）最大者**；
4. 候选 = `[AI] *BaseDefenses=` 里**该类别值 > 0** 的建筑；
5. 候选里按该类值加权随机；该类别没有候选才回退 armor → infantry → air。

零售数值把这个坑埋好了：

| 建筑 | Inf | Armor | Air | 后果 |
| --- | --- | --- | --- | --- |
| `NASAM` 盟军爱国者 | **0** | **0** | 25 | **只在 air 类别是候选** |
| `NAFLAK` 苏军防空炮 | **0** | **0** | 25 | **只在 air 类别是候选** |
| `YAGGUN` 尤里盖特机炮 | 25 | 10 | 25 | **三类都是候选** |

air 类别要赢，得让敌方空中占比超过我方防空覆盖；AI 之间几乎没有空军，所以它很少赢，
盟/苏防空炮于是几乎不被选中。日志实测：`YAGGUN` 62 次 > `NASAM` 41 次 > `NAFLAK` 29 次，
盟军防空占其防御约 17%、苏军约 12%。

**改动**（`SECTION_KEY_EDITS`）：

```ini
[NASAM]  AntiInfantryValue=25   AntiArmorValue=10     ; 零售 0 / 0
[NAFLAK] AntiInfantryValue=25   AntiArmorValue=10     ; 零售 0 / 0
```

- **防御节点总数一个没动**（`*BaseDefenseCounts` 仍零售 `25/20/6`）→ 建造强度不变，
  只是同样这些节点里防空被选中的概率从"几乎 0"提到和盖特机炮同级（预期 20–30%）；
- 想更激进就调大（30/15），想收一点就 15/5；
- 新增 `assert_aa_defenses_competitive`：三个防空建筑的三类值必须**都非零**，否则构建失败
  —— `0/0/25` 这种"看起来正常、实际被架空"的数值最容易在换数据时静默回归；
- `tools/analyze_log.py` 增加防空占比统计与 `AA_MIN=20%` 闸门（`AA: 6 of 17 defences (35%)`），
  下一局可直接从日志验收。

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
python tools/build_mod.py --rules-dir "<原版规则目录>" \
    --out "<游戏目录>/Mods/SuperAI-assembly" --assembly-teams
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
