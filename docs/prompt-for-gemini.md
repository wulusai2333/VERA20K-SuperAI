# 给 Gemini 的提示词（直接整段复制）

---

我在给 **VERA20k 0.4.0**（《红色警戒2：尤里的复仇》的开源重制版，Rust 实现，支持部分 Ares 语法）
做规则 mod。mod 由 `rulesmd.ini` / `aimd.ini` / `artmd.ini` 和 `.yrm` 地图文件组成，我用 Python
脚本从零售 `rulesmd.ini` 生成 mod 文件，所以任何改动都是"基于零售值 + 我的覆盖"。

请帮我设计一个**只归人类玩家（0 号位）使用**的"核弹兵/核弹飞艇"投放方案。
要求：**尽量做成地图专属**（只在那张 `.yrm` 里生效），并且**绝对不要改动任何公共/共享配置**
（不要动 `[General]` 的 `*ParaDrop*`、不要动 `[CombatDamage]` 的散布、不要给电脑的超武加 `SW.*`、
不要动 AI 的 `TaskForce` / `AITrigger`）。

## 一、已经验证可用的（可以直接用）

1. **新增超武类型可以加载**：`[SuperWeaponTypes]` 末尾追加
   `13=ZAIUnlimitedNuke`，超武段：

   ```ini
   [ZAIUnlimitedNuke]
   UIName=Name:Nuke
   Name=N U K E !!! (player)
   Type=MultiMissile
   WeaponType=NukeCarrier
   Action=Nuke
   SidebarImage=NukeIcon
   Range=7
   LineMultiplier=2
   IsPowered=true
   ShowTimer=no
   RechargeTime=0.01
   SW.Shots=1000
   SW.AllowPlayer=yes
   SW.AllowAI=no
   SW.AlwaysGranted=yes
   SW.RequiresTarget=yes
   SW.FireIntoShroud=yes
   ```

   实测：玩家点一次就能打一发普通核弹，电脑拿不到（`SW.AllowAI=no`）。这是"专属"的正面样板。

2. **新增载具类型可以加载**：`[VehicleTypes]` 末尾追加 `85=ZAINukeGunship`，
   克隆 `[ZEP]`（基洛夫）：

   ```ini
   [ZAINukeGunship]
   Prerequisite=GAWEAP
   TechLevel=1
   Cost=2000
   Strength=100000
   Insignificant=yes
   BalloonHover=yes
   GuardRange=200
   CanPassiveAquire=yes
   OpportunityFire=yes
   Primary=ZAINukeMissile
   Ammo=200
   Locomotor={92612C46-F71F-11d1-AC9F-006008055BB5}
   MovementZone=Fly
   ConsideredAircraft=yes
   ```

   实测：战车工厂能造、能飞、200 格自动开火、防空打不死、电脑不会造（不进任何 `TaskForce`）。

## 二、已经排除的做法（**请不要重复这些**，都是实测过的）

| 做法 | 结果 |
| --- | --- |
| 新超武 `Type=MultiMissile` + `Range=200` + `LineMultiplier=40` | 只出一发普通核弹。核弹弹头来自**全局** `[General] Nuke.Payload`，单个超武换 `WeaponType` 改不了 |
| 新超武 `Type=Battery` + `SW.MaxCount=40` | 完全无效 |
| `Type=SpyPlane` + `[General] SpyPlane.Type/Count/Mission` | 飞机会横穿地图，但 **spyplane 的 mission 从不使用飞机武器**，且航线是引擎写死的，改不了；飞机还会被防空打掉 |
| `Type=DropPod` + `[General] DropPod.Types` | 点下去**毫无反应** |
| `[General] ParaDrop.Types=<载具>` | 投出来是**普通伞兵**。VERA 的 paradrop 只读四张**按阵营、与电脑共用**的表：`AmerParaDropInf` / `AllyParaDropInf` / `SovParaDropInf` / `YuriParaDropInf`（结构上是 `GeneralTypeLists { paradrop_infantry: [Vec<String>; 4] }`） |
| 改那四张 `*ParaDropInf` 表 | 玩家和电脑**共用**，电脑也会投同样的东西 → 不可接受 |
| 地图触发器动作 4（创建队伍）/ 7 / 80（空投队伍）/ 107（超时空传送队伍） | 队伍的房子取自**触发器所属国家**（`resolve_trigger_house` 用 `CountryIdx`），而玩家人类的国家是开局界面自选的，地图无法预知 |
| 地图 `[Units]` 预置单位 | `INDEX=OWNER,TYPE,HEALTH,X,Y,FACING,MISSION,TAG,...` 里的 `OWNER` 是**国家/房子名**，多人图里同样无法保证落到人类玩家 |

补充事实：

- 地图的 `[Houses]` 是 `0=Americans / 1=Alliance / 2=French ...` 这种"序号=国家"的映射；
- 引擎支持 Ares 的 `<Player @ N>` 选择器，但已知只在**部分超武参数的取值**里被解析
  （例如 `SW.Range.<Player @ ..>` 这种写法在二进制里出现过）；
- `[SuperWeaponTypes]` 是**列表驱动**的，新增项会真的加载；
- `SW.RechargeTime=0` 会被当成"未设置"（回落到默认 10 分钟），所以必须写 `0.01` 这种极小值。

## 三、我的需求

给我一个**人类玩家专属**的"核弹兵"（会飞、自动开火、打核弹）或"核弹飞艇"的**投放/获取方式**，
满足：

1. **只有人类玩家（0 号位）能拿到**，电脑拿不到；
2. **最好地图专属**：只写在那张 `.yrm` 或那张图的附属配置里；
3. **不改公共表**：`[General]` 的 `*ParaDropInf`、`[CombatDamage]`、零售超武的 `SW.*`、
   AI 的 `TaskForce`/`AITrigger` 全部保持零售值；
4. 允许的手段：地图文件自身的数据（`[Houses]`、`[Triggers]`、`[Units]`、`[Countries]`、
   `[Basic]`、`[VariableNames]` 等）、**新增的独立类型**（新超武 / 新单位 / 新武器 / 新弹头）、
   Ares 的 `Player @ N` 选择器，或任何 VERA 支持的地图级特性。

## 四、请给出

1. **具体到键名和文件位置**的方案（哪个 ini/地图段、哪几个键、取什么值）；
2. 每一步**为什么在 VERA 里能成立**的依据（如果只是"原版 RA2/Ares 可以"，请说明 VERA 是否实现了它，
   或者怎么验证）；
3. **验证方法**：游戏内看到什么现象、日志里应该出现什么行（例如
   `SuperWeaponTypes: N loaded`、`RuleSet loaded: ... (.. air ..)`）；
4. 如果有多套可行方案，按"改动最小 / 最稳"排序，并说明各自的代价。

---

## 附：当前 mod 的版本与结构（供参考）

- 版本 3.10.8，mod 目录 `Mods/SuperAI/`，包含 `rulesmd.ini`、`aimd.ini`、`artmd.ini`、`mod.ini`；
- 地图目录 `Maps/`，其中 `SuperAI-FlatSnow-120-Center.yrm` 是 300×300 的雪地平地，
  120 个出生点，玩家固定在 `(150,150)`（waypoint 0），其余 119 个是电脑；
- 该图有 `[Houses]`（14 条 `序号=国家`）、`[Triggers]`（`<none>` 拥有者 + `Player @ X` 参数的
  AIHunt 触发器、动作 6）；`[Units]`/`[Infantry]`/`[Structures]` 目前为空。
