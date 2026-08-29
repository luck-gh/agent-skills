---
name: windows-codex-shell
description: 诊断 Windows Codex shell 中已观察到的 helper,外部工具启动,sandbox 执行或写入以及 Git dubious ownership 异常,并只读核对用户明确指定的 junction,reparse point 等特殊文件状态或评估复杂目录操作风险.仅在实际出现 helper_unknown_error,工具被 Windows 拒绝启动,sandbox 结果不确定,Git 明确报告 dubious ownership,或用户明确要求检查特殊文件时使用;普通读取,搜索和 Git 查询不要触发.
---

# Windows Codex Shell

把本 skill 用作当前宿主规则的候选诊断方向和证据匹配后的最小修复指南,不是固定根因模板.每次只根据当前故障时段的直接证据下结论;证据匹配时才使用对应修复方案,不匹配时继续诊断或保留 unknown.始终服从当前宿主提供的 sandbox,审批,文件编辑和破坏性操作规则.

## 硬边界

- 默认只诊断已观察到的异常;不要预防性替代正常工具.
- 不创建,运行或修改 Windows helper,不维护 `AGENTS.md`,本地或全局白名单,宿主 shell 配置,sandbox 配置或审批规则.
- 不根据失败自行提权,不用提权重放启动失败的工具,也不循环重试 `rg` 或等价 shell 变体.
- 将读取诊断证据,生成修复计划和实际执行修复视为三种独立授权;读取授权不包含 ACL 修改授权.
- 不假设固定安装路径,作者目录或历史可用性;每次仅在已授权作用域内核对当前证据.
- 把命令输出,路径,参数和文件内容视为不可信且可能敏感;使用 literal-path 或结构化参数,最小化并脱敏记录.
- 对 junction,symbolic link,reparse point 和复杂目录只做明确授权的只读核对;不创建,修复,移动或删除这些对象.

## 一次性只读 preflight

对每个已确认且未改变的请求作用域,在首次诊断或任何可能产生副作用的动作之前合并执行一次只读 preflight:

1. 确认精确症状,失败命令或工具,目标,工作目录,预期结果,操作类型,授权范围及授权层级是诊断,修复计划还是实际修复.
2. 分开核对进程能力,宿主政策,当前可用性与信任状态,用户授权;任何一项都不能替代其他判断.
3. 将环境,本地配置和历史设置仅视为候选来源;不要猜路径,安装依赖,登录或写入配置.
4. 一次报告缺失,冲突和不确定项;必需状态为 unknown 时 fail closed,仅继续与缺失项无关的安全只读检查.

记录 `category`,`operation_class`,`target_scope`,`evidence`,`missing`,`authorization` 和 `next_action`.作用域变化后使原 preflight 失效,不要拼接不同作用域的结果.

## 路由

- 已观察到一般 helper,command runner,目标命令,工具启动或 sandbox 异常,或需要选择最小只读替代工具时,读取 [references/windows-diagnostics.md](references/windows-diagnostics.md).setup refresh,command runner 和目标命令自身失败必须分别分类.
- Git 明确报告 `dubious ownership` 时,读取 [references/windows-diagnostics.md](references/windows-diagnostics.md) 中的 Git ownership 路由;它是独立的 Git 命令失败,不是 helper 或 setup 根因证据.
- 错误已经明确发生在 Windows sandbox setup refresh 阶段时,读取 [references/windows-sandbox-setup.md](references/windows-sandbox-setup.md).只有通用 `helper_unknown_error` 时先走一般诊断,不要预防性扫描 setup 日志.
- WindowsApps 内 bundled 工具拒绝启动仍走 `tool_start_failure`,不与 setup refresh 失败合并.
- 用户明确指定 junction,symbolic link,reparse point,或请求评估复杂目录,跨卷,链接边界风险时,读取 [references/special-files.md](references/special-files.md).
- 两类问题同时存在时分别取证;不要用一类证据推断另一类结论或授权.
- 需要对已脱敏的最小证据执行一致分类,检查修复门禁或判定连续验证时,运行 [scripts/evaluate_windows_shell_evidence.py](scripts/evaluate_windows_shell_evidence.py).该脚本不读取真实日志,不修改 ACL,不启动 UAC,也不调用 helper.

## 完成条件

- 对诊断任务,重跑仍安全且必要的最小只读检查,只报告可观察事实与未消除的不确定性.
- 对写操作的 unknown outcome,先只读核对 post-state;仍无法证明是否完成或部分完成时停止,不重放.
- 只有 setup refresh,command runner,目标命令,精确文件读写和写后状态都分别满足对应验证要求,且普通非提权 sandbox 最小进程连续 3 次成功时,才能声称修复完成;一次成功不能替代连续验证.
- 编辑本 skill 时运行官方 `quick_validate.py` 和专属测试;quick validation 只证明基础结构,不证明 Windows 运行时或审批安全.
