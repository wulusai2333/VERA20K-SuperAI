# Mass Skirmish AI（Stage 1）设计说明

> 已转正为默认模组。本文只描述**已实现并跑通单图 probe**的 Stage 1；
> Stage 2 的实机帧率/观感联调尚未执行，文末列出观测清单。

## 1. 目标

- 用**纯净官方** `rulesmd.ini` / `aimd.ini` / `artmd.ini` / `mpmodesmd.ini`
  （`F:\Games\red2`）生成独立模组 `mod/MassSkirmish`，不改 VERA20k 二进制。
- **已经移除** `GACNST/NACNST/YACNST`、`AMCV/SMCV/PCV` 和 6 个超武上的 `BuildLimit`：
  VERA20k 的 AI 工厂不执行它，它实际只限制玩家侧边栏。
- `GACNST/NACNST/YACNST` 保持 **`AIBuildThis=yes`**：这是 AI 基地计划的 `BuildConst` 种子。
  曾经试过设为 `no` 来禁止平地 yard，但会清空 `build_const_order`，AI 只剩电厂/防御，
  连兵营都不造；已回退。平地 yard 的彻底限制需要引擎层处理，不能靠这个键。
- 当前控制超额建造的主要手段是 **`AIRestrictReplaceTime=15`（15 fps 下 1 秒）**；
  这是实机验证过的“减少超额建造/重建抖动”的参数，不是精确的硬上限。
- `AIBuildCounts` 仍作为**基地计划目标数**：Stage 1 为超武 `3,3,3`、生产建筑 `2/3`；
  `--profile max` 为超武 `20,20,20`。它是计划目标，不是实时拥有上限。
- 进攻队出生即出征；脚本第一优先拆敌方建造厂；空军为主、地面为辅；
  除运输队外禁止空地混编。

## 2. 构建与安装

```powershell
# 生成 Stage 1（默认 4 厂 / 每类 3 超武计划目标）
python tools/build_mass_skirmish.py --rules-dir F:\Games\red2 --out mod\MassSkirmish --profile stage1

# 生成 max 计划目标（20 厂 / 每类 20 超武）
python tools/build_mass_skirmish.py --rules-dir F:\Games\red2 --out mod\MassSkirmish --profile max

# 安装（不切换 config.toml 的激活 mod）
python tools/install.py --game-dir F:\Games\VERA20K --mod MassSkirmish --no-maps

# 单图无头校验
python tools/check.py --game-dir F:\Games\VERA20K --mod MassSkirmish --only-map SuperAI-IceLake-120-NoOre.yrm
```

`mod/MassSkirmish/build-report.txt` 记录参数、计数、断言和 SHA256；重复构建应逐字节一致。

## 3. 关键参数

### 3.1 经济与节奏

| 键 | 值 |
| --- | --- |
| `BuildSpeed` | `.025`（约 1.5 秒/1000 信用点） |
| `MultiplayerAICM` | `100000,100000,100000`（×1001） |
| `TeamDelays` | `180,270,360`（12/18/24 秒） |
| `TotalAITeamCap` | `12,12,12` |
| `DissolveUnfilledTeamDelay` | `2400` |
| `UseMinDefenseRule` / Min / Max 防守队 | `no` / `0,0,0` / `0,0,0` |
| 矿场 `ProduceCashAmount/Delay` | `100` / `60`（每 4 秒 +100） |
| `AIVirtualPurifiers` / `AIExtraRefineries` / `AISlaveMinerNumber` | `4,2,0` / `0,0,0` / `2,2,2` |

### 3.2 基地、超武与建造节流

| 项 | 值 | 说明 |
| --- | --- | --- |
| `BuildLimit` | **已移除** | 从 3 个 yards、3 个 MCV、6 个超武段删除；AI 工厂不执行，保留只限制玩家 |
| `GACNST/NACNST/YACNST` | `AIBuildThis=yes` | 必须保留基地计划种子；设为 no 会让 AI 只造电厂/防御 |
| 扩建触发器条件 | Stage 1 `< 4`；max `< 20` | 3 条 5000 权重 `ZAIEXP01-03-G`，是目标不是硬上限 |
| 6 个超武 `AIBuildCounts` | Stage 1 `3,3,3`；max `20,20,20` | 基地计划目标数，不是实时拥有上限 |
| 维修厂 | `AIBuildThis=yes` | 解锁 MCV |
| 防御计划 | `10,10,10` | 从零售 25/20/6 降下来 |
| 墙 | `AIPickWallDefensePercent=0` | 不造墙 |
| 重建延迟 | `AIRestrictReplaceTime=15` | 15 帧 = 1 秒；只延迟“丢失建筑节点的重新规划” |
| 建造失败上限 | `MaximumBuildingPlacementFailures=3` | 放不下就放弃节点 |

**引擎事实**：
- `base_plan_generation.rs:357` 的候选过滤要求 `candidate.ai_build_this`；yard 设为 `no` 后
  连 `BuildConst` 种子也被剔除，`build_const_order` 为空，`choose_building` 直接返回，
  只剩电厂/防御路径。因此 yard 必须保持 `AIBuildThis=yes`。
