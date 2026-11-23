# Changelog

本项目在 2026-11-22 从零迭代到 2.0，同日继续到 3.7；以下是可复现的功能节点。

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
