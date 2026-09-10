# Repository update contract

只在用户明确询问已安装 Skill 的更新或授权升级时读取本说明.普通创建,修改,使用,验收与只读内容审查不加载本流程,不检查远端或写更新状态.本流程管理已安装软件的更新,不研究设计参考项目.

## Check timing

- 先核对范围:检查本身会 fetch 或请求网络并写用户级状态,不是只读命令.只读限制,禁止联网或范围不允许写状态时不运行,报告未检查及原因.命令依赖同级有效 `settings.json`;缺失时不得仅为 TTL 检查补建配置,记录跳过,当轮目标仍可使用显式路径.
- 范围允许且用户明确询问是否有更新时运行 `check --force --json`,绕过 24 小时 TTL;同一次获准更新任务中的重复检查可运行 `check --json` 复用有效状态.网络不可达时报告检查失败,不把它当成本地 Skill 不可用,不自动重试或阻塞无关工作.
- 同批任务共享更新状态时,只指定一个检查所有者,其他执行方接收目标范围,检查时间,结果及跳过原因.只复用同一来源且范围覆盖当前目标,仍在 TTL 内,期间配置或安装状态未变的证据;需要重查时仍由该所有者串行执行.这是任务编排约定,不代表脚本提供跨独立进程锁.
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

没有安装基线,本地内容偏离基线,来源不匹配或目录含链接时阻止覆盖.内容哈希排除 `settings.json`,`tools/local/`,`test-output/` 和 Python/Git 缓存,这些本机状态不构成 Skill 修改.升级前临时备份目标目录,本机 `settings.json` 和 CLI lock;通过固定的 `skills@1.5.21` 重复 `--skill` 更新变化项.成功后恢复 settings,运行 validator,核对 manifest 哈希并写入新基线;失败恢复原目录和 lock.更新包含 `new-skills` 自身时,当前流程结束后提示重启 Agent.
