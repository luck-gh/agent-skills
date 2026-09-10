# windows-codex-shell

针对 Windows Codex 已经出现的 shell,helper,外部工具启动,sandbox 或 Git ownership 异常,按当前证据分类并确定最小下一步.也可对用户明确指定的 Junction/reparse point 和复杂目录操作做只读风险核对.

适合实际故障诊断与结果不确定的状态核实.普通读文件,搜索或 Git 查询无需启动本流程;它不是预防性系统优化器,也不管理 Codex 的白名单,helper 或审批配置.

## 安装与发现

从[公共仓库](https://github.com/luck-gh/agent-skills)取得完整 `windows-codex-shell/` 目录.公共下载只含已发布版本,本地未发布内容可直接接入当前工作区实体目录.

Windows Codex 用户级入口位于 `%USERPROFILE%\.agents\skills\windows-codex-shell`.可以安装完整实体目录,或用精确目录链接指向唯一实体,不要覆盖未知目标或重复复制.参见 [Codex 发现说明](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).输入 `$windows-codex-shell` 调用;列表未刷新时重启 Agent.其他平台的普通 shell 故障不属于该 Skill 的 Windows 诊断范围.

## 最小示例

```text
使用 $windows-codex-shell,诊断刚才工具返回的 helper_unknown_error.只使用当前故障时段和本次目录范围的证据,区分 runner、目标命令与 setup 失败.先只读核对,不要提权、修改 ACL、配置或重放写操作.
```

进阶用例:

```text
使用 $windows-codex-shell,上一次文件写入返回 unknown outcome.请只读核对该精确文件的实际状态,判断完成、部分完成或仍未知,不要再次执行写入.我会提供原操作、目标和期望内容,不扫描其他日志或目录.
```

检查目录链接时明确给出精确对象与只读范围.本 Skill 可以核对它,但不会创建,移动,修复或删除该对象.

## 输入,依赖与结果

提供症状,失败工具/命令,工作目录,目标,时间范围,期望结果和本次授权层级.先做一次作用域内只读 preflight,分别判断工具能力,宿主政策,可用性和用户授权;范围变化后重新核对.

输出包含分类,操作类型,目标范围,证据,缺失项,授权与下一动作.只有明确发生在 sandbox setup refresh 时才读取对应 setup 证据,不能从通用 helper 错误推断 ACL 根因.流程见[通用诊断](references/windows-diagnostics.md),[setup 分支](references/windows-sandbox-setup.md)和[特殊文件](references/special-files.md).

使用不需要 settings.确定性[证据分类工具](scripts/evaluate_windows_shell_evidence.py)使用 Python 标准库,接收已脱敏的最小证据;它不采集真实日志,修改 ACL 或启动 UAC.实际诊断需要宿主允许的 Windows 只读工具.当前脚本验收基线是 CPython 3.12 / Windows x64.

## 限制与验收

读取证据,制定修复计划和执行修复分别受授权约束.写入结果未知时先核实状态,不能循环重试或提权重放.普通工具恢复与 Git ownership 按各自分支验收;setup 修复还需要多个层面的成功及普通非提权最小进程连续三次成功,不能只凭一个命令成功宣称全部恢复.

已有分类器与边界回归,但历史修订的最终独立领域复核仍有缺口,本次 README 检查没有关闭它.静态检查不能证明实际 Windows 环境已修复或审批安全;没有足够证据时保持 unknown.

本 README 供使用者阅读,执行规则在 [SKILL.md](SKILL.md) 与必要引用.本目录按 [Apache License 2.0](https://github.com/luck-gh/agent-skills/blob/main/LICENSE) 分发.具体诊断结论来自当前故障证据,不把历史机器路径或经验当作当前事实.
