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

先分清是「计划里没有」还是「计划里有但没落地」。用日志判，不要靠眼看：

```bash
python tools/analyze_log.py --log "F:/Games/VERA20K/logs/ra2.log" --session last
```

- **战车工厂/高科/维修厂首次出现的序号很靠后**（闸门是 ≤25%）：太多建筑被塞了
  `AIBuildCounts`，副本被随机撒到整张计划里，把后期建筑挤到队尾。本模组只给 6 个
  生产建筑（兵营/战车工厂），其余类型不写这个键。
  见 [ai-tuning-playbook.md §1.2](ai-tuning-playbook.md#12-按难度给数量冷酷-3-兵营-5-战车工厂26-起)。
- **某种建筑一次都没出现**：先查它的 `AIBuildThis`。原版把不少类型设成 `no`，
  那它们永远进不了计划，和钱、科技等级无关。
- **防御数量远少于计划数**：正常。防御节点找不到前置已满足的类型时会被**直接删除**，
  不是延后。看日志里的实际落地数（本模组已关闭围墙，所以不会再有围墙抢占）。
- **AI 在造围墙 / 基地被墙堵住**：本模组已把 `AIPickWallDefensePercent` 设为 `0,0,0`，
  AI 不可能造墙。如果你改成非 0 想恢复，注意 `tools/build_mod.py` 的 `assert_no_walls`
  会阻止构建 —— 那是有意为之。见
  [ai-tuning-playbook.md §11](ai-tuning-playbook.md#11-围墙全部关掉26-起)。
- **只改 `[AI]` 里的 `WarRatio` / `DefenseLimit` / `RefineryLimit` 没反应**：那些是死键，
  引擎根本没有读取者。完整清单见
  [ai-tuning-playbook.md §1.5](ai-tuning-playbook.md#15-死键清单)。
- **基地在约 70 栋时停下**：检查 `AIBaseSpacing` 是否被改成 2。
- **同一格反复放同一个建筑**：只有 Yuri 的矿场会这样，原因见
  [ai-tuning-playbook.md §4](ai-tuning-playbook.md#4-yuri-的矿场为什么自己复制自己)。

### AI 不造基地车 / 不扩张

**先说结论：引擎有这样的路径，2.2 起这条路径已经打通。**
数据里备好了 3 条「本户拥有 0 座建造厂」的 AI 触发器和 3 支 `Max=1` 的 MCV 队伍
（脚本 `043F23CC-G` = 找空地 + 展开）；真正把它堵死的是原版给三个维修厂标了
`AIBuildThis=no`，而基地车的前置正好是维修厂：

```ini
AMCV Prerequisite=GAWEAP,GADEPT
SMCV Prerequisite=NAWEAP,NADEPT
PCV  Prerequisite=YAWEAP,YAGRND
```

模组把 `GADEPT`/`NADEPT`/`YADEPT` 改成 `AIBuildThis=yes`，AI 才可能造出维修厂、进而造出基地车。

如果仍然看不到扩张，按顺序排查：

1. **维修厂有没有落地**：`analyze_log.py` 会在末尾列出「没有维修厂的房主」。
   一个都没有的话，先解决维修厂（前置是战车工厂 + 建造厂）。
2. **AI 有没有战车工厂**：产 MCV 需要在线战车工厂；被拆光就无解。
3. **MCV 是不是展开了但被拒**：日志里搜 `MCV deploy blocked at origin`
   （`world_spawn.rs` 的 `deploy_mcv` 在 `can_place_building_at` 失败时打印）。
   一局出现几十次很正常——基地太挤，4×4 空地不够。这跟「不造 MCV」是两个问题。
4. **建造厂被拆后 AI 是不是完全不动**：没有建造厂就不能造任何建筑，
   这时唯一的活路就是战车工厂产 MCV。第 1、2 步任一不满足，这一局就结束了。

> 不要为了让 MCV 触发器「更优先」把权重调到 5000：在这个引擎里那是「接管抽签」的标记，
> 会把其它所有触发器清掉，结果是这支 AI 完全不进攻。见
> [ai-tuning-playbook.md §5](ai-tuning-playbook.md#5-触发器权重-5000-是接管标记不是加强)。

### AI 建筑被打掉了却不重建

「打掉就重建」是引擎原生的节点重规划，不需要触发器，但**按类型分档**：

- 电厂、所有有武器的建筑（碉堡/光棱塔/爱国者…）、贴着自家建筑的围墙
  —— **本来就立即重建**，不需要配置；
- 兵营、战车工厂、高科、维修厂 —— 受 `AIRestrictReplaceTime` 限制。
  模组设为 **`0`**（不限制），所以它们也应立即重建；
- 如果发现不重建，按下面顺序查：

1. `AIRestrictReplaceTime` 是不是被改回了非 0 的值。
2. 那种建筑**有没有进过基地计划**：从没规划过的类型永远不会补
   （`AIBuildThis=no` 的类型进不了计划）。
3. 是不是**没有建造厂**：没有建造厂时引擎什么都不造，只能等基地车。
4. 连续 6 次选址失败后节点会被**删除**（`MaximumBuildingPlacementFailures=5`），
   此后那种建筑不会再补 —— 基地被围死时会看到这个现象。
5. 想量化验证，用重建事件报告：

```bash
python tools/analyze_log.py --log "F:/Games/VERA20K/logs/ra2.log" --session last --rebuilds
```

> 注意：建筑**丢失**本身不写日志，所以这个报告是「同一类型隔一段时间又在别的格子出现」
> 的代理指标，有噪声，要连同闸门报告一起看。

### AI 建满基地却不造兵、不进攻

**先查这一条**，它比任何触发器权重问题都常见：

```ini
UseMinDefenseRule=no
MinimumAIDefensiveTeams=0,0,0
```

模组把所有非 MCV 队伍都改成了 `IsBaseDefense=no`（没有守家队类型）。
如果这时把 `UseMinDefenseRule` 设为 `yes`、`MinimumAIDefensiveTeams` 设为非零，
引擎会要求「先有 1 支守家队才允许组队」，而守家队永远不存在 ——
于是 163 条触发器全部被拒：AI 不组队、不造兵、不进攻，但基地照常建造，
日志里**没有任何报错**。2.2 就这样静默失效过一整轮。

排查顺序：

1. `aimd.ini` 里有没有 `IsBaseDefense=yes` 的队伍类型？没有就该是上面的设置。
2. 再查 `TotalAITeamCap` 是否为 0，或 `RatioAITriggerTeam` 是否被地图改小。
3. 仍不正常就查触发器权重：**任何队伍若权重 ≥ 5000，会接管整次抽签**，
   而一支凑不齐的队伍会把该户其它队伍全部饿死。

> 注意：单位生产和队伍创建**完全不写日志**，`analyze_log.py` 也只统计建筑。
> 所以「造不造兵」无法从日志判断，只能进游戏看。

### AI 有平地却不继续扩建

2.4 起这是**预期行为**：计划节点就是建造预算，节点建完基地就静止，
之后的扩张靠「打掉就重建」。所以没人打它、它就不长。

- 想让基地本身更大：只调 `*BaseDefenseCounts`（如 `60,60,60`）。
  防御节点沿周长**向外**找位置，是唯一不破坏建造顺序的扩容旋钮。
- 不建议再去调 `AIBuildCounts`：副本是随机撒点，容易重新打乱建造顺序。
- 机制说明见 [ai-tuning-playbook.md §7.12](ai-tuning-playbook.md#712-ai-不扩张其实是计划节点用完了)
  与 [§9](ai-tuning-playbook.md#9-打掉就重建原生节点重规划不需要触发器)。

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

### `UnicodeDecodeError: 'gbk' codec can't decode byte ...`

Windows 控制台默认 cp936，而引擎和 `ra2.log` 都是 UTF-8。`tools/check.py` 与
`tools/analyze_log.py` 已显式指定 UTF-8；自己写脚本时也要显式指定
（`subprocess.run(..., encoding="utf-8", errors="replace")`、
`open(..., encoding="utf-8", errors="replace")`），不要依赖 `text=True`。

### 日志里同一个 `Computer1` 一会儿造 Yuri 建筑、一会儿造苏军建筑

`vera20k.exe` 追加写同一个 `ra2.log`，重开一局不会重启进程。一次启动里可能有多场对局，
第二场以 `sim::runtime] Initialized authored native` 开始。切分必须两级：
先按 `VERA20k <版本> starting` 切启动，再按上面那行切对局。
`analyze_log.py` 已经这样做，并会打印 `session N, match M`。

### 日志里没有 `Completed refinery YAREFN`，是不是 Yuri 矿场建不起来

不是。那行日志属于「矿场完成时送一台矿车」的路径，只有带 `Refinery=yes`/`FreeUnit=`
的类型才有（GAREFN、NAREFN）。YAREFN 是建筑变形体，没有这段。
判断 Yuri 矿场有没有落地，看 `placed YAREFN at (x, y)`。

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
