# 地图格式与触发器笔记

这里的结论都来自 VERA20k 源码与实测日志，适用于 `.yrm` / `.mmx` / `.map` / `.mpr`。
地图本质上是一个 INI 文本文件，只有 `[IsoMapPack5]` 是二进制压缩数据。

## 1. 基本区段

```ini
[Basic]
Name=Super AI Flat 30
Size=0,0,254,262          ; 整张地图，含四周填充
LocalSize=2,5,250,250     ; 可玩区 (left, top, width, height)
MaxPlayers=30

[Map]
...

[Waypoints]
0=258002
1=...
```

- `Size` 是整张地图的格子范围；`LocalSize` 是可玩矩形。
  可玩区之外仍属于地图，单位可以站，但通常没有地形装饰。
- 两者之间通常有 2 格左边距、5 格上边距和若干下/右边距。
  把观战者放在 `LocalSize` 下方 3 格，正好有空间放下 3×3 的 MCV。

## 2. 航点编码

```text
packed = y * 1000 + x
```

例如：

| packed | 格子 | 用途 |
| --- | --- | --- |
| `27180` | (180, 27) | Ice Lake 玩家位，可玩区右边缘外 |
| `258002` | (2, 258) | Flat 30 玩家位，可玩区左下角外 |
| `508002` | (2, 508) | Flat 120 玩家位 |
| `198082` | (82, 198) | Flat 200 普通角落位 |

`x` 必须小于 1000，所以地图宽度上限是 1000 格。

**不要放在填充区的角落。** 之前把 0 号位设成 `4002` = (2,4)，
基地车 3×3 找不到落点，日志报 `Failed to seed session MCV ... at waypoint 0 (2,4)`，
玩家没有任何单位，首帧判负。至少留 3 格宽的空间。

## 3. 地图上的建筑会被跳过

VERA 沿用原版多人规则：**地图里属于本地玩家的建筑，在载入时被删除**。

```text
Skipping map Techno SPYSATX owned by Americans before constructor resolution
```

遭遇战里 AI 房屋叫 `Computer1`、`Computer2`…，地图里写的国家名（`Americans` 等）
匹配不上，所以给 AI 预置建筑也不会生效；只有 `Neutral` / `Special` 的保留。

结论：

- 不要靠地图预置建筑给玩家加视野或基地。
- 观战者的全图用触发器（动作 16）或引擎的 `/spysat`。
- 建筑增益（如建造厂 `SpySat=yes`）放在 `rulesmd.ini` 里。

## 4. `[IsoMapPack5]` 地形包

### 4.1 文本格式

```ini
[IsoMapPack5]
1=AAAA...
2=AAAA...
```

每个值是 base64 文本，单行不超过 512 字节（引擎的通用上限）。把所有值按顺序拼接、
base64 解码后得到压缩流。

### 4.2 压缩流

```text
[u16 src_len][u16 dst_len][src_len bytes LZO1X]  ...  [0x0000 0x0000]
```

- 解压后每 8192 字节为一个块；`dst_len` 是该块解压后的长度。
- 生成时按 8192 字节切块，逐块用 LZO1X 压缩，写入 `src_len/dst_len` 和压缩数据。
- Python 用 `lzokay` 即可读写。

### 4.3 单元格记录

解压后的数据是连续的 11 字节记录：

```c
struct IsoCell {
    int16 x;       // 等距坐标
    int16 y;
    int32 tile;    // TileType 索引
    uint8 sub;     // 子格 0..3
    uint8 z;       // 高度 0..15
    uint8 legacy;  // 原版保留
};
```

以 4 个零字节（`x=0, y=0`）作为结束标记。

已知地块：

| tile | 外观 | 可建造 |
| --- | --- | --- |
| 418 | 单格平地（橄榄绿） | 是 |
| 323 | 水面 | 否 |
| 493 | 沙地 | 是 |

Flat 系列地图把**全部记录**改成 `tile=418, sub=0, z=4`，
所以整张图是一块同高平地，没有海岸线、水、悬崖。

### 4.4 为什么删掉 `[OverlayPack]`

`[OverlayPack]` / `[OverlayDataPack]` 存的是矿石、道路、围墙、铺装等 overlay。
矿石会占住格子，导致 AI 的基地选址失败：

- 有矿的 Ice Lake：100 秒 632 栋，70 秒后掉到每 10 秒 5 栋。
- 删掉 overlay 后：100 秒 863 栋，全程稳定。

删掉这两个段，矿石和道路一起消失。再用：

```ini
TiberiumGrows=no
TiberiumSpreads=no
```

阻止重新生长。经济由矿场的 `ProduceCash` 补上。

## 5. 触发器

### 5.1 四个区段