- `Factory_AI` → `suggest_new_object()` → `start_active_production()` 不调用
  `CanBuild`/`check_build_limit`；只在 `NPATCH_ENABLED` 下检查
  `AIBuildLimit`/`EnableAIBuildLimitation`。当前 VERA20k 0.4.1 的
  `NPatch support compiled in: false`，所以 AI 工厂不执行 `BuildLimit`。
- `BuildLimit` 只在 `CanBuild`/`check_build_limit`（侧边栏、队伍准入）路径生效。
- `AIRestrictReplaceTime` 只在 `node_may_replan()` 里读：只影响“已丢失、原本在计划里的
  建筑节点”的重规划；电厂、有武器建筑、墙、资源建筑会绕过它；它**不控制新建**。
- 因此 1 秒延迟是“减少重建抖动/超额建造速度”的经验参数，不是精确的 20 上限。

### 3.3 零集结 + 斩首建造厂

`ZAIATK-CY`：

```ini
[ZAIATK-CY]
Name=Mass Skirmish Decap
0=53,0
1=46,131074    ; 0x20000 | GACNST 2
2=46,131097    ; 0x20000 | NACNST 25
3=46,131372    ; 0x20000 | YACNST 300（dense index）
4=0,6
5=0,2
6=0,1
7=0,5
8=49,0
```

- `53` 是到敌方基地外，不是回家；满足“出生即出征”。
- 动作 46 的 `argument & 0xFFFF` 是 `base_plan_type_index`，高位 `2` = 最近目标
  （`src/sim/team_script_vm/actions.rs:2917`、`:3006`、`:3322`）。
- **YACNST 是 300，不是 301**：零售 `[BuildingTypes]` 有重复 `NAPSYA`；
  `loading.rs:1683` 使用 `parse_registry` 去重后的 dense index，`loading.rs:2171-2200`
  明确大小写去重。构建脚本断言 GACNST=2、NACNST=25、YACNST=300。
- 例外：3 支 MCV 队保留 `043F23CC-G`；9 支含 55/57 的超武队保留零售脚本；
  运输队保留原脚本；间谍/工程师队保留原脚本。

### 3.4 空地分离与空军为主

- 只读分析官方 `aimd.ini` 发现 3 个混合 TaskForce：
  - `0CE4DA9C-G`：4 JUMPJET + 6 MTNK → 原 TF 改为纯地面，新增纯空 TF/Team；
  - `0ACDD81C-G`：3 V3ROCKET + 2 SHK + 2 HTK → 原 TF 改为纯地面，新增纯空 TF/Team；
  - `0617909C-G`：SHAD + TANY/E1/GGI → **运输队例外**，保留混编。
- 纯空队：ZEP 每队 8、`Max=3`；JUMPJET 每队 10、`Max=3`；V3ROCKET/DISK/SCHP 至少 6。
- 机场队按**难度分流**，一局里 4 机与 8 机共存，且每户不超过停机位：
  - **Hard**：`ZAI-HVY-0CAC9EFC-G`（克隆 H1，`0=8,ORCA`，`Max=1`，零售脚本
    `08A2135C-G`）→ 8 架正好填满 2 座空指部的 8 个停机位；
  - **Normal/Easy**：原 `0CAC9EFC-G`（4×ORCA，`Max=1`，难度位 `1,1,0`）；
  - 韩国 `0CB1CDEC-G`（4×BEAG）本轮 `Max=0` parked：Hard 已有 8 架，叠加就会超编；
  - 其它机场队 `Max=0`。
  - 守卫：`assert_aimd` 按难度累加“活动机场机数”，超过 `AIBuildCounts×4` 直接构建失败；
    并要求 `Max=1` 的机场队里同时存在 4 机与 8 机两种编制。
- 空指部 `AIBuildCounts=2`（`GAAIRC`、`AMRADR`）→ 每户 8 个停机位；韩国走 `GAAIRC`。
- **地面队翻倍**：拆分后纯地面 TaskForce 的每个条目 ×2（上限 20），
  让地面波次恢复混编时的人数规模；MCV/间谍/工程师/超武/运输队保持零售编制。
- 机场机队**不套** `ZAIATK-CY`，保留零售脚本（`08A2135C-G` / `0CB13B4C-G`）：
  斩首脚本第 0 步 `53`（到敌方基地外集结）对飞机永远不完成，整队会悬停、不投弹；
  零售飞机脚本直接打 quarry，实测 4 架同目标投弹/返场/再出击。构建期有守卫
  （`assert_aimd`：含 `ORCA`/`BEAG` 的队若出现 `Script=ZAIATK-CY` 直接失败）。
  细节与实测数据见 [handoff-aircraft-report.md](handoff-aircraft-report.md)。

> 飞机编队/投弹的现状、已知线索和下一步实验，见
> [handoff-aircraft.md](handoff-aircraft.md)。

