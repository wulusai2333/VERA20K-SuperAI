# 超级AI (Super AI)

这是 **VERA20K-SuperAI** 项目的模组本体，由 `tools/build_mod.py` 生成。

- 完整说明：见仓库根目录的 `README.md`
- 安装方法：见 `docs/install.md`
- AI 参数与设计：见 `docs/ai-design.md`
- 常见问题：见 `docs/troubleshooting.md`

文件：

| 文件 | 内容 |
| --- | --- |
| `mod.ini` | 模组声明（`[Extensions] Ares=yes`） |
| `rulesmd.ini` | 规则：资金、建造、防御、建造厂卫星、矿场收入 |
| `artmd.ini` | 与原版一致，未修改 |
| `aimd.ini` | 队伍编制、不集结脚本、触发器权重 |

改动规则后请重启游戏。联机时所有人必须使用完全相同的文件。
