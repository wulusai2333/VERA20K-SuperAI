# AI 设计说明

这份文档解释模组**改了什么、为什么这样改**，以及哪些地方撞到了引擎的硬限制。

## 1. 目标

1. 电脑不再「攒一波、回家、再出发」，而是持续施压。
2. 基地向外交替铺开，而不是挤在建造厂旁边。
3. 中后期不囤兵：家里的部队会被定期清出去。
4. 观战者不会被打死，也不需要手动输入作弊码。

## 2. 规则层（`rulesmd.ini`）

### 经济

| 键 | 值 | 说明 |
| --- | --- | --- |
| `MultiplayerAICM` | `100000,100000,100000` | 开局按当前资金追加 `coef/100`，即 **×1001**。原版 `400` = 困难 5 倍 |
| `BuildSpeed` | `.025` | 原版 `.7`；数值是每 1000 信用点需要的分钟数，**全局生效** |
| `ProduceCashAmount` / `Delay` | 矿场 `100` / `60` | 每 4 秒 +100，无矿地图的经济来源 |
| `AIBuildCounts` | 见下 | Ares 的「计划副本数」，控制基地规模 |

`AIBuildCounts` 分布（三个难度相同）：

| 建筑 | 数量 |
| --- | --- |
| 电厂 / 矿场 / 兵营 / 战车工厂 | 60 |
| 作战实验室 / 雷达 | 40 |
| 维修厂 | 30 |
| 机场 / 心灵信标 | 20 |

> 实测把电厂设成 250 会让 AI 把建造预算全砸在排在前面的建筑上
> （403 个电厂、只有 12 个战车工厂），所以保持 60 的均衡值。
> 引擎的 `BASE_PLAN_INSERT_LIMIT` 是 256，超过也不会更好。

### 基地与防御

| 键 | 值 | 说明 |
| --- | --- | --- |
| `Allied/Soviet/ThirdBaseDefenseCounts` | `100,100,100` | 每家规划 100 个防御建筑 |
| `AIBaseSpacing` | `1` | **不要调大**。设 2 会让选址失败，基地卡在约 70 栋 |
| `AIRestrictReplaceTime` | `120` | 被拆后更快重建 |
| `[GACNST]/[NACNST]/[YACNST]` | `SpySat=yes` | 展开基地即全图，不耗电 |

### 进攻节奏

| 键 | 原版 | 模组 | 说明 |
| --- | --- | --- | --- |
| `TeamDelays` | 2000/2500/3500 | `45,60,90` | 单位是逻辑帧（约 15 帧/秒），困难约 3 秒一轮 |
| `TotalAITeamCap` | 30 | `45` | 同时存在的队伍上限 |
| `MaximumAIDefensiveTeams` | 2 | `0` | 不保留守家编制 |
| `MinimumAIDefensiveTeams` | 1 | `0` | 同上 |
| `UseMinDefenseRule` | yes | `no` | 开局不强制先造防御队 |
| `AIHateDelays` | 30/50/70 | `8,12,18` | 更快锁定敌人 |
| `AITriggerSuccessWeightDelta` | 20 | `50` | 打赢后权重涨得快 |
| `AITriggerFailureWeightDelta` | -50 | `0` | 打输也不降权，越打越敢打 |
| `DissolveUnfilledTeamDelay` | 5000 | `900` | 凑不齐的队伍 60 秒后解散，腾出编制 |
| `[AI] Paranoid` | yes | `no` | 电脑不抱团针对玩家 |
| `AINearestEnemy`（VERA 扩展） | 否 | `yes` | 电脑选最近的敌人，FFA 会互殴 |

## 3. 队伍层（`aimd.ini`）

### 3.1 编制放大

对 65 支「进攻型」队伍（`Aggressive=yes` 且 `IsBaseDefense!=yes`，排除工程师/间谍/
矿车/MCV/海军等特种队）的 TaskForce 做 ×2：

| 队伍 | 原版 | 模组 |
| --- | --- | --- |
| 苏联装甲（困难） | 7 | **14** |
| 苏联天启（困难） | 4 | **8** |
| 盟军超硬 | 13 | **26** |
| 尤里终结者 | 13 | **26** |

单条目上限 16、单队总量上限 40，避免一个队伍大到无法集结。
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

67 条进攻触发器的 `[AITriggerTypes]` 权重从 70 提到 **250**，下限 150，
三个难度位全部设为 1。防御队和特种队的触发器不动。

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
AlliedBaseDefenseCounts=60,60,60
```

想更疯：

```ini
TeamDelays=20,30,45
BuildSpeed=.015
MultiplayerAICM=200000,200000,200000
```

改完必须重启游戏。`tools/build_mod.py` 里的常量是这些值的唯一来源，
直接改发布版 `rulesmd.ini` 也可以，但下次重建会被覆盖。

## 7. 撞到的引擎限制

这些都已经实测确认，不是猜测：

| 限制 | 现象 | 结论 |
| --- | --- | --- |
| 基地选址周长 | 每家在约 100 栋后停止建造 | 换大图 / 减少 AI，改 INI 无法突破 |
| `AIBaseSpacing=2` | 约 70 栋后大量选址失败 | 必须保持 1 |
| AI 不会造 MCV 扩张 | 没有「生产 MCV → 展开」路径 | 只能改引擎源码 |
| 类型注册表固定 | 新增 `[VehicleTypes]` 不生效（日志仍 85 项） | 不新增单位，只改既有数据 |
| 本地玩家地图建筑被跳过 | 预置的卫星/基地被删除 | 用触发器，不用地图建筑 |
| `AIBuildCounts=250` | 建造顺序严重偏科 | 保持每类 60 |

## 8. 参考

- VERA20k 源码：`src/sim/ai_team_creation.rs`、`ai_base_building.rs`、
  `base_plan_generation.rs`、`team_script_vm/actions.rs`、`house_strategy.rs`、
  `scenario_bootstrap/launch_houses.rs`。
- 地图格式与触发器细节见 [map-format.md](map-format.md)。
