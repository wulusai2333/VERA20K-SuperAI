# 边界手册：今天踩过的坑与确认过的正确路径

> 用途：下次做地图/单位改动前，先读这一页。
> 版本基线：mod 3.11.x（VERA20k 0.4.0）。

---

## 一、动手前的三个问题（顺序不能反）

1. **这东西属于哪一级？**
   - **地图级**（`.yrm`）：只影响那一张图；
   - **玩家级**（超武）：靠 `SW.AlwaysGranted` + `SW.AllowAI` 控制归属；
   - **全局级**（`rulesmd.ini` / `aimd.ini` 的公共表）：**所有地图、所有电脑**都受影响。
2. **验证信号是什么？** 必须是能看见的东西：日志行（`SuperWeaponTypes: N loaded`）、
   游戏内现象（有没有模型、炸多大、会不会开火），而不是"配置看起来对"。
3. **失败怎么退？** 每次改动前先想好"回滚是改哪一行"。

**铁律**：想让某个东西"只给人类玩家"，就走**新超武类型**，不要改公共表。
公共表的"唯一合法例外"是：改完之后**明确知道还有谁在用它**，并且把那些使用者一起隔离
（例如把 `[CombatDamage]` 调大后必须关掉零售高炮的散布）。

---

## 二、确认过、可以直接复用的正确路径

### 2.1 给玩家一个专属超武（最干净的"只给人类"载体）

```ini
[SuperWeaponTypes]
13=ZAIUnlimitedNuke

[ZAIUnlimitedNuke]
Type=MultiMissile
RechargeTime=0.01        ; 注意：写 0 会被当成"未设置"，回落到 10 分钟
SW.Shots=1000
SW.AllowPlayer=yes
SW.AllowAI=no            ; ← 电脑拿不到
SW.AlwaysGranted=yes     ; ← 不需要建筑，开局就有
SW.RequiresTarget=yes
```

实测有效、全局生效、不依赖国家选择。

### 2.2 用超武把**自建单位**投给玩家

```ini
[SuperWeaponTypes]
14=ZAINukeGunshipDrop

[ZAINukeGunshipDrop]
Type=UnitDelivery        ; 引擎里真实存在的实现（sim/superweapon/unit_delivery.rs）
Action=Nuke
RechargeTime=0.01
SW.AllowPlayer=yes
SW.AllowAI=no
SW.AlwaysGranted=yes
SW.InitialReady=yes      ; 开局即可用
SW.RequiresTarget=yes
Deliver.Types=ZAINukeGunship    ; ← 载荷键是 Deliver.Types，不是 UnitDelivery.Types
```

配套事实：`Type=PlaceUnits` **无效**；`UnitDelivery.Types` **无效**（写错就"点了没反应"）。

### 2.3 新单位要有模型：`Image=` 写在 **rulesmd**

```ini
; rulesmd.ini
[ZAINukeGunship]
Image=ZEP          ; 借用基洛夫的 art/voxel（零售同款： [JUMPJET] Image=ROCK）
```

**反例**：在 `artmd.ini` 里新建 `[ZAINukeGunship] Image=ZEP` —— **仍然隐形**，
因为引擎按对象 ID 去找 `ZAINukeGunship.vxl`，找不到就不画。

### 2.4 让核弹弹丸"乱飞"：散布是**弹丸级**的

```ini
[ZAINukeRifleProj]
Arcing=true            ; 弹道弹
Ranged=yes             ; 非追踪（追踪弹永远精确）
Inaccurate=yes         ; 不吸附目标点
FlakScatter=yes        ; 会散
BallisticScatter.Min=50    ; ← 武器专属散布下限（格），实测生效
BallisticScatter.Max=200   ; ← 武器专属散布上限（格），实测生效
AG=yes                 ; 要打地面就必须 AG=yes
```

要点：
- **半径用 `BallisticScatter.Min/Max` 写在弹丸段里**（实测有效，公共表不用动）；
- `[CombatDamage] BallisticScatter` 是**全局唯一段**，改它会波及所有弹道/高炮使用者
  （零售注释：`maximum scatter distance (cells) for inaccurate ballistic projectiles`）；
- **追踪弹（有 `Arm`/`ROT`）永远不会散**，必须有 `FlakScatter` + 非追踪 + 弹道。

### 2.5 伤害与爆炸范围：克隆现成弹头

```ini
[ZAINukeWH]            ; 3 星（精英）无畏导弹弹头
CellSpread=3
PercentAtMax=.5
AnimList=MININUKE      ; 小蘑菇云
Verses=100%,90%,80%,100%,80%,80%,85%,65%,28%,80%,0%
```

