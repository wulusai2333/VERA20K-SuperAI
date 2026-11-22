# 常见问题

## 模组

### 模组列表里没有「超级AI」

- 装完后必须**完全退出游戏再启动**，模组目录只在启动时扫描。
- 确认 `<游戏目录>/Mods/SuperAI/mod.ini` 存在，且 `[Files]` 指向的三个文件都在。
- `mod.ini` 的路径是相对模组目录的，不要把文件再套一层文件夹。

### 选项里有模组，但规则没变

- 用无窗口探针确认加载来源：

```bash
vera20k.exe --probe --ra2-dir "<YR 数据>" --mod SuperAI
```

看 `rules_parts.files` 里 `rules` / `ai` 的 `source` 是否为 `SuperAI`。
- 检查 `config.toml` 是否还有 `mod = "SuperAI"`，或者模组菜单里是否选中。
- Ares 必须是 **Auto** 或 **On**，否则 `AIBuildCounts` 等键会被忽略。

### 启动时报 Ares 相关错误

模组声明了 `[Extensions] Ares=yes`，但引擎或数据不完整时可能拒绝加载。
把 Ares 设为 `Auto`，确认游戏数据里有完整的 `rulesmd.ini` 等文件。

## 对局

### 一进地图就游戏结束

99% 是玩家出生点没有空间放基地车：

```text
Failed to seed session MCV 'AMCV' for Computer1 at waypoint 0 (2,4)
```

- 本地遭遇战：确认自己坐 **Start 1**，并且 **快速游戏 = 关**。
- 自建地图：0 号位至少留 3×3 的空地，不要放在填充区角落。
  推荐放在可玩区下方 3 格（本项目的做法）。

### 没有全图视野

- 地图自带 `RevealAll`，开局 1 秒后生效；如果没亮，按 Enter 输入 `/spysat`。
- `/spysat` 需要 `VERA.INI` 的 `SkirmishCheats=yes`。
- 普通对战地图没有 `RevealAll`，只能靠建造厂的 `SpySat=yes`（展开基地后生效）。

### 基地车没有铁幕

- 铁幕只覆盖 0 号位周围 3×3；把 MCV 开走就没了，开回来会重新套上。
- 只有带 `IronCurtain` 触发器的地图才有这个效果（Ice Lake、Flat 30/120）。

### AI 中后期还是堵在基地

- 确认地图带 `AIHuntAll` 触发器：

```bash
python tools/build_maps.py info --src maps/SuperAI-IceLake-1v7-NoOre.yrm
```

输出里 `triggers` 应大于 0。
- 确认自己坐 **Start 1**，触发器只清 1 号位之后的 AI。
- 确认 AI 之间是 FFA（队伍关闭），否则它们会结盟、没有敌人可打。

### AI 不铺建筑 / 只造电厂

- 难度必须是冷酷/困难；`TeamDelays` 与防御队设置都按难度分档。
- 检查 `AIBuildCounts` 是否被其他模组覆盖。
- 如果基地在约 70 栋时停下，检查 `AIBaseSpacing` 是否被改成 2。
- 如果只造某一种建筑，可能是把 `AIBuildCounts` 调得过高（例如 250），
  建造顺序会偏科；回到 60。

### AI 不造基地车 / 不扩张

VERA 的 AI 没有「生产 MCV 并展开」的决策路径，这是引擎限制。
模组保留 3 支 MCV 队伍的原版部署脚本，AI 有 MCV 时会去展开，
但它不会主动为了扩张而生产 MCV。

### 建造速度太快，玩家也受影响

`BuildSpeed` 是全局键。想只让 AI 快，需要改引擎或给 AI 单独的建造队列，
纯 INI 做不到。把 `.025` 调回 `.07`（10 倍）或 `.2`（3.5 倍）即可缓和。

### 4 个以上 AI 时卡顿

- 30/120 人图非常吃 CPU；先减少 AI 数量。
- 降低资金（10000），减少同时建造量。
- 关闭「战斗中高刷新率」，或把游戏速度降一档。

## 地图

### 地图列表里没有新地图

- 确认 `.yrm` 在 `<游戏目录>/Maps/` 下，而不是子文件夹。
- 重启游戏。
- 文件名不要含特殊字符；显示名来自 `[Basic] Name=`。

### 地图全是水 / 悬崖 / 树

`build_maps.py flat` 会删掉 overlay、树、中立建筑并统一地形。
如果只用了 `uniform`，overlay 仍然存在，需要先 `flat` 或手动删段。

### 200×200 地图生成失败

生成器只支持 160/250/350/500。200 需要改生成器副本，见
[map-format.md](map-format.md#62-200200非标准尺寸)。建议直接用 250。

## 录像与联机

### 旧录像播不了

规则和地图变了，录像内的校验对不上。看旧录像前关闭模组，或加 `--no-mod`；
用本模组录的新录像则必须开着模组播放。

### 联机不同步

- 所有人的 `Mods/SuperAI` 与地图文件必须完全一致（建议直接传压缩包）。
- 任何一方改了 `rulesmd.ini` / `aimd.ini` 都会 desync。
- 观战席位只在 LAN/在线房间生效；本地遭遇战用地图触发器方案。

## 工具

### `ModuleNotFoundError: lzokay`

```bash
python -m pip install -r tools/requirements.txt
```

### `rules keys not replaced`

`build_mod.py` 找不到原版值，说明 `--rules-dir` 里的规则文件不是预期版本
（可能被其他模组改过，或是不同语言/版本的规则）。换一份干净的原版文件。

### 地图构建后触发器没生效

- 用 `build_maps.py info` 看 `triggers` 数量。
- 检查 `[Actions]` 第一个数字是不是动作条数、最后一位是不是航点字母。
- 检查事件 13 的时间单位是秒，`[Tags]` 的 repeat 是 2。