```ini
[Triggers]
ID=HOUSE,<none>,NAME,DISABLED,EASY,MEDIUM,HARD,TRANSFER

[Events]
ID=COUNT,KIND,PARAM_TYPE,VALUE

[Actions]
ID=COUNT,KIND,P1,P2,P3,P4,P5,P6,WAYPOINT

[Tags]
ID=REPEAT,NAME,TRIGGER_ID
```

### 5.2 容易踩的坑

- **`[Actions]` 的第一个数字是「动作条数」，不是动作编号。**
  一条动作是 8 个 token：`KIND,P1..P6,WAYPOINT`。
  写 `1,16,0,0,0,0,0,0,0` = 1 个动作，动作 16。
  写成 `16,0,0,...` 会被读成 16 个动作，整条失效。
- **航点字段是字母**：`A=0`、`B=1`、…、`Z=25`，
  两位字母是 `26 * 第一个 + 第二个 + 26`。写成数字 `0` 会解析失败，
  `waypoint_index = None`，动作直接返回。
- **事件 13 是计时器，单位是秒**（内部 `value × 15` 帧）。
- **`[Tags]` 的 `REPEAT`**：`0` 一次性，`2` 可重复（会重置计时器），
  `1` 是特殊语义，不要拿来当循环。
- **单值 512 字节上限**：动作多时要拆成多条触发器（120 人图拆了 12 条）。
- 计时器事件（13）归类为 **Logic 标签**，每帧轮询，不需要挂到房屋或单位上。

### 5.3 本项目的动作

| 动作 | 含义 | 参数 |
| --- | --- | --- |
| 6 | All to Hunt | 目标房屋选择器 |
| 16 | 揭开全图 | 无 |
| 109 | 在航点施放铁幕 | 航点字母 |

房屋选择器 `0x117B + slot` 是 Ares 的 `Player @ X`：

```text
4475 = Player @ 0（本地玩家）
4476 = Player @ 1（1 号位）
...
```

所以 `4476..4482` 对应 1–7 号位的 7 个电脑。

### 5.4 示例：每 20 秒清一次 AI 部队

```ini
[Triggers]
02000000=<none>,<none>,AIHuntAll,0,1,1,1,0

[Events]
02000000=1,13,0,20

[Actions]
02000000=7,6,0,4476,0,0,0,0,A,6,0,4477,0,0,0,0,A,6,0,4478,0,0,0,0,A,6,0,4479,0,0,0,0,A,6,0,4480,0,0,0,0,A,6,0,4481,0,0,0,0,A,6,0,4482,0,0,0,0,A

[Tags]
02000001=2,AIHuntAll,02000000
```

## 6. 生成 Flat 地图

### 6.1 随机地图尺寸

VERA 的 `--generate-map` 读取 SED：

```ini
[RandomMap]
Description=Flat 120
Width=7
Height=7
NumPlayers=120
Seed=20261122
MapType=1          ; 1 = 单块大陆
Ruggedness=0
WaterAmount=0
Vegetation=0
Tiberium=1
Resources=0
```

尺寸档与 `Width/Height` 对应：

| Width/Height | 可玩区 |
| --- | --- |
| 4 | 160×160 |
| 5 | 250×250 |
| 6 | 350×350 |
| 7 | 500×500 |

`NumPlayers` 支持到 120，生成器会放对应数量的出生点。
`MapType=1` + `Ruggedness=0` + `WaterAmount=0` 会得到一块完整平地；
`MapType=0` 会生成带海岸线的岛屿。

### 6.2 200×200（非标准尺寸）

生成器的尺寸表是硬编码的 `[160, 250, 350, 500]`，没有 200。做法：

1. **复制**一份 `vera20k.exe`，只用于生成地图（不要改游戏本体）。
2. 在副本中搜索小端 i32 数组 `160, 250, 350, 500`，
   把 `250` 改成 `200`。
3. 用 `Width=5 Height=5` 生成，得到 `LocalSize=...,200,200`。

这是未公开的取巧做法，引擎升级后偏移会变，需要重新搜索字节模式。
优先使用 250 / 500 两种标准尺寸。

### 6.3 统一地形

生成出来的地图仍有草地纹理、海岸线和少量杂物。用：

```bash
python tools/build_maps.py uniform --src raw.yrm --out flat.yrm --tile 418 --height 4
```

它会把 `[IsoMapPack5]` 的每条记录重写成同一块平地。
Flat 200 的发布版使用了 CRLF 地形行（历史原因），重建时加 `--terrain-newline crlf`。

## 7. 校验地图

```bash
python tools/build_maps.py info --src maps/SuperAI-Flat30.yrm
```

输出名称、`LocalSize`、出生点数、触发器数和地形分布，用来确认：
地形是否纯平、出生点数量是否正确、触发器是否写进去了。

引擎侧校验：

```bash
vera20k.exe --probe --ra2-dir "<YR 数据>" --mod SuperAI --map "maps/SuperAI-Flat30.yrm"
```

`max_start_waypoints` 应等于地图的出生点数量。