### 3.5 触发器

- 55 条 `condition=4` 的攻击触发器：下限 = 起始值，防止“越打越软”。
- 10 条国家特色触发器三槽钉死：英/德/古巴×2/伊拉克/利比亚/俄罗斯=500，韩国=1500。
- 6 条 always（`condition=-1`、权重 40）。
- 6 条反制（ORCA/APOC × 3 阵营，权重 100/20/120）。
- 普通进攻不使用 5000；5000 只留给 MCV 救急/扩建、超武、守卫。
- 新拆出的空中触发器不继承零售的 Team2，避免已知的 `IsBaseDefense` 不一致。

### 3.6 超武自动发射

`SW.AllowAI=yes`、`SW.AutoFire=yes`、`SW.UseAITargeting=yes`，并按引擎的
**mode 名**（不是 constraint 名）写 `SW.AITargeting`：

| 建筑 | 模式 |
| --- | --- |
| `NAMISL` | `nuke` |
| `GAWEAT` | `lightningstorm` |
| `YAPPET` | `psychicdominator` |
| `YAGNTC` | `geneticmutator` |
| `GACSPH` | `offensive` + `SW.AITargeting.Constraints=offensive_cell_set` |
| `NAIRON` | `ironcurtain` + `Constraints=defensive_cell_set` + `SW.AIRequiresHouse=owner` + `SW.AIRequiresTarget=units` + `SW.AffectsHouse=owner` |

> 旧 `mod/SuperAI` 把 `SW.AITargeting` 写成 `offensive_cell_clear` 等
> **constraint 名**；VERA 的 `superweapon_targeting.rs:426-462` 只把 mode 名写进
> `mode`，未知值保留原值。因此新模组改用合法 mode，并在 Stage 2 实测。

## 4. Stage 1 构建结果

| 项 | 值 |
| --- | --- |
| TaskForces | 134（零售 132；拆 2 个混合 TF 新增 2 个纯空 TF） |
| TeamTypes | 165（零售 163；新增 2 个纯空 Team） |
| ScriptTypes | 89（零售 88 + `ZAIATK-CY`） |
| AITriggerTypes | 182 |
| 混合 TF | 仅 `0617909C-G`（运输队，白名单） |
| MCV 队 | 3 |
| 超武队 | 9 |
| 使用 `ZAIATK-CY` 的队 | 131 |
| 纯空队提升 | 20（机场队只保留 2 支 `Max=1`，其余 `Max=0`） |
| condition-4 下限钉死 | 55 |
| `BuildLimit` | 12 个目标段全部移除（3 yards + 3 MCV + 6 超武） |
| yards 直接建造 | `AIBuildThis=yes` 保留基地种子；`AIBuildThis=no` 实验失败（AI 只造电厂/防御），已回退 |
| 重建延迟 | `AIRestrictReplaceTime=15`（1 秒） |
| Stage 1 计划目标 | 4 厂 / 每类 3 超武 |
| 单图 probe | `SuperAI-IceLake-120-NoOre.yrm`，exit 0，starts=120 |

## 5. 风险与 Stage 2 观测清单

**风险**
- **1 秒延迟不是精确上限**：它是 `AIRestrictReplaceTime`，只延迟“丢失节点重规划”，
  不阻止 `Factory_AI` 新建；它能减轻超额建造/重建抖动，但 AI 仍可能超过 20。
- `BuildLimit` 已移除；玩家侧边栏也不再受 20/1 的限制，可以造更多 MCV/超武。
- `GACNST/NACNST/YACNST AIBuildThis=yes` 是基地计划种子，不能设为 no；否则 AI 只造电厂/防御。
  平地 yard 仍可能出现，1 秒延迟只能缓解；要彻底禁止需引擎层区分“种子”和“额外直接建造”。
- `AIBuildCounts` 是计划目标，不是实时上限；建筑被摧毁后仍会重建。
- 1 秒延迟可能让被打残的 AI 恢复更慢；Stage 2 需要观察战局节奏。
- 动作 46 的 dense index 依赖纯官方 `[BuildingTypes]`；以后加建筑必须重新断言。
- 运输队 `0617909C-G` 是唯一混编白名单；其它混编会被构建断言拒绝。
- `BuildSpeed` 在抽取源码中没有读取者；`.025` 沿用旧值，Stage 2 做对照。

**Stage 2 观测**
1. 中期/后期 FPS；1 秒延迟是否把超额建造控制在可接受范围。
2. 记录**实测最大同时存活**的建造厂数/超武数；不设“≤20”验收，因为当前不是硬上限。
3. 进攻队是否先拆建造厂；拆完后是否继续打工厂/建筑。
4. 空地混编是否为 0（运输队除外）。
5. 铁幕/超时空/核弹/闪电是否实际释放。
6. 间谍/超时空突击队是否出现。
7. 是否还有家里囤兵、基地堵车、拉锯死局。
8. 若 1 秒不够：试 30/45 帧；若副作用太大：回到 0 或 5/10 帧。
