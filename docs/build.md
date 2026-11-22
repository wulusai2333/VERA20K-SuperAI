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
python tools/build_mod.py --rules-dir "F:/Games/red2" --out mod/SuperAI
```

输出：

```
rules: AIBuildCounts on 21 building types
aimd : 65 attack teams, 160 charged, 60 task forces rescaled, 67 triggers boosted (1 shared task forces skipped)
```

`--no-art` 可以跳过 `artmd.ini`（本模组没有改它，引擎会回退到原版）。
发布版仍保留该文件，保证「整包替换」的行为一致。

## 2. 重建地图

### 2.1 Ice Lake（需要原始 1v7 地图）

原始地图 `ice lake (1v7).yrm` 属于第三方作品，不在仓库内。把它放到任意路径：

```bash
python tools/build_maps.py ice --src "ice lake (1v7).yrm" --out maps
```

会生成：

- `maps/SuperAI-IceLake-1v7.yrm`
- `maps/SuperAI-IceLake-1v7-NoOre.yrm`（删掉矿石/道路 overlay）

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
# 200：只加 All to Hunt，玩家在普通角落
python tools/build_maps.py flat \
  --src Flat200-raw.yrm --out maps/SuperAI-Flat200.yrm \
  --name "Super AI Flat 200" --players 8 --triggers hunt \
  --terrain-newline crlf

# 30：揭图 + 铁幕 + 猎杀，玩家移到左下角可玩区外
python tools/build_maps.py flat \
  --src Flat30-raw.yrm --out maps/SuperAI-Flat30.yrm \
  --name "Super AI Flat 30" --players 30 --triggers full --move-player-corner

# 120：同上，500×500
python tools/build_maps.py flat \
  --src Flat120-raw.yrm --out maps/SuperAI-Flat120.yrm \
  --name "Super AI Flat 120" --players 120 --triggers full --move-player-corner
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--players` | 出生点数量；省略时从 `[Waypoints]` 读取 |
| `--triggers full\|hunt` | `full` = 揭图 + 铁幕 + 猎杀；`hunt` = 只加猎杀 |
| `--move-player-corner` | 把 0 号位移到可玩区下方 `--corner-gap` 格（默认 3） |
| `--tile` / `--sub` / `--height` | 统一地形参数，默认 418 / 0 / 4 |
| `--terrain-newline lf\|crlf` | 仅影响 `[IsoMapPack5]` 的换行，纯外观 |

### 2.3 只改地形

```bash
python tools/build_maps.py uniform --src raw.yrm --out flat.yrm --tile 418 --height 4
```

## 3. 校验

```bash
python tools/check.py --game-dir "F:/Games/VERA20K"
```

它会对模组和 `maps/` 下所有 `.yrm` 跑 `--probe`，打印 `starts` 与错误。

单张地图的摘要：

```bash
python tools/build_maps.py info --src maps/SuperAI-Flat120.yrm
```

## 4. 可复现性

发布版（v1.9）与仓库内的构建脚本结果：

| 产物 | 结果 |
| --- | --- |
| `mod/SuperAI/rulesmd.ini` | 逐字节一致 |
| `mod/SuperAI/artmd.ini` | 逐字节一致（原版复制） |
| `mod/SuperAI/aimd.ini` | 逐字节一致 |
| `SuperAI-IceLake-1v7.yrm` | 逐字节一致 |
| `SuperAI-IceLake-1v7-NoOre.yrm` | 逐字节一致 |
| `SuperAI-Flat30.yrm` | 逐字节一致 |
| `SuperAI-Flat120.yrm` | 逐字节一致 |
| `SuperAI-Flat200.yrm` | 逐字节一致（构建时加 `--terrain-newline crlf`） |

模组构建依赖原版规则文件的字节内容；不同语言版本（`rulesmd.ini` 被本地化修改过）
会导致 `RULES_EDITS` 找不到原值而报错，这是有意的保护。

## 5. 安装到游戏

```bash
python tools/install.py --game-dir "F:/Games/VERA20K" --enable
```

见 [install.md](install.md)。

## 6. 加一张自己的观战图

1. 生成底图（或找一张 8 人图）。
2. 用 `build_maps.py flat` 统一地形、加触发器。
3. 玩家位放在可玩区外、留够 3 格；或者不加 `--move-player-corner`，
   把玩家放在地图角落自己部署。
4. `check.py` 确认 `starts` 数量正确。
5. 在 `docs/spectator-guide.md` 的地图表里补一行。

如果地图本身有 `[Triggers]`，`add_triggers` 会拒绝覆盖。
需要先合并原有触发器，或删掉该段再构建。
