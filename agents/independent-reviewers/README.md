# 独立完成评审：当前暂停

2026-10-25 用户已禁用小川（douyin-male-player-reviewer）、小禾（douyin-female-player-reviewer）、小砚（independent-game-art-reviewer）。三人完成评审门暂停，当前任务不要求三人票据或票门检查；不得调用三位，也不得用普通 agent、复制角色指令或自评代演回退。小衡保留但暂停主持。小谨 game-verifier 的独立验收及适用前置、真人和平台门保持。恢复须用户明确要求，并先同步角色安装与当前入口规则。

当前 `python tools/install_reviewers.py` 只安装保留的小衡及历史票门工具；`python tools/install_team.py` 安装十生产岗位与暂停主持的小衡。三位角色不再安装为活动 `.toml` 定义；旧安装副本归档为 `.disabled`，源码保留供恢复。`--check` 仅校验。

以下为旧版安装、调用和评审说明，仅供恢复参考；当前不执行，不据此重新派三位或使用普通 agent 回退。

---

# 小衡：跨项目三人独立评审总入口

在任意小游戏项目中，直接说：

```text
请调用小衡（game-review-panel），组织小川、小禾、小砚独立评审当前游戏。
```

可附评审范围、可玩入口、截图/录屏、版本和目标设备；已有材料由小衡自行查找。小衡冻结同版材料，分别创建三位独立实例，收齐报告、检查票据并汇总。**三人都评，至少两票有效通过**；小衡不投票。没有足够材料就明确待审，不虚构试玩或通过票。

未通过时，三位必须逐项说明具体问题、证据位置、影响、最小优化方向和可观察复评条件，明确区分缺证与个人偏好。小衡汇总保留每人的拒绝点，便于制作人派修；不只给“质感差”“不值10元”或票数。

本文件就是文件夹的总入口。未发现命名角色时，也可直接提及本文件夹或这个 README，要求读取 [game-review-panel.toml](game-review-panel.toml) 的完整指令启动新独立实例，再调用同目录三位；须如实记录调用方式。

| 名字 | 职责与设定文件 | 核心条件 |
| --- | --- | --- |
| 小衡 | 主持人：[game-review-panel.toml](game-review-panel.toml) | 锁定材料、分别委派、保存原票、校验汇总；不代评、不改票。 |
| 小川 | 普通男性玩家：`douyin-male-player-reviewer`（源定义仅供恢复，不随活动包安装） | 画面与玩法成立，并愿意花自己的 10 元玩当前游戏。 |
| 小禾 | 普通女性玩家：`douyin-female-player-reviewer`（源定义仅供恢复，不随活动包安装） | 同样严格的 10 元价值判断，广泛接受风格，不套性别标签。 |
| 小砚 | 资深游戏美术：`independent-game-art-reviewer`（源定义仅供恢复，不随活动包安装） | 细节到位、达到同类商业小游戏质感，关键专业项至少 4/5。 |

昵称用于称呼，技术标识和票据仍用 TOML 的 `name`，三位票据版本仍为 `1.1`。完整心理、偏好、风格范围、门槛和证据规则均在各自 TOML 内。调查事实与画像假设分开写在 [RESEARCH.md](RESEARCH.md)。三位是合成评审视角，不冒称真人已体验或真实愿意付款。

整套制作/技术/美术/验收/评审团队的统一入口是 `$game-team`。只需要三人独立评审时继续调用小衡；完整团队由个人级 game-team skill 统一调度十二位。

从实际源码仓库根运行，安装完整团队与评审：

```powershell
python tools/install_team.py --check
python tools/install_team.py
```

仅安装评审主持、三位评审与便携票门工具：

```powershell
python tools/install_reviewers.py --check
python tools/install_reviewers.py
```

默认安装结构：

```text
CODEX_HOME/agents/                 # 未设置时为 ~/.codex/agents/
  game-review-panel.toml          # 小衡，总入口
  douyin-male-player-reviewer.toml # 小川
  douyin-female-player-reviewer.toml # 小禾
  independent-game-art-reviewer.toml # 小砚
  game-review-panel/review_gate.py # 与仓库票门完全相同，可独立运行
```

安装后跨项目调用无需回到 E 盘、复制项目配置、安装制作人或接入看板。命名角色列表尚未刷新时新开会话；也可按上面的完整指令降级方式执行，不能只换显示名。个人级独立 TOML 遵循 [Codex 自定义 agent 规范](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents)。

可用 `--destination <自定义agents目录>` 安装完整包，调用时说明该目录；搬到另一台机器时，复制上面的四份 TOML 和整个 `game-review-panel/` 工具目录到该机器个人 agents 目录。票门需要 Python 3.11+（安装器使用标准库 tomllib），无额外包。相同文件跳过，覆盖前唯一备份，不影响原岗位。制作人及原八岗位仍用 `python tools/install_roles.py` 更新。

制作人的强制完成门见 [COMPLETION_REVIEW.md](../COMPLETION_REVIEW.md)，可委派小衡组织。原有功能和平台门仍须满足；小衡和三位都不新增看板岗位、不写 STATE、不冒充正式验收。用户直接在其他项目调用时，只给评审，不自动启动制作流程。并发名额少时分批执行，三位仍须各自独立回票。

单独调用示例（实际材料替换尖括号）：

```text
请调用小川（douyin-male-player-reviewer），独立评定以下实际游戏。
task_id: <任务>
round_id: <本轮>
candidate_id: <锁定版本>
evidence_ids 与材料路径/入口: <截图、录屏、可玩入口>
范围、目标设备与已知未测项: <实际信息>
请按角色指令给出报告和票据，不读取其他评审结论。
```

其他两位分别调用，不能让一个实例代演三位。没有材料就如实缺证，不需要为单独调用创建项目、上报事件或推进阶段。
