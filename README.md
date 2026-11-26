# VERA20K-SuperAI —— 为「看 AI 打 AI」而生的混战模组

[![repo](https://img.shields.io/badge/GitHub-VERA20K--SuperAI-blue)](https://github.com/wulusai2333/VERA20K-SuperAI)
[![Super AI](https://img.shields.io/badge/Super%20AI-v3.13.10-green)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Mass Skirmish](https://img.shields.io/badge/Mass%20Skirmish-v0.1.0-orange)](mod/MassSkirmish/mod.ini)

> **VERA20K-SuperAI 不是竞技 AI。** 它面向「电子斗蛐蛐」与观战：把 8 / 30 / 120 家电脑放进同一张地图，
> 让它们带满编部队互相撞在一起。不追求胜率最高、微操极致或冷冰冰的最优解，更在意多方势力交火时的
> **进攻欲望、兵种碰撞与战场观赏性** —— 每局要打得**热闹、胶着、充满戏剧张力**。
>
> 一局"好"的判据不是谁赢，而是：前 5 分钟打起来了、10 分钟还在拉锯、有一家挨打后翻了回来、
> 满屏一直有仗在打。为此我们刻意接受非最优：铺满地图持续进攻、超武充满就放、全员冲锋 FFA 乱战。
>
> 默认模组是 **Mass Skirmish AI**（`mod/MassSkirmish`，0.1.0 / Stage 1，纯净官方 INI 生成）：
> `tools/install.py` / `tools/check.py` 不带 `--mod` 就装/验它；旧的调参模组 **Super AI**（3.13.10）
> 需显式 `--mod SuperAI`。完整理念见 [docs/philosophy.md](docs/philosophy.md)。

> English summary: a spectator-first AI mass-battle mod for VERA20k. It is not a
> competitive AI — it does not chase the highest win rate, perfect micro, or the
> coldest optimal solution. It optimises for aggression, unit collisions and how
> the battle reads on screen: 8 / 30 / 120 computer players on one map, colliding
> at full army strength. A good match has a fight inside five minutes, a
> tug-of-war at ten, a comeback after somebody gets mauled, and something burning
> all the time. The default mod is **Mass Skirmish AI** (no `--mod` needed);
> the older tuning mod **Super AI** needs `--mod SuperAI`.

![Super AI Flat 200](previews/flat200.png)

## 这不是竞技 AI

它不追求胜率最高，不追求微操极致，也不追求冷冰冰的最优解。它面向**「电子斗蛐蛐」与观战场景**：
把 8 / 30 / 120 家电脑放进同一张地图，让它们带满编部队互相撞在一起。更在意的是多方势力交火时的
**进攻欲望、兵种碰撞与战场观赏性** —— 每局要打得**热闹、胶着、充满戏剧张力**（拉锯、翻盘、
满屏单位互撞、基地被打穿又重新铺起来）。

一局"好"的判据不是谁赢，而是：

- **前 5 分钟有没有打起来** —— 开局不能是各建各的家。
- **10 分钟有没有拉锯** —— 一边倒不算好局。
- **有没有哪一家挨打后翻回来** —— 翻盘是最好看的部分。
- **满屏是不是一直有仗在打** —— 中间空两三分钟，观感就断了。

为此我们刻意接受非最优：铺满地图持续进攻、超武充满就放（被打掉就重建）、全员冲锋 FFA 乱战、
观战位无敌 + 全图常亮 + 错峰 All to Hunt、数据改动可复现可审计。完整版见
[docs/philosophy.md](docs/philosophy.md)。

如果你要的是能赢的 AI，这个项目不是；要的是一局值得录下来、看着爽的混战，那它就是了。

## 两个模组

本项目面向 [VERA20k](https://github.com/YuriPlanet/vera20k)（YR 的开源重制引擎），
由两个模组与一套地图包组成。两个模组都只改规则与 AI 脚本，不替换任何美术资源：

| 项 | Mass Skirmish AI | Super AI |
| --- | --- | --- |
| 定位 | **默认模组** | 旧调参模组 |
| 版本 / 阶段 | `0.1.0` / Stage 1 | `3.13.10` |
| 数据来源 | **纯净官方** `rulesmd` / `aimd` / `artmd` / `mpmodesmd.ini`，经 `tools/build_mass_skirmish.py` 生成，**不覆盖** `mod/SuperAI` | 零售数据上的数值与流程改造，经 `tools/build_mod.py` 生成 |
| 规模 | 120 人混战 | 8 / 30 / 120 人观战图 |
| 安装 / 校验 | 不带 `--mod`（`tools/install.py` / `tools/check.py` 默认就是它） | 显式 `--mod SuperAI` |

- **SuperAI 地图包**：7 张地图，从 1v7 观战图到 30 人 / 120 人超大混战图（含一张纯平雪地 120 人图）。

## 快速开始

前置：VERA20k 本体 + 一份可用的 YR 游戏数据（`ra2.mix` 等），Ares 设为 **Auto** 或 **On**。

```bash
git clone https://github.com/wulusai2333/VERA20K-SuperAI.git
cd VERA20K-SuperAI
python -m pip install -r tools/requirements.txt   # 只有 lzokay，重建地图时才需要
python tools/install.py --game-dir "<游戏目录>" --enable                 # 默认装 Mass Skirmish AI
python tools/install.py --game-dir "<游戏目录>" --enable --mod SuperAI   # 旧调参模组
python tools/check.py   --game-dir "<游戏目录>"   # 可选：无头校验模组与 7 张地图
```

`--enable` 会备份并改写 `config.toml` 里的 `mod = "MassSkirmish"`（装旧调参模组时是
`mod = "SuperAI"`）。也可以手动把 `mod/MassSkirmish` 复制到 `<游戏目录>/Mods/`、把
`maps/*.yrm` 复制到 `Maps/`，再在 **选项 → 模组** 里选择「Mass Skirmish AI」（旧调参模组选「超级AI」）。

启动后：

1. **单人游戏 → 遭遇战**
2. 地图选 **Super AI Ice Lake 1v7 No Ore**（或任意一张 Flat 图）
3. 自己坐 **Start 1**，加 7 个电脑、难度 **冷酷**、队伍 **关闭（FFA）**
4. 游戏选项：基地开、快速游戏 **关**、战争迷雾 **关**、资金 10000–100000
5. 开始。1 秒后全图自动点亮，基地车自动套铁幕，不需要输入任何指令

详细步骤见 [docs/spectator-guide.md](docs/spectator-guide.md)。

## Mass Skirmish AI（默认模组）

`mod/MassSkirmish`，0.1.0 / Stage 1。构建起点是**纯净官方** `rulesmd` / `aimd` / `artmd` /
`mpmodesmd.ini`，由 `tools/build_mass_skirmish.py`（+ `tools/mass_skirmish_aimd.py`）生成，
只改规则与 AI 脚本、不替换任何美术资源，**不覆盖** `mod/SuperAI`。

`--profile stage1` 的关键参数（全部是**计划目标**，不是实时硬上限）：

| 项 | stage1 值 |
| --- | --- |
| 建造厂目标 | **4 座**（`build-report.txt` 的 `base_target=4`） |
| 超武 `AIBuildCounts` | **每类 3 座**（计划目标，不阻止 AI 继续建） |
| 维修厂 | `AIBuildThis=yes`（解锁 MCV，基地被打掉才能重建） |
| 重建节流 | `AIRestrictReplaceTime=15`（15 fps 下 1 秒，只是节流） |

产物可逐字节复现：`mod/MassSkirmish/build-report.txt` 记录构建参数、计数与五个文件的 SHA256，
重复构建逐字节一致。设计取舍见 [docs/mass-skirmish-design.md](docs/mass-skirmish-design.md)。

## Super AI（旧调参模组）

旧的调参模组 **SuperAI** 当前版本 **3.13.10**：电脑会被打到就立刻重建、把基地铺到 3 个、超武（核弹/闪电/心灵/基因/铁幕/超时空）
充满即用；本模组**不造围墙**，冷酷难度给到 3 兵营 / 5 战车工厂。玩家手里有四个核弹超武，
分别显示 **核弹攻击 / 核弹炮艇 / 空中炮艇 / 集束炮艇**。

### 经济与建造

| 项 | 原版 | SuperAI |
| --- | --- | --- |
| AI 开局资金 | `MultiplayerAICM=400,0,0` | **×1001**（按当前资金追加 1000 倍；10 万开局 → 约 1 亿） |
| 全局建造速度 | `BuildSpeed=.7` | **`.025`（玩家同样生效）**<br>注：该键的读取路径未在引擎抽取源码中确认，见 [playbook §1.5](docs/ai-tuning-playbook.md#15-死键清单) |
| 建筑规划 | 每种 1 个 | **只给 6 个生产建筑**：冷酷 **3 个兵营 / 5 个战车工厂**（`AIBuildCounts=3,1,1` / `5,1,1`），中等/简单保持 1 个 |
| 基地防御 | 25 / 20 / 6（苏、尤里 25 / 22 / 6） | **原版值，未改**；想要更大基地就只调这里（防御节点沿周长向外找位置） |
| **空军** | 11 支空军队伍全部 `Max=1`（同时最多一支）、每支 1–4 架、权重 40–70；且触发器会因战损失败把权重砸到 30 的地板（「打完很久不造」的真因） | 机场型飞机（入侵者/黑鹰）**每队 4 架、`Max=3`**（4 架正好一座空指部的 4 个位，超了会起飞坠毁）、`AirstripLimit` 0→4（抽取源码里没有该键的读取者，机库增加未实测，见 playbook §16）；基洛夫 6–8 架 `Max=6`；火箭飞行兵每队 6 人 `Max=6`；权重 **×3 并钉死**（三档同值，钳制区间退化为一点，失败不再衰减）；空队伍解散延迟 900→2400 |
| **防空部队** | 只有 46/165 条触发器带防空单位 | 防空触发器权重 **×2**：带防空队伍在抽签中的权重占比约 28% → 44% |
| **防空比例** | 盟/苏防空炮只在「air 类别」被选中（`AntiInfantryValue=0`/`AntiArmorValue=0`） | **3.11.6 已回退零售 `0/0/25`**：AI 先按敌方三类造价份额选类别，盟/苏防空炮只在 air 类别候选，防空建筑占比回到零售的 12–17%；这是引擎行为，配置改不动。防空**部队**仍由触发器权重 ×2 提升 |
| **被打掉就重建** | `AIRestrictReplaceTime=400`（约 27 秒内只补墙/防御/电厂） | **`0`**：任何建筑丢失后立刻重建，扩建由此被动发生 |
| **基地数量** | 1 座建造厂 | **稳定 3 座**：建造厂 < 3 时立刻补基地车去展开（`… MCV - Expand` 触发器，权重 5000；MCV 队伍 `Max=1`，一次只跑 1 台），被打掉会补回 |
| **核弹飞艇投放** | 无 | 玩家专属超武 `ZAINukeGunshipDrop` / `ZAINukeGunship2Drop` / `ZAINukeGunship3Drop`（`Type=UnitDelivery`）：点地面即把对应的飞艇投下来（载荷键是 `Deliver.Types`、`SW.AllowAI=no`、`SW.AlwaysGranted=yes`、`SW.InitialReady=yes`）；不碰任何公共表 |
| **四个核弹超武的名字** | 只有一个「核弹攻击」 | 无限核弹仍叫 **核弹攻击**；三艘飞艇的投放按钮叫 **核弹炮艇** / **空中炮艇** / **集束炮艇**。`UIName=` 是 CSF 标签而不是文字，所以模组自带一张 `ares.csf` 提供这几行（Ares 游戏在 `ra2md.csf` 之后追加它，与界面语言无关；缺了它游戏里会画成 `MISSING:'…'`） |
| **飞艇索敌范围** | — | 三艘飞艇都是 `GuardRange=200` + 武器 `Range=200`（`Range` 只是武器射程；两者必须相等，否则会追着打不到的目标转） |
| **核弹落点特效** | 闪白 + 把整张地图的光照重算一遍 | 飞艇的弹头一律用零售 `[NUKE]` 的克隆段（`ZAINukeMissileWH`）而不是零售 `[NUKE]` 本身：引擎按**弹头名字** `strcmpi(warhead,"NUKE")` 触发核弹特判，换名后只剩 `AnimList=NUKEANIM` 的蘑菇云，伤害与爆炸半径与零售核弹完全一致 |
| **集束炮艇（第四个超武）** | 无 | 空中炮艇的射速（`ROF=9`、`Range=200`、`Sight=200`）+ **4 发齐射**（`Burst=4` + 四个 `BurstDelay0..3=0`，约 0.27 秒）：每发母弹落在点击点外 0–200 格任意处，**本身是一颗 10 格核爆**（`ZAINukeMissileWH`、`NUKEANIM`、不闪白）；爆开时各分裂 **1 颗**追踪子弹，4 颗全部飞回**点击点** ±3 格炸开（`Splits=yes`、`Cluster=1`、`AroundTarget=yes`）。结果 = **4 母 + 4 子 = 8 个弹头**、**5 个落点**（4 个随机核爆 + 1 个被集火的点）。为什么是 4 不是 8：`Burst` 每 tick 一发、默认间隔 3–5 帧、单位只有 4 个 `BurstDelay` 槽 |
| **三艘炮艇的造价** | 战车工厂 2000 | **核弹炮艇 1000000 / 空中炮艇 100000 / 集束炮艇 10000000**。本模组 `BuildSpeed=.025` 是全局的，建造时间 ≈ `Cost × .025 × .9` 帧（150 秒 / 25 分钟 / ~4.2 小时），所以这三档价格实际等于"只能靠投放超武拿"；投放超武不看 `Cost=` |
| **玩家核弹** | 要造发射井、每 10 分钟一发 | **0 号位玩家无限核弹**：新增独立超武类型 `ZAIUnlimitedNuke`（`SW.AlwaysGranted=yes` 免发射井、`RechargeTime=0.01` ≈0.6 秒、`SW.AllowAI=no`；写 0 会被引擎当成"未设置"回落到 10 分钟）；**电脑的 `NukeSpecial` 原封不动**，照旧 10 分钟一发 |
| **超级武器** | 充满后 AI 不放 | **充满即自动发射**：给 AI 可造的 6 个带目标超武写 `SW.AutoFire=yes` / `SW.UseAITargeting=yes`（Ares 超武扩展） |
| 围墙占防御 | 50 / 25 / 10 | **`AIPickWallDefensePercent=0,0,0`**：AI **完全不造围墙**（墙会占防御名额又堵路），防御抽签全部落到真枪 |
| 额外矿场 | 2 / 1 / 0 | **`AIExtraRefineries=0,0,0`** |
| 奴隶矿工 | 4 / 3 / 2 | **`AISlaveMinerNumber=2,2,2`**（尤里：矿场复制数，也决定 `YAREFN` 能否就地重建） |
| 维修厂 | `AIBuildThis=no` | **`yes`**（`GADEPT`/`NADEPT`/`YADEPT`，AI 因此能造基地车） |
| 矿场收入 | 无 | **每 4 秒 +100**（无矿地图也能运转） |
| 建造厂 | 无雷达 | **`SpySat=yes`**（展开即全图，不耗电） |

### 进攻

| 项 | 原版 | SuperAI |
| --- | --- | --- |
| 组队间隔 `TeamDelays` | 2000/2500/3500 帧 | **300/450/600 帧（困难 20 / 中等 30 / 简单 40 秒）** |
| 同时队伍上限 | 30 | **10**（每户） |
| 进攻队编制 | 基准 | **原版规模**（65 支作战队伍，不再 ×2；苏联装甲 7、天启 4、盟军超硬 13） |
| 进攻触发器权重 | 70 / 下限 10 | **67 个进攻触发器 250 / 下限 150，三难度全开** |
| 集结行为 | 先回基地、再到敌方基地外集结 | **不集结，出生即冲锋**（151 支队伍改用 `ZAIATK01-G`；3 支 MCV 队伍保留原版 `043F23CC-G` 移动并展开；9 支带铁幕/超时空动作的队伍保留零售脚本） |
| 守家队伍 | 2 支 | **0 支**（全部队伍都是进攻队；`UseMinDefenseRule=no` 必须配套，否则 AI 一兵不发） |
| 中后期囤兵 | 无处理 | **地图触发器每 60 秒 All to Hunt** |

- [docs/boundaries-and-lessons.md](docs/boundaries-and-lessons.md)：边界手册 —— 动手前先确认改动属于地图/玩家/全局哪一级，附已验证的正确路径与黑名单

## 地图包

| 地图 | 可玩区 | 出生点 | 玩家位 | 触发器 |
| --- | --- | --- | --- | --- |
| **Super AI Ice Lake 1v7** | 176×114 | 8 | 可玩区外右侧 | 揭图 + 铁幕 + 猎杀 |
| **Super AI Ice Lake 1v7 No Ore** | 176×114 | 8 | 可玩区外右侧 | 揭图 + 铁幕 + 猎杀，无矿 |
| **Super AI Ice Lake 120 No Ore** | 176×114 | 120 | **右上角 (180,27) 独占** | 揭图 + 铁幕 + 猎杀（120 槽），无矿 |
| **Super AI Flat 200** | 200×200 | 8 | 普通角落 | 揭图 + 铁幕（1 秒起）+ 猎杀 |
| **Super AI Flat 30** | 250×250 | 30 | 可玩区左下角 (19,256) | 揭图 + 铁幕（1 秒起）+ 猎杀 |
| **Super AI Flat 120** | 500×500（引擎上限） | 120 | 可玩区左下角 (19,506) | 揭图 + 铁幕（1 秒起）+ 猎杀 |
| **Super AI Flat Snow 120 Center** | 300×300（菱形全平） | 120 | **正中 (150,150)** | 揭图 + 铁幕（开局即罩、每 10 秒）+ 猎杀 |

所有 Flat 地图的地形都是**同一块平地**：没有水、海岸线、高地、悬崖、树、石头、矿石、
中立建筑，建筑可以任意摆放。`Flat30/120/200` 用草地砖 `tile 418 / z=4`；
**`Flat Snow 120 Center`** 用雪地砖 `tile 696 / z=1`。

**Flat Snow 120 Center** 由 `IceLake 120 No Ore` 改造而来：43080 格**全部**改成雪地
（`696/0/1`），`OverlayPack`/`Terrain`/`Structures`/`Units`/`Infantry`/`Aircraft`/`Smudge`/
`CellTags`/`Preview` 全部清空，玩家放**地形正中 (150,150)**、开局就被铁幕罩住，
119 个电脑用最远点采样铺满全图，**玩家周围 12 格内不生成电脑**（实测最近 23 格），电脑之间最近邻 **22–33 格**（`assert_flat120` 每次构建都复核这两条间距）。

**Ice Lake 120** 是同一张冰湖图的 120 人版：**地形一格没动**
（`IsoMapPack5` 逐字节相同，43080 格），只改了出生点列表 —— 玩家仍站原 `wp0`（右上角
高台），119 个电脑全部铺在玩家的左下方向、落脚于原图 7 个电脑出生点所站的同一块冰面
（`tile 696` / 高度 1），用最远点采样铺开，相邻间距 11–19 格（大致相等，且按你的要求
不预留扩张空间）。

## 已验证

### Mass Skirmish AI（默认模组）

| 项目 | 结果 |
| --- | --- |
| 单图无头 probe | `tools/check.py --only-map SuperAI-IceLake-120-NoOre.yrm` → `all maps OK`，`349638 bytes  starts=120` |
| 产物可复现 | 五个文件重复构建**逐字节一致**，SHA256 记在 [`mod/MassSkirmish/build-report.txt`](mod/MassSkirmish/build-report.txt) |

### Super AI（旧调参模组）

| 项目 | 结果 |
| --- | --- |
| 模组重建 | `rulesmd.ini` / `artmd.ini` / `aimd.ini` 与发布版**逐字节一致** |
| 地图重建 | Ice Lake 三张、Flat 30、Flat 120 逐字节一致；Flat 200 仅差一处空行换行符 |
| 无窗口加载 | 7 张图 `--probe` 均 exit 0（`--mod SuperAI`，2026-11-26 实测），出生点按文件名排序 120 / 8 / 30 / 120 / 120 / 8 / 8 |
| 8 人局 | 隐藏窗口 100 秒：**1029 栋建筑**，防御 320 栋，全程无掉速 |
| 30 人局 | 29 AI + 玩家，**30 个 MCV 全部生成**，30 秒 1182 栋 |
| 120 人局 | 119 AI + 玩家，**120 个 MCV 全部生成**，30 秒 3418 栋 |

重建与校验命令见 [docs/build.md](docs/build.md)。

表中 1029 栋 / 320 防御 / 每种 60 这类数字来自 2.2 之前的配置，只作历史记录；
2.2 起 `AIBuildCounts` 改成分级，2.4 直接清空回到原版节奏，它们不再代表当前配置。

## 已知限制

### Mass Skirmish AI（默认模组）

以下 6 条都出自 [docs/mass-skirmish-design.md](docs/mass-skirmish-design.md) 与
[`mod/MassSkirmish/build-report.txt`](mod/MassSkirmish/build-report.txt)，按原文口径写，不美化：

- **`AIBuildCounts` 是基地计划目标，不是实时硬上限**。AI 会继续建，建筑被打掉还会重建。
- **`BuildLimit` 已从 3 个建造厂 / 3 辆 MCV / 6 个超武删除**：VERA20k 的 AI 工厂不执行它，
  它只限制玩家侧边栏；删掉这 12 处后，玩家侧也不再受这些上限约束。
- **建造厂必须保持 `AIBuildThis=yes`**：它是 AI 基地计划的种子，设为 `no` 会让 AI 只造电厂/防御，
  已实测失败并回退。
- **`AIRestrictReplaceTime=15`（1 秒）只是节流，不是硬上限**：它只延迟"丢失建筑节点的重新规划"，
  不阻止 AI 工厂新建。
- **扩厂触发器的条件（stage1 `< 4`，max 档 `< 20`）是目标，不是上限**。
- **Stage 2 的实机帧率 / 观感联调尚未执行**。这是最重要的一条诚实声明：现有数据只到"单图无头
  probe 通过"与"重复构建逐字节一致"，还没有一局实机的帧率与观感结论。

### Super AI（旧调参模组）

这些是配置解决不了、或者必须满足前置条件的边界，写在这里避免误解：

- **基地规模就是计划节点数，建完就停**。基地计划整局只生成一次，每个节点一栋建筑；
  节点放完，即使还有平地也不会再铺 —— **扩张靠「打掉就重建」被动发生**。
  没人打它，基地就静止。这是 2.4 的设计取舍，不是故障。
  想让基地本身更大，只调 `*BaseDefenseCounts`；不建议再动 `AIBuildCounts`。
- **基地数量固定铺到 3 座**。建造厂少于 3 时，扩建触发器会补基地车去展开（`Max=1`，
  同一时间只有一台在路上，展开后再抽下一台）。代价：不满 3 座期间该户暂停组建新的进攻队，
  已在场的部队不受影响。想让它更激进就去打掉它的建造厂 —— 它会优先补回来。
- **触发器不能下建造令**。`[AITriggerTypes]` 只能组队，所以「造建筑」只有计划节点一条路。
- **铁幕 / 超时空由「队伍脚本」施放，不是超武 AI**。引擎里这两个超武的唯一使用路径是
  队伍脚本动作 `53`（集结到敌方基地）→ `55`（放铁幕）/ `57`（超时空传送）→ `49`（进攻），
  零售数据已配好（`Soviet Iron Curtain Team`、`Allied Chrono-Sphere Unit`，触发条件 5/6、权重 5000）。
  所以它们**只在有队伍被拉出来时才会放**；纯防守、没有成队出击的 AI 不会用。
  本模组会保留这些脚本（`assert_superweapon_teams_intact` 守着），改 AI 脚本时不要把它们一起换掉。
- **超武发射不写日志**。只有 `superweapon::force_shield` 会打日志，核弹/铁幕/超时空的发射
  一条都不写；录像也只存本地玩家指令。所以「AI 到底放没放超武」只能进游戏看，
  不要指望用日志或工具验证（`docs/ai-tuning-playbook.md` §13.1.2 记录了三条失效的判定器）。
- **AI 造基地车是有前提的**。引擎本来就有这条路：3 个「自己 0 座建造厂」的触发器
  （权重 5000 = 引擎的接管权重，命中即清空其它触发器）拉起 3 支 MCV 队伍，
  走原版 `043F23CC-G` 移动并展开脚本。
  真正把它堵死的是零售给维修厂的 `AIBuildThis=no`——AI 造不出 `GADEPT` / `NADEPT` / `YADEPT`，
  而 `AMCV` 需要 `GAWEAP`+`GADEPT`、`SMCV` 需要 `NAWEAP`+`NADEPT`、`PCV` 需要 `YAWEAP`+`YAGRND`，
  所以以前 AI 再富也造不出 MCV，建造厂被拆掉就是永久损失；本版把三个维修厂改为可建。
  剩下的真实限制：AI 手里得同时有可用的战车工厂和维修厂，MCV 还要找到干净的 4×4 空地
  才展得开，日志里的 `MCV deploy blocked at origin` 记的就是这些失败。
- **引擎的类型注册表沿用原版数量**（`[VehicleTypes]` 85 项），新增单位类型不会生效，
  所以本项目不新增单位，只改既有数据。
- **建造速度是全局的**，玩家也会变快。
- **规则改动会让旧录像失效**；联机时所有人必须使用完全相同的模组与地图。
- **观战图必须坐 Start 1**：All to Hunt 触发器只作用于 1 号位之后的 AI 槽位。
- **无法用触发器自动展开玩家的 MCV**：这个引擎没有“部署”动作，且会跳过本地玩家
  在地图里自带的建筑。Flat 30/120 已把 Start 1 放在可玩区内的空地（3×3 完全可放），
  进图按一次 `D` 即可展开；铁幕从第 1 秒开始覆盖该位置。

## 兼容性

- 目标引擎：VERA20k（`mod.ini` 声明 `Ares=yes`，依赖 Ares 扩展键）。
- 需要完整的 YR 规则与 AI 文件作为基底，仓库中的 `rulesmd.ini` 等即为完整替换文件。
- 本项目不包含任何原版美术、音频或影片资源；地图仅包含地形与触发器数据。

## 项目结构

```
VERA20K-SuperAI/
├── mod/MassSkirmish/      # 默认模组：纯净官方 INI 生成的 Stage 1 计划
├── mod/SuperAI/           # 旧调参模组：mod.ini + rulesmd/artmd/aimd.ini
├── maps/                  # 7 张 .yrm
├── tools/
│   ├── build_mass_skirmish.py  # 从纯净官方 INI 生成 Mass Skirmish（默认模组）
│   ├── mass_skirmish_aimd.py   # Mass Skirmish 的 AI 脚本生成器
│   ├── build_mod.py       # 从原版 rules 目录重建模组
│   ├── build_maps.py      # 重建/改造地图（ice / ice120 / flat / uniform / info）
│   ├── veramap.py         # 地图 INI + IsoMapPack5 读写库
│   ├── install.py         # 安装到 VERA20k
│   ├── check.py           # 无窗口加载校验
│   ├── analyze_log.py     # 从 ra2.log 统计 AI 实际建成了什么
│   └── sed/               # 随机地图生成参数
├── docs/                  # 安装、观战、AI 设计、AI 调参、地图格式、排障、构建
└── previews/              # 地图预览
```

AI 设计取舍见 [docs/ai-design.md](docs/ai-design.md)，每个键该调到哪、怎么用日志验收见
[docs/ai-tuning-playbook.md](docs/ai-tuning-playbook.md)。

## 许可

- **工具与文档**：MIT，见 [LICENSE](LICENSE)。
- **规则/地图数据**：属于《命令与征服：尤里的复仇》衍生作品，
  版权归其权利人所有，仅用于非商业的模组与联机游玩。
  详见 [LICENSE](LICENSE) 的 NOTICE 部分。

## 致谢

- [VERA20k](https://github.com/YuriPlanet/vera20k) —— 引擎、地图格式与模组加载机制。
- 原版 Westwood / EA 的规则与 AI 脚本，本模组是在其基础上做数值与流程改造。
- `ice lake (1v7)` 地图作者 —— Ice Lake 两张观战图的地形来源。
