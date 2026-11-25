# 构建与校验

所有构建脚本只依赖 Python 3.11+ 与 [`lzokay`](https://pypi.org/project/lzokay/)：

```bash
python -m pip install -r tools/requirements.txt
```

脚本不会修改游戏本体；只有生成地图时会调用 `vera20k.exe`。

## 1. 重建模组

需要一个包含原版 `rulesmd.ini`、`artmd.ini`、`aimd.ini` 的目录
（YR 安装目录，或从 MIX 中提取出来的规则文件）：

```bash
python tools/build_mod.py --rules-dir "<原版规则目录>" --out mod/SuperAI
```

输出：

```
rules: AIBuildCounts on 6 building types (empty table = retail rhythm)
aimd : 151 team types charging, 9 kept their superweapon script, 6 MCV triggers re-armed
air  : 12 air teams (Max<=6, 12 raised), +8 aircraft, 11 air triggers weighted x3
aa   : 41 AA teams, 43 AA triggers weighted x2
nuke : [ZAINukeMissileWH] is retail [NUKE]'s 9 keys under another name, so the engine's NUKE block (screen flash + global relight) never runs
csf  : 3 label(s) in ares.csf (空中炮艇, 集束炮艇, 核弹炮艇)
cluster: 4 launches a trigger (all BurstDelays 0), each mother is a nuke and lands 0-200 cells off the aim point, then splits into 1 child that flies back to the aim point; 8 warheads, 5 landing points; Sight=200
```

`--no-art` 可以跳过 `artmd.ini`（本模组没有改它，引擎会回退到原版）。
发布版仍保留该文件，保证「整包替换」的行为一致。

构建还会写 `ares.csf` —— 模组自己的界面文字表，由 [tools/csf.py](../tools/csf.py) 生成，
内容来自 `build_mod.py` 的 `UI_LABELS`（`UIName=` 是 **CSF 标签**，不是文字；
标签查不到游戏会画 `MISSING:'…'`）。Ares 游戏在 `ra2md.csf` 之后追加这张表，
**与界面语言无关**，所以中文界面、英文界面都会显示这两个名字。
改名字只改 `UI_LABELS` 一处，然后重新构建。

## 2. 重建地图

所有地图在写出前都会把 `[Basic] GameMode=` 统一成：

```text
GameMode=standard, teamgame, megawealth, duel, meatgrind, navalwar
```

`ice` / `ice120` / `flat` 都用 `ensure_value` 写入（已有该键就替换，缺失就插在 `Name=` 后），
写出前再断言 6 个过滤名一个不缺，缺一个就 `SystemExit`、不写文件。原因：引擎的随机图导出把
`GameMode` 硬编码成 `standard`，不补这一步，重建一次就会把模式支持冲掉。`flat` 可以用
`--game-modes "..."` 覆盖写入值，但覆盖值仍必须包含这 6 个过滤名（可以追加别的），否则断言失败。
过滤名大小写敏感、必须全小写；`cooperative` 故意不加（Coop 类最多 2 人）。

### 2.1 Ice Lake（需要原始 1v7 地图）

原始地图 `ice lake (1v7).yrm` 属于第三方作品，不在仓库内。把它放到任意路径：

```bash
python tools/build_maps.py ice --src "ice lake (1v7).yrm" --out maps
```

会生成：

- `maps/SuperAI-IceLake-1v7.yrm`
- `maps/SuperAI-IceLake-1v7-NoOre.yrm`（删掉矿石/道路 overlay）

### 2.1.1 Ice Lake 120（**地形不动**，只改出生点）

```bash
python tools/build_maps.py ice120 \
    --src maps/SuperAI-IceLake-1v7-NoOre.yrm \
    --out maps/SuperAI-IceLake-120-NoOre.yrm
```

只做一件事：把 8 个出生点变成 120 个。**`[IsoMapPack5]`、`Size`、`LocalSize`、`Theater`
一字不动**（构建期会逐字节比对，改了就拒绝写出）。

- 玩家位沿用原 `wp0`（`(180,27)`）——这张图的 0 号位本来就在**右上角**，独占；
- 119 个电脑出生点只落在**原图 7 个电脑出生点所站的同一块冰面**上
  （`tile 696` / 高度 `1`，共 10528 格，其中玩家左下方向 10209 格），因此必然可站；
- 排布用**最远点采样**：先取离玩家最远的一格，再反复取"离已选点最远"的格子，
  铺满后把最靠近玩家的 4 个丢掉。实测相邻间距 **min 11 / 中位 13 / max 19 格**，
  基本等距；按需求不预留扩张空间。
- `--spacing N` 可以要求最小间距（会用不满 119 个名额，然后直接报错，不会静默少给）；
- `[Header]` 的 `WaypointN` / `NumberStartingPoints` 一并重写成 120
  （引擎的换算：`((x-y+512)/2, (x+y+1)/2)`，能精确复现原图 8/8 个出生点）；
- `[Basic]`：`MaxPlayer`/`MaxPlayers` 改 120。

构建期断言：地形/尺寸/剧场零改动、120 个出生点、玩家位不变、每个电脑点都在那块冰面上且
在玩家的左下方向、两两间距达标、`[Header]` 与 `[Waypoints]` 一致。
`--probe` 报告 `max_start_waypoints: 120` 才算通过。

### 2.2 Flat 系列（先生成底图）

用 VERA20k 的随机地图生成器：

```bash
vera20k.exe --generate-map --sed tools/sed/flat30.sed  --output Flat30-raw.yrm  --no-mod
vera20k.exe --generate-map --sed tools/sed/flat120.sed --output Flat120-raw.yrm --no-mod
vera20k.exe --generate-map --sed tools/sed/flat200.sed --output Flat200-raw.yrm --no-mod
```

> `flat200.sed` 需要 200 尺寸支持，见 [map-format.md](map-format.md#62-200200非标准尺寸)；
> 没有改过生成器时，用 250×250 代替即可。

再改造成纯平观战图：

```bash
# 200：与 30/120 同一套触发器（揭图 + 铁幕 + 猎杀），玩家出生点沿用原始航点
python tools/build_maps.py flat \
  --src Flat200-raw.yrm --out maps/SuperAI-Flat200.yrm \
  --name "Super AI Flat 200" --players 8 --triggers full \
  --terrain-newline crlf

# 30：揭图 + 铁幕（1 秒起）+ 猎杀，玩家在左下角内侧 4 格
python tools/build_maps.py flat \
  --src Flat30-raw.yrm --out maps/SuperAI-Flat30.yrm \
  --name "Super AI Flat 30" --players 30 --triggers full --player-inside 2

# 120：同上，500×500
python tools/build_maps.py flat \
  --src Flat120-raw.yrm --out maps/SuperAI-Flat120.yrm \
  --name "Super AI Flat 120" --players 120 --triggers full --player-inside 2
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--players` | 出生点数量；省略时从 `[Waypoints]` 读取 |
| `--triggers full\|hunt` | `full` = 揭图 + 铁幕 + 猎杀；`hunt` = 只加猎杀 |
| `--player-inside N` | 在可玩区菱形内扫出左下角、且 4×4 建造厂地基 + N 格余量放得下的格子（30/120 用 2） |
| `--move-player-corner` | 把 0 号位移到可玩区下方 `--corner-gap` 格（老方案，需先把 MCV 开进来） |
| `--tile` / `--sub` / `--height` | 统一地形参数，默认 418 / 0 / 4 |
| `--terrain-newline lf\|crlf` | 仅影响 `[IsoMapPack5]` 的换行，纯外观 |
| `--game-modes "..."` | 写入 `[Basic] GameMode=` 的过滤名，默认即上面的 6 个；覆盖值必须仍含这 6 个 |

### 2.3 只改地形

```bash
# 纯平雪地 120 人图：玩家在地形正中、119 家均布全图、物件全部清空
python tools/build_maps.py flat \
    --src maps/SuperAI-IceLake-120-NoOre.yrm \
    --out maps/SuperAI-FlatSnow-120-Center.yrm \
    --name "Super AI Flat Snow 120 Center" \
    --players 120 --tile 696 --sub 0 --height 1 --terrain-newline crlf \
    --player-center --spread 119

python tools/build_maps.py uniform --src raw.yrm --out flat.yrm --tile 418 --height 4
```

### 2.4 只补触发器

已有地图要换成同一套观战触发器（地形、出生点、其余段落逐字节保留）：

```bash
python tools/build_maps.py retrigger \
  --src maps/SuperAI-Flat200.yrm --out maps/SuperAI-Flat200.yrm \
  --players 8 --triggers full
```

### 2.5 模式名单：离线 Skirmish 也全列出

引擎在离线 Skirmish 里只列 Battle / FreeForAll 两个模式类（LAN 房间不过滤类）。
`mod/SuperAI/mpmodesmd.ini` 覆盖零售名单，把 4/5/6/7/8 这五行放进 `[Battle]` 段，
于是 9 个模式都会出现在离线 Skirmish 的游戏类型下拉里；`mod/SuperAI/mod.ini` 通过
`[Files] Modes=mpmodesmd.ini` 指定这份名单。

- 9 行 id 必须保持 **1..9 连续**，不能删行、跳号（联机 agreement 会按行数核对每个模式的覆盖 INI）；
- 每行仍是零售的 5 个字段：`UINameKey, TooltipKey, OverrideFile, MapFilter, RandomMapsAllowed`；
- 代价：4 号「邪恶联盟」退化成普通 Battle 类，失去"苏盟双 MCV"和 Bases=on 强制；
- 模式名单是联机 digest 的比较对象，联机双方必须用同一版本的模组；
- 地图 `GameMode` 第 4 字段与这里的 `MapFilter` 必须逐字一致（大小写敏感）。

## 3. 校验

```bash
python tools/check.py --game-dir "<游戏目录>"
```

它会对模组和 `maps/` 下所有 `.yrm` 跑 `--probe`，打印 `starts` 与错误。

单张地图的摘要：

```bash
python tools/build_maps.py info --src maps/SuperAI-Flat120.yrm
```

一次校验整包（`maps/` 下每张图的 `[Basic] GameMode=` 都要含全部 6 个过滤名，缺一个退出码非 0）：

```bash
python tools/build_maps.py modes --dir maps
```

## 4. 可复现性

发布版（v3.13.5）与仓库内的构建脚本结果：

| 产物 | 结果 |
| --- | --- |
| `mod/SuperAI/rulesmd.ini` | 逐字节一致 |
| `mod/SuperAI/artmd.ini` | 逐字节一致（原版复制） |
| `mod/SuperAI/aimd.ini` | 逐字节一致 |
| `mod/SuperAI/ares.csf` | 逐字节一致（`tools/csf.py` 按标签排序写出） |
| `SuperAI-IceLake-1v7.yrm` | 逐字节一致 |
| `SuperAI-IceLake-1v7-NoOre.yrm` | 逐字节一致 |
| `SuperAI-IceLake-120-NoOre.yrm` | 逐字节一致（用 2.1.1 的 `ice120` 重建） |
| `SuperAI-Flat30.yrm` | 逐字节一致 |
| `SuperAI-Flat120.yrm` | 逐字节一致 |
| `SuperAI-Flat200.yrm` | 逐字节一致（构建时加 `--terrain-newline crlf`） |

> v3.13.5 的地图带 20 秒 AIHunt；当前仓库已改为 60 秒，因此表中地图产物不再与
> v3.13.5 逐字节一致。`rulesmd.ini` / `aimd.ini` / `ares.csf` 仍一致。

模组构建依赖原版规则文件的字节内容；不同语言版本（`rulesmd.ini` 被本地化修改过）
会导致 `RULES_EDITS` 找不到原值而报错，这是有意的保护。

## 4.0 诊断用：队伍集结版（`--assembly-teams`）

```bash
python tools/build_mod.py --rules-dir "<原版规则目录>" \
    --out "<游戏目录>/Mods/SuperAI-assembly" --assembly-teams
```

**默认关闭，只用于诊断。** 它跳过"把 151 支队伍的脚本换成不集结脚本"这一步，
让 AI 恢复原版"先回基地集结、再成队出击"。产出的模组与正式版**只差这 160 行 `Script=`**，
其余（`rulesmd.ini`、`artmd.ini`、`aimd.ini` 的其它行）逐字节相同。

用途：判定"铁幕/超时空不放"到底是**我们的进攻逻辑消灭了 3×3 集群**，
还是**引擎没有对应的 AI 发射路径**。判定规则见
[ai-tuning-playbook.md §13.1.3](ai-tuning-playbook.md#1313-铁幕超时空一个是不是我们自己把机会弄没了的对照实验)。

## 4.1 规则键的「无头判定器」（tools/probe_rules.py）

```bash
python tools/probe_rules.py --game-dir "<游戏目录>" --selftest
```

想确认某个 INI 键到底被不被引擎解析时用这个工具：它把模组复制到临时的
`Mods/_probe`，改一处键、跑一次 `--probe`、比对 `rules_digest`，测完删掉临时目录。

用例文件：`tools/sw-cases.txt`（每一行 `键=值`，`-键` 表示删除该键，`[段名]` 切换段）。
`--log` 参数对 `tools/analyze_log.py` 是**必填**的，没有内置默认路径。

`--selftest` 会先做三个对照（改注释 / 改活键 `TeamDelays` / 改死键 `WarRatio`）。
**注意：目前的自检结论是"这个判定器不可用"** —— `rules_digest` 连注释都会影响，
说明它是文件哈希而不是解析摘要。工具因此会拒绝给出结论。
留着它是因为：换引擎版本后重跑一次，就能知道这个判定器有没有变得可用；
它也是「非法值一律被静默接受」这个事实的可复现证据。

## 5. 安装到游戏

```bash
python tools/install.py --game-dir "<游戏目录>" --enable
```

见 [install.md](install.md)。

## 6. 加一张自己的观战图

1. 生成底图（或找一张 8 人图）。
2. 用 `build_maps.py flat` 统一地形、加触发器。
3. 玩家位用 `--player-inside 2` 放在可玩区菱形内，保证 4×4 建造厂地基能落地；
   不要用可玩区外的位置，MCV 能生成但无法就地展开。
4. `check.py` 确认 `starts` 数量正确。
5. 在 `docs/spectator-guide.md` 的地图表里补一行。

如果地图本身有 `[Triggers]`，`add_triggers` 会拒绝覆盖。
需要先合并原有触发器，或删掉该段再构建。