命名规律：**精英版 = 同名 + `E`**（`[DMISLWH]` 1.5 格 → `[DMISLEWH]` 3 格）。
三档参照：普通导弹 1.5 格 / 3 星无畏 3 格 / 零售核弹 10 格（`[NUKE]`，别动）。

### 2.6 自动开火与射程

```ini
GuardRange=20          ; 真正的"自动索敌半径"，必须等于武器 Range
CanPassiveAquire=yes   ; 自己找目标
OpportunityFire=yes    ; 边飞边打
CanRetaliate=yes       ; 挨打还手
```

**坑**：只改武器 `Range` 不会让它主动开火；`GuardRange` 大于 `Range` 会让它追着打不到的目标转。

### 2.7 打不死、不被瞄

```ini
Strength=100000
Insignificant=yes      ; AI 的防空不把它当目标
```

### 2.8 基洛夫机体（不需要停机位）

```ini
BalloonHover=yes
Locomotor={92612C46-F71F-11d1-AC9F-006008055BB5}
MovementZone=Fly
ConsideredAircraft=yes
```

---

## 三、黑名单（试过、无效或有害，别再试）

| 做法 | 结果 |
| --- | --- |
| `[General] ParaDrop.Types=<载具>` | 投出来是普通伞兵（引擎只读四张按阵营的**步兵**表） |
| 改 `AmerParaDropInf` 等四张表 | **玩家与电脑共用** → 电脑也投同样的东西，属于越权，已回滚 |
| `Type=DropPod` + `DropPod.Types` | 点击毫无反应 |
| `Type=SpyPlane` + `SpyPlane.Type/Count/Mission` | 飞机横穿但不使用武器、航线写死、还会被打掉 |
| `Type=MultiMissile` + `Range/LineMultiplier` 想散射 | 只有一发普通核弹（弹头来自全局 `[General] Nuke.Payload`） |
| `Type=Battery` + `SW.MaxCount` | 无效 |
| `Type=PlaceUnits` | 无效 |
| `artmd.ini` 里写 `Image=` | 无效（单位隐形） |
| `[CombatDamage]` 想"给某个单位单独一份" | 全局唯一段，写两个只会覆盖 |
| `Airburst=yes` 挂在弹丸上 | `Airburst` 是 **VoxelAnim** 键，不是抛射体键 |
| `RechargeTime=0` | 被当成"未设置"，回落 10 分钟 |
| 追踪弹想靠 `HomingScatter` 散 | 追踪弹永远咬住目标，照样精确命中 |

---

## 四、方法论（下次照这个流程走）

1. **先分类，再动手**：新键/新段属于哪一类（Projectile / Weapon / Warhead / VoxelAnim /
   General / Art / Map）？—— **查二进制字段表**，不要信教程措辞
   （`Airburst` 就是这么被识破的）。
2. **一次只变一个变量**，并给用户一个明确的验证动作（"打一梭子看落点"）。
3. **静默失败要变断言**：凡是"写错不报错、只是不生效"的（缺 art → 隐形、缺 `Deliver.Types`
   → 点了没反应、`RechargeTime=0` → 回落），构建期就断言掉。
4. **改公共表前先列出所有使用者**，能隔离就隔离，不能隔离就问用户要不要承担。
5. **发现方向错了就整体回滚**，不要"顺手把对方也关了"（那是越权，不是修复）。

---

## 五、今日版本轨迹（供回溯）

| 版本 | 内容 | 结果 |
| --- | --- | --- |
| 3.9.x | 试图用超武一次撒满全图（`MultiMissile`/`Battery`/`SpyPlane`/`DropPod`） | ✗ 全部无效 |
| 3.10.0–3.10.6 | 改为空投核弹兵，逐步修好武器/弹道/弹头 | ✗ 空投表是公共的，且只能投步兵 |
| 3.10.7–3.10.8 | 试图关电脑空投 → 越权 → **整体回滚** | — |
| 3.10.9–3.10.10 | 发现 `UnitDelivery` + 找到正确键 `Deliver.Types` | ✓ 投放成功 |
| 3.10.11–3.10.12 | 修模型：`Image=` 要写在 rulesmd | ✓ 有基洛夫外形 |
| 3.11.0–3.11.2 | 两艘飞艇（20 格追踪弹 / 200 格弹道核弹）+ 武器级散布 | ✓ 确认可用 |
