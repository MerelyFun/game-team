# game-team

从 [AgentBoard](https://github.com/MerelyFun/AgentBoard) 提取的小游戏协作团队：用一个 `$game-team` 入口，在当前项目按需组织制作、策划、技术、开发、美术与独立验收。共享协议与完整角色指令可以跨项目复用；具体阶段、引擎、平台和完成条件仍以目标项目为准。

## 安装

需要 Python 3.11+，安装器仅使用标准库，无需安装 Python 第三方依赖。先 clone 完整仓库，再从仓库根目录执行：

```shell
git clone https://github.com/MerelyFun/game-team.git
cd game-team
python tools/install_team.py --check
```

`--check` 只读取并校验源文件，不创建或修改安装目标。可先安装到仓库外的隔离目录，检查实际产物：

```shell
python tools/install_team.py --destination ../game-team-install-test
python tools/install_team.py --destination ../game-team-install-test
```

确认后安装到个人 Codex 目录：

```shell
python tools/install_team.py
```

默认目标为环境变量 `CODEX_HOME` 指定的目录；未设置或为空时为用户 home 下的 `~/.codex`。`--destination` 显式指定的是替代 **CODEX_HOME 根目录**，不是其 `agents/` 子目录。安装需要对目标目录的写入权限，不要求写入系统目录。

安装器会生成完整的个人包：

```text
<目标目录>/
  agents/
    game-*.toml                   # 十个生产岗位与暂停主持的小衡
    game-review-panel/review_gate.py
  skills/game-team/
    SKILL.md
    agents/openai.yaml
    references/                   # 共享流程与历史协议
    roles/                        # 完整角色指令，供命名角色不可用时按规则使用
    scripts/review_gate.py         # 保留的历史工具
```

**不要只复制仓库里的 `skills/game-team/` 目录安装。** 仓库保留原始源结构，由安装器把 `agents/` 和 `tools/` 的必要文件组装到个人包；安装后的 `skills/game-team/` 才包含完整角色与依赖引用。

重复安装会跳过字节相同的文件；替换不同内容前，在原目录保留唯一的 `.bak`、`.bak.1` 等备份。不改写 `config.toml`，不删除无关文件。三个已禁用评审的旧活动 TOML 若存在于目标的 `agents/`、本 skill 的 `roles/` 或历史评审引用目录，会归档为 `.toml.disabled`；重名归档保留为独立备份。

## 使用与岗位

在支持 skills 和自定义 agent 的 Codex 环境中，从实际目标项目调用：

```text
$game-team 接手当前小游戏，先核对本项目的 AGENTS、STATE 和路线，再推进一个最小可验证切片。
```

入口聊天承担小策；显式委派制作人时只保留一位负责产品调度与 STATE。岗位按任务需要调用，不要求同时开启全部角色。接手流程和隔离交付约定见 [共享工作流](skills/game-team/references/WORKFLOW.md)。

| 名字 | 真实角色 | 职责 |
| --- | --- | --- |
| 小策 | `game-producer` | 制作人兼主策，确定体验、范围、优先级与项目状态 |
| 小游 | `game-systems-designer` | 细化玩法规则、状态、教学和关卡 |
| 小算 | `game-balance-designer` | 维护难度、成长、资源经济与可复算参数 |
| 小岳 | `game-tech-lead` | 唯一技术负责人，隔离派工、逐提交审查和集成 |
| 小程 | `game-developer` | 在指定独立分支或 worktree 实现模块并自测 |
| 小谨 | `game-verifier` | 独立评审与验收明确候选版本，保留证据及未测项 |
| 小墨 | `game-art-lead` | 美术方向、样板与专家协调，和制作人领域平权 |
| 小绘 | `game-asset-artist` | 原画、角色、物件、场景与图标资产 |
| 小序 | `game-ui-artist` | 实际游玩尺寸的 HUD、界面状态与触控布局 |
| 小跃 | `game-vfx-artist` | 服务操作反馈和节奏的轻量动效与特效 |

小衡 `game-review-panel` 保留定义并随包安装，当前暂停主持。小川 `douyin-male-player-reviewer`、小禾 `douyin-female-player-reviewer`、小砚 `independent-game-art-reviewer` 已禁用；当前不调用，也不以普通 agent、复制指令或自评代演回退，三人完成票门暂停。小谨的独立验收及项目适用的前置、真人和平台门继续有效。

## 源结构与历史资料

本仓库唯一安装入口是 `tools/install_team.py`。三个历史文档 [完成评审协议](agents/COMPLETION_REVIEW.md)、[评审入口](agents/independent-reviewers/README.md)、[研究记录](agents/independent-reviewers/RESEARCH.md) 仅作档案和恢复参考，保留了旧调用、旧人数及旧安装说明；其中的 `install_reviewers.py`、`install_roles.py` 和三位评审调用方式不适用于当前包。三位已禁用评审的源 TOML 只留在 AgentBoard 源仓库，未收入这个公开包。恢复须用户明确要求，并先同步安装与当前规则；不要执行历史段落重新启用。

`skills/game-team/` 保存五个入口与共享流程源文件，`agents/` 保存十个生产岗位、暂停主持的小衡及上述历史文档，`tools/` 保存组装安装器和历史票门工具，`tests/` 保存两者对应单元测试。部分 skill 内部引用指向安装器生成的文件，应在完整安装产物中读取。

## 依赖与权限边界

安装器可离线运行。本包保留原角色的模型配置 `gpt-6.1-sol`；实际可用模型、agent 调用能力和并发数取决于运行环境与账号配置。安装本包不附带 Codex 运行时、图像模型、游戏引擎、浏览器工具、GitHub 或云端权限。

每个项目单独确认适用 AGENTS、Git 根、STATE、引擎/平台和授权。维护团队配置不会自动启动游戏生产；看板默认不接入，未接入不创建 run/parent 或发送上报。本包不继承 AgentBoard 的发布、GitHub Pages 或 Supabase 授权，也不包含凭证或运行数据。角色指令是协作约定，实际工具权限仍由宿主环境控制。

安装检查和单元测试验证的是配置、打包与历史工具行为；submitted、合入或测试通过均不代表游戏体验、真机或平台验收通过。

## 本地检查

```shell
python -m unittest discover -s tests -p test_install_team.py -v
python -m unittest discover -s tests -p test_review_gate.py -v
python tools/install_team.py --check
```

测试使用临时目录和合成票据，不安装到个人配置，也不产生真实评审结果。
