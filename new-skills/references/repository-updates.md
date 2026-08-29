# Repository update contract

只在 `new-skills` 被用于安装,创建,更新,迁移,移动,修复或验收,用户显式询问更新,或用户授权执行已发现更新时读取本说明.

## Check timing

- 用户显式询问是否有更新时运行 `check --force --json`,绕过 24 小时 TTL.
- 生命周期任务开始时运行 `check --json`.自动检查失败不得阻塞当前任务;先完成任务,再报告失败摘要或更新提示.
- 发现更新时先完成当前任务,再展示变化项.没有用户明确确认时不得运行 `apply`.

```text
python -X utf8 -B scripts/manage_updates.py check --json
python -X utf8 -B scripts/manage_updates.py check --force --json
python -X utf8 -B scripts/manage_updates.py apply --expected-update-id <id> --authorized --json
```

## State and credentials

更新状态不写入 Skill 或仓库.Windows 使用 `%LOCALAPPDATA%\new-skills\update-state.json`;POSIX 使用 `${XDG_STATE_HOME:-~/.local/state}/new-skills/update-state.json`.状态只含上次检查时间,公开快照 ID,逐 Skill 安装基线哈希和失败摘要,不保存凭据.

## Modes

当 `physical_root` 位于有效 Git 工作树时使用 Git 模式.`check` 执行 fetch 并比较 upstream;只有分支可 fast-forward,工作区干净,update ID 未变化且用户明确授权时,`apply` 才执行 `git pull --ff-only`.ahead,diverged,detached 或 dirty 状态都不自动修复.

非 Git 的公共安装使用 `luck-gh/agent-skills` 的 schema v1 manifest.只管理 `.agents/.skill-lock.json` 中来源精确为该仓库,并位于 canonical `~/.agents/skills` physical root 的 Skill.只更新已安装且哈希变化的 Skill;新增 Skill只列为 available,retired Skill 只提示而不删除.

没有安装基线,本地内容偏离基线,来源不匹配或目录含链接时阻止覆盖.升级前临时备份目标目录,本机 `settings.json` 和 CLI lock;通过固定的 `skills@1.5.21` 重复 `--skill` 更新变化项.成功后恢复 settings,运行 validator,核对 manifest 哈希并写入新基线;失败恢复原目录和 lock.更新包含 `new-skills` 自身时,当前流程结束后提示重启 Agent.
