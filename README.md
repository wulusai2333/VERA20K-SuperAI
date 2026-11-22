# Super AI for VERA20k

把《红色警戒 2：尤里的复仇》遭遇战里的电脑，变成一个**会铺满地图、全员冲锋、永不囤兵**的对手；
再附上一套专门为「看 AI 打 AI」设计的纯平地图。

本项目面向 [VERA20k](https://github.com/YuriPlanet/vera20k)（YR 的开源重制引擎），
由两部分组成：

- **SuperAI 模组**：只改规则与 AI 脚本，不替换任何美术资源。
- **SuperAI 地图包**：5 张地图，从 1v7 观战图到 30 人 / 120 人超大混战图。

> English summary: a fan-made mod + spectator map pack for VERA20k. It gives the
> skirmish AI x1001 starting credits, ~28x build speed, 60 planned copies of each
> production building, 100 base defences, doubled attack task forces, and a custom
> team script that skips the retail "regroup at base" steps. Maps are uniform flat
> stages with map triggers for full-map reveal, a permanent Iron Curtain on the
> spectator slot, and a periodic All-to-Hunt sweep.

![Super AI Flat 200](previews/flat200.png)

## 特性

### 经济与建造

| 项 | 原版 | SuperAI |
| --- | --- | --- |
| AI 开局资金 | `MultiplayerAICM=400,0,0` | **×1001**（按当前资金追加 1000 倍；10 万开局 → 约 1 亿） |
| 全局建造速度 | `BuildSpeed=.7` | **`.025`（约 28 倍，玩家同样生效）** |
| 建筑规划 | 每种 1 个 | **Ares `AIBuildCounts`：电厂/矿场/兵营/战车工厂各 60** |
| 基地防御 | 25 | **100** |
| 矿场收入 | 无 | **每 4 秒 +100**（无矿地图也能运转） |
| 建造厂 | 无雷达 | **`SpySat=yes`**（展开即全图，不耗电） |

### 进攻

| 项 | 原版 | SuperAI |
| --- | --- | --- |
| 组队间隔 `TeamDelays` | 2000/2500/3500 帧 | **45/60/90 帧** |
| 同时队伍上限 | 30 | **45** |
| 进攻队编制 | 基准 | **×2**（苏联装甲 7→14、天启 4→8、盟军超硬 13→26） |
| 进攻触发器权重 | 70 / 下限 10 | **250 / 下限 150，三难度全开** |
| 集结行为 | 先回基地、再到敌方基地外集结 | **不集结，出生即冲锋**（160 支队伍） |
| 守家队伍 | 2 支 | **0 支** |
| 中后期囤兵 | 无处理 | **地图触发器每 20 秒 All to Hunt** |

### 地图

| 地图 | 可玩区 | 出生点 | 玩家位 | 触发器 |
| --- | --- | --- | --- | --- |
| **Super AI Ice Lake 1v7** | 176×114 | 8 | 可玩区外右侧 | 揭图 + 铁幕 + 猎杀 |
| **Super AI Ice Lake 1v7 No Ore** | 176×114 | 8 | 可玩区外右侧 | 揭图 + 铁幕 + 猎杀，无矿 |
| **Super AI Flat 200** | 200×200 | 8 | 普通角落 | 仅猎杀 |
| **Super AI Flat 30** | 250×250 | 30 | 左下角可玩区外 | 揭图 + 铁幕 + 猎杀 |
| **Super AI Flat 120** | 500×500（引擎上限） | 120 | 左下角可玩区外 | 揭图 + 铁幕 + 猎杀 |

所有 Flat 地图的地形都是**同一块平地（tile 418）、同一高度（z=4）**：
没有水、海岸线、高地、悬崖、树、石头、矿石、中立建筑，建筑可以任意摆放。

## 快速开始

前置：VERA20k 本体 + 一份可用的 YR 游戏数据（`ra2.mix` 等），Ares 设为 **Auto** 或 **On**。

```bash
git clone <this repo> VERA20K-SuperAI
cd VERA20K-SuperAI
python tools/install.py --game-dir "F:/Games/VERA20K" --enable
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
├── maps/                  # 5 张 .yrm
├── tools/
│   ├── build_mod.py       # 从原版 rules 目录重建模组
│   ├── build_maps.py      # 重建/改造地图（ice / flat / uniform / info）
│   ├── veramap.py         # 地图 INI + IsoMapPack5 读写库
│   ├── install.py         # 安装到 VERA20k
│   ├── check.py           # 无窗口加载校验
│   └── sed/               # 随机地图生成参数
├── docs/                  # 安装、观战、AI 设计、地图格式、排障、构建
└── previews/              # 地图预览
```

## 已验证

| 项目 | 结果 |
| --- | --- |
| 模组重建 | `rulesmd.ini` / `artmd.ini` / `aimd.ini` 与发布版**逐字节一致** |
| 地图重建 | Ice Lake 两张、Flat 30、Flat 120 逐字节一致；Flat 200 仅差一处空行换行符 |
| 无窗口加载 | 5 张图 `--probe` 均 exit 0，出生点 8 / 8 / 8 / 30 / 120 |
| 8 人局 | 隐藏窗口 100 秒：**1029 栋建筑**，防御 320 栋，全程无掉速 |
| 30 人局 | 29 AI + 玩家，**30 个 MCV 全部生成**，30 秒 1182 栋 |
| 120 人局 | 119 AI + 玩家，**120 个 MCV 全部生成**，30 秒 3418 栋 |

重建与校验命令见 [docs/build.md](docs/build.md)。

## 已知限制

这些不是配置能解决的，写在这里避免误解：

- **每个 AI 的基地约 100 栋就停**。原因是基地选址的可用周长用完，属于引擎机制；
  换更大的图、减少 AI 数量可以缓解。
- **AI 不会主动造基地车扩张**。VERA 的 `AI_Choose_Building` 只按已有建造厂选建筑，
  没有「生产 MCV → 找地方展开」的代码路径；地图预置给 AI 的建造厂也会被引擎跳过。
- **引擎的类型注册表沿用原版数量**（`[VehicleTypes]` 85 项），新增单位类型不会生效，
  所以本项目不新增单位，只改既有数据。
- **建造速度是全局的**，玩家也会变快。
- **规则改动会让旧录像失效**；联机时所有人必须使用完全相同的模组与地图。
- **观战图必须坐 Start 1**：All to Hunt 触发器只作用于 1 号位之后的 AI 槽位。

## 兼容性

- 目标引擎：VERA20k（`mod.ini` 声明 `Ares=yes`，依赖 Ares 扩展键）。
- 需要完整的 YR 规则与 AI 文件作为基底，仓库中的 `rulesmd.ini` 等即为完整替换文件。
- 本项目不包含任何原版美术、音频或影片资源；地图仅包含地形与触发器数据。

## 许可

- **工具与文档**：MIT，见 [LICENSE](LICENSE)。
- **规则/地图数据**：属于《命令与征服：尤里的复仇》衍生作品，
  版权归其权利人所有，仅用于非商业的模组与联机游玩。
  详见 [LICENSE](LICENSE) 的 NOTICE 部分。

## 致谢

- [VERA20k](https://github.com/YuriPlanet/vera20k) —— 引擎、地图格式与模组加载机制。
- 原版 Westwood / EA 的规则与 AI 脚本，本模组是在其基础上做数值与流程改造。
- `ice lake (1v7)` 地图作者 —— Ice Lake 两张观战图的地形来源。
