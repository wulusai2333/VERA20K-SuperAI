# Changelog

本项目在 2026-11-22 从零迭代到 1.9，以下是可复现的功能节点。

## 1.9

- 基地车完全还原原版：`[AMCV]/[SMCV]/[PCV]` 无 `Immune`、`Strength=1000`，
  与零售 `rulesmd.ini` 逐字节一致。
- 3 支 MCV 队伍恢复原版 `043F23CC-G` 部署脚本，其余 160 支队伍继续全员冲锋。
- 移除未使用的 `SPYSATX` 建筑定义与 AI 专用 MCV 克隆（引擎类型表不接受新类型）。

## 1.8（已回退）

- 尝试给 AI 使用可击杀的 MCV 克隆 `AMCV2/SMCV2/PCV2`；
  引擎 `[VehicleTypes]` 注册表仍只读原版 85 项，克隆不生效，已删除。

## 1.7

- 地图新增 `AIHuntAll`：每 20 秒对 1–7 号位执行 All to Hunt，
  清掉中后期囤在基地里的部队。
- 观战者必须坐 Start 1，触发器不会作用于 0 号位。

## 1.6

- **160 支队伍全部不守家、直接冲锋**（`ZAIATK01-G`）。
- `*BaseDefenseCounts=100,100,100`，防御建筑占比约 31%。
- `MaximumAIDefensiveTeams=0`、`MinimumAIDefensiveTeams=0`、`UseMinDefenseRule=no`。

## 1.5

- 新增 `ZAIATK01-G` 脚本，绕过原版脚本开头的 `54`（回基地集结）与
  `53`（到敌方基地外集结）。
- `DissolveUnfilledTeamDelay` 5000 → 900。

## 1.4

- 无矿版 Ice Lake：删除 `[OverlayPack]` / `[OverlayDataPack]`，
  矿石不再阻塞基地选址（100 秒 863 栋，对比有矿 632 栋）。
- 矿场加 `ProduceCashAmount=100` / `ProduceCashDelay=60` 支撑无矿经济。
- `AIBuildCounts` 每类 60。

## 1.3

- 建造厂 `SpySat=yes`：展开基地即全图。
- Ice Lake 地图内置 `RevealAll`（1 秒）与 `IronCurtain`（每 10 秒，航点 A）。
- 修正 `[Actions]` 行格式：首字段是动作条数，末字段是航点字母。

## 1.2

- 基地扩张：`AIBaseSpacing=2`（后来发现会导致选址失败，1.4 起回到 1）。
- 65 支进攻队编制 ×2，进攻触发器权重 250。
- `TotalAITeamCap=45`、`MaximumAIDefensiveTeams` 调整、`AIHateDelays` 缩短。

## 1.1

- 回退到最小改动，只保留资金、组队间隔、建造速度三项，用于验证基线。

## 1.0

- 第一版：放大进攻队编制、精英等级、触发器权重，缩短组队间隔。
