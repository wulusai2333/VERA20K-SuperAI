# 安装与启用

## 1. 前置条件

| 需要 | 说明 |
| --- | --- |
| VERA20k | 游戏根目录下应有 `vera20k.exe` 与 `Mods/` 文件夹 |
| YR 游戏数据 | 引擎直接读取 `.mix`；`config.toml` 的 `[paths] ra2_dir` 要指向它 |
| Ares | 模组使用 `AIBuildCounts` 等 Ares 键，Ares 必须是 **Auto** 或 **On** |
| Python 3.11+ | 只有使用 `tools/` 下的脚本时需要；玩游戏不需要 |

检查 Ares 设置：主菜单 → 选项 → 游戏，或直接看 `VERA.INI` / `config.toml`。
`Auto` 会按模组声明自动启用，`On` 强制启用。

## 2. 自动安装

```bash
python tools/install.py --game-dir "<游戏目录>" --enable
```

脚本做三件事：

1. 把 `mod/SuperAI/` 复制到 `<游戏目录>/Mods/SuperAI/`
2. 把 `maps/*.yrm` 复制到 `<游戏目录>/Maps/`
3. `--enable`：备份 `config.toml` 为 `config.toml.bak`，写入 `mod = "SuperAI"`

只装模组、不装地图：

```bash
python tools/install.py --game-dir "<游戏目录>" --no-maps
```

已经装过再运行是安全的：内容相同的文件会被跳过。

## 3. 手动安装

1. 复制 `mod/SuperAI` 整个文件夹到 `<游戏目录>/Mods/`
2. 复制 `maps/*.yrm` 到 `<游戏目录>/Maps/`
3. 打开 `<游戏目录>/config.toml`，在 `[paths]` 下加一行：

```toml
mod = "SuperAI"
```

或者启动游戏，在 **选项 → 模组** 里选择「超级AI (Super AI)」。

## 4. 验证

用无窗口探针检查规则、AI 与地图是否能加载：

```bash
python tools/check.py --game-dir "<游戏目录>"
```

期望输出类似：

```
rules / AI
  mod=超级AI (Super AI) v3.13.5 ares=on check=None
  rules mod        changed=True
  art   mod        changed=False
  ai    mod        changed=True
sidebar names
  csf  ares.csf   3 label(s): Name:ZAINukeGunship2Drop=空中炮艇, Name:ZAINukeGunship3Drop=集束炮艇, Name:ZAINukeGunshipDrop=核弹炮艇
maps
  OK   SuperAI-Flat120.yrm  3494010 bytes  starts=120
  ...
all maps OK
```

也可以直接调用引擎：

```bash
vera20k.exe --probe --ra2-dir "<YR 数据目录>" --mod SuperAI --map "Maps/SuperAI-Flat30.yrm"
```

## 5. 启用后要重启

模组列表与所有 INI 只在**启动时**读取一次。安装或修改文件后必须完全退出游戏再启动，
否则看到的仍是旧数据。

## 6. 卸载

- 关闭模组：**选项 → 模组 → 不使用模组**，或删掉 `config.toml` 里的 `mod = "SuperAI"`。
- 彻底删除：移除 `<游戏目录>/Mods/SuperAI/` 和不需要的地图。
- 规则改动会让旧录像失效；卸载后原来的录像才能重新播放。

## 7. 联机注意

- 房间内**所有人**必须使用完全相同的 `mod/SuperAI` 文件与地图文件。
- 任何一方规则不同都会导致不同步（desync）。
- 观战席位仅 LAN/在线房间支持；本地遭遇战用本项目的地图触发器方案。
