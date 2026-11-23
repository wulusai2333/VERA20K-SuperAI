# Super AI for VERA20k

[![repo](https://img.shields.io/badge/GitHub-VERA20K--SuperAI-blue)](https://github.com/wulusai2333/VERA20K-SuperAI)
[![mod version](https://img.shields.io/badge/mod-v3.0-green)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

把《红色警戒 2：尤里的复仇》遭遇战里的电脑，变成一个**会铺满地图、几乎全员冲锋、永不囤兵**的对手；
再附上一套专门为「看 AI 打 AI」设计的地图包（平地图 + 冰湖图）。

当前版本 **3.0**：电脑会被打到就立刻重建、把基地铺到 3 个、超武（核弹/闪电/心灵/基因/铁幕/超时空）
充满即用；本模组**不造围墙**，冷酷难度给到 3 兵营 / 5 战车工厂。

本项目面向 [VERA20k](https://github.com/YuriPlanet/vera20k)（YR 的开源重制引擎），
由两部分组成：

- **SuperAI 模组**：只改规则与 AI 脚本，不替换任何美术资源。
- **SuperAI 地图包**：7 张地图，从 1v7 观战图到 30 人 / 120 人超大混战图（含一张纯平雪地 120 人图）。

> English summary: a fan-made mod + spectator map pack for VERA20k. It gives the
> skirmish AI x1001 starting credits, an aggressive global build speed, a graded
> per-type building plan at the retail three-difficulty rhythm (no AIBuildCounts
> tuning), 25/20/6 base defences, instant rebuild of any destroyed building
> (`AIRestrictReplaceTime=0`) which is also how the base grows, a 10-team cap with
> retail-sized task forces, and a custom team script that skips the retail
> "regroup at base" steps. Repair depots are now AI-buildable, which is what
> finally lets the AI rebuild a lost MCV — its rebuild triggers carry the engine's
> 5000 priority weight, so a yardless house does exactly that. Maps are uniform
> flat stages with map triggers for full-map reveal, a permanent Iron Curtain on
> the spectator
> slot, and a periodic All-to-Hunt sweep.

![Super AI Flat 200](previews/flat200.png)

## 特性

### 经济与建造

| 项 | 原版 | SuperAI |
| --- | --- | --- |
| AI 开局资金 | `MultiplayerAICM=400,0,0` | **×1001**（按当前资金追加 1000 倍；10 万开局 → 约 1 亿） |
| 全局建造速度 | `BuildSpeed=.7` | **`.025`（玩家同样生效）**<br>注：该键的读取路径未在引擎抽取源码中确认，见 [playbook §1.5](docs/ai-tuning-playbook.md#15-死键清单) |
| 建筑规划 | 每种 1 个 | **只给 6 个生产建筑**：冷酷 **3 个兵营 / 5 个战车工厂**（`AIBuildCounts=3,1,1` / `5,1,1`），中等/简单保持 1 个 |
| 基地防御 | 25 / 20 / 6 | **原版 `25/20/6`**；想要更大基地就只调这里（防御节点沿周长向外找位置） |
| **空军** | 11 支空军队伍全部 `Max=1`（同时最多一支）、每支 1–4 架、权重 40–70；且触发器会因战损失败把权重砸到 30 的地板（「打完很久不造」的真因） | 机场型飞机（入侵者/黑鹰）**每队 3 架、`Max=3`**（停机位是硬约束：一座空指部 4 个位，超了会起飞坠毁）、`AirstripLimit` 0→4 让 AI 真的造机库；基洛夫 6–8 架 `Max=6`；火箭飞行兵每队 6 人 `Max=6`；权重 **×3 并钉死**（三档同值，钳制区间退化为一点，失败不再衰减）；空队伍解散延迟 900→2400 |
| **防空部队** | 只有 46/165 条触发器带防空单位 | 防空触发器权重 **×2**：带防空队伍在抽签中的权重占比约 28% → 44% |
| **防空比例** | 盟/苏防空炮只在「air 类别」被选中（`AntiInfantryValue=0`/`AntiArmorValue=0`） | **和尤里盖特机炮同形状（25/10/25）**：三类都是候选，防御总数不变、防空占比 12–17% → 20%+ |
| **被打掉就重建** | `AIRestrictReplaceTime=400`（约 27 秒内只补墙/防御/电厂） | **`0`**：任何建筑丢失后立刻重建，扩建由此被动发生 |
| **基地数量** | 1 座建造厂 | **稳定 3 座**：建造厂 < 3 时立刻补基地车去展开（`… MCV - Expand` 触发器，权重 5000；MCV 队伍 `Max=2`），被打掉会补回 |
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
| 组队间隔 `TeamDelays` | 2000/2500/3500 帧 | **300/450/600 帧（20/30/40 秒）** |
| 同时队伍上限 | 30 | **10**（每户） |
| 进攻队编制 | 基准 | **原版规模**（65 支作战队伍，不再 ×2；苏联装甲 7、天启 4、盟军超硬 13） |
| 进攻触发器权重 | 70 / 下限 10 | **67 个进攻触发器 250 / 下限 150，三难度全开** |
| 集结行为 | 先回基地、再到敌方基地外集结 | **不集结，出生即冲锋**（151 支队伍改用 `ZAIATK01-G`；3 支 MCV 队伍保留原版 `043F23CC-G` 移动并展开；9 支带铁幕/超时空动作的队伍保留零售脚本） |
| 守家队伍 | 2 支 | **0 支**（全部队伍都是进攻队；`UseMinDefenseRule=no` 必须配套，否则 AI 一兵不发） |
| 中后期囤兵 | 无处理 | **地图触发器每 20 秒 All to Hunt** |

### 地图

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

## 快速开始

前置：VERA20k 本体 + 一份可用的 YR 游戏数据（`ra2.mix` 等），Ares 设为 **Auto** 或 **On**。

```bash
git clone https://github.com/wulusai2333/VERA20K-SuperAI.git
cd VERA20K-SuperAI
python -m pip install -r tools/requirements.txt   # 只有 lzokay，重建地图时才需要
python tools/install.py --game-dir "<游戏目录>" --enable
python tools/check.py   --game-dir "<游戏目录>"   # 可选：无头校验模组与 7 张地图
```

`--enable` 会备份并改写 `config.toml` 里的 `mod = "SuperAI"`。
也可以手动把 `mod/SuperAI` 复制到 `<游戏目录>/Mods/`、把 `maps/*.yrm` 复制到 `Maps/`，
再在 **选项 → 模组** 里选择「超级AI」。

启动后：

1. **单人游戏 → 遭遇战**
2. 地图选 **Super AI Ice Lake 1v7 No Ore**（或任意一张 Flat 图）
3. 自己坐 **Start 1**，加 7 个电脑、难度 **冷酷**、队伍 **关闭（FFA）**
4. 游戏选项：基地开、快速游戏 **关**、战争迷雾 **关**、资金 10000–100000
5. 开始。1 秒后全图自动点亮，基地车自动套铁幕，不需要输入任何指令

详细步骤见 [docs/spectator-guide.md](docs/spectator-guide.md)。

## 项目结构

```
VERA20K-SuperAI/
├── mod/SuperAI/           # 模组：mod.ini + rulesmd/artmd/aimd.ini
├── maps/                  # 6 张 .yrm
├── tools/
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

## 已验证

| 项目 | 结果 |
| --- | --- |
| 模组重建 | `rulesmd.ini` / `artmd.ini` / `aimd.ini` 与发布版**逐字节一致** |
| 地图重建 | Ice Lake 三张、Flat 30、Flat 120 逐字节一致；Flat 200 仅差一处空行换行符 |
| 无窗口加载 | 6 张图 `--probe` 均 exit 0，出生点 120 / 8 / 30 / 120 / 8 / 8（按文件名排序） |
| 8 人局 | 隐藏窗口 100 秒：**1029 栋建筑**，防御 320 栋，全程无掉速 |
| 30 人局 | 29 AI + 玩家，**30 个 MCV 全部生成**，30 秒 1182 栋 |
| 120 人局 | 119 AI + 玩家，**120 个 MCV 全部生成**，30 秒 3418 栋 |

重建与校验命令见 [docs/build.md](docs/build.md)。

表中 1029 栋 / 320 防御 / 每种 60 这类数字来自 2.2 之前的配置，只作历史记录；
2.2 起 `AIBuildCounts` 改成分级，2.4 直接清空回到原版节奏，它们不再代表当前配置。

## 已知限制

这些是配置解决不了、或者必须满足前置条件的边界，写在这里避免误解：

- **基地规模就是计划节点数，建完就停**。基地计划整局只生成一次，每个节点一栋建筑；
  节点放完，即使还有平地也不会再铺 —— **扩张靠「打掉就重建」被动发生**。
  没人打它，基地就静止。这是 2.4 的设计取舍，不是故障。
  想让基地本身更大，只调 `*BaseDefenseCounts`；不建议再动 `AIBuildCounts`。
- **基地数量固定铺到 3 座**。建造厂少于 3 时，扩建触发器会补基地车去展开（`Max=2`，
  最多两台同时在路上）。代价：不满 3 座期间该户暂停组建新的进攻队，
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

## 发布到 GitHub

仓库已经初始化并提交（`main` 分支）。创建远端后：

```bash
git remote add origin git@github.com:<你的账号>/VERA20K-SuperAI.git
git push -u origin main
```

建议仓库描述写明「VERA20k / Yuri's Revenge fan mod + spectator maps」，
并在 README 保留许可与第三方地图来源说明。

## 许可

- **工具与文档**：MIT，见 [LICENSE](LICENSE)。
- **规则/地图数据**：属于《命令与征服：尤里的复仇》衍生作品，
  版权归其权利人所有，仅用于非商业的模组与联机游玩。
  详见 [LICENSE](LICENSE) 的 NOTICE 部分。

## 致谢

- [VERA20k](https://github.com/YuriPlanet/vera20k) —— 引擎、地图格式与模组加载机制。
- 原版 Westwood / EA 的规则与 AI 脚本，本模组是在其基础上做数值与流程改造。
- `ice lake (1v7)` 地图作者 —— Ice Lake 两张观战图的地形来源。
