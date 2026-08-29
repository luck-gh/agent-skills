# Windows helper,工具启动与沙箱诊断

仅在已经观察到 helper,工具启动或 sandbox 异常,或需要选择最小只读替代工具时读取本引用.

## 按直接证据分类

| category | 直接证据 |
| --- | --- |
| `policy_denial` | 宿主明确返回沙箱或审批拒绝 |
| `missing_tool` | 发现结果明确表明工具或依赖不存在 |
| `tool_start_failure` | Windows 拒绝创建进程,加载映像或访问可执行文件 |
| `helper_failure` | helper 明确崩溃或返回自身故障 |
| `unresolved_helper_failure` | 只有通用 helper 错误,没有可定位的子错误 |
| `command_runner_failure` | setup 已成功,但宿主未能创建或管理目标命令进程 |
| `command_failure` | 工具已经启动并返回自身退出状态或结构化错误 |
| `sandbox-path-specific_failure` | 外部执行成功,普通 sandbox 路径仍失败,但具体根因尚未证实 |
| `unknown_outcome` | 无法证明是否启动,完成或产生部分效果 |

保留安全化后的工具名,操作类型,工作目录,退出状态或原始错误码,尝试次数和观察结果.不要默认保存完整命令,环境,内容或未经脱敏的长日志,也不要让类别互相冒充.

## 处理 `helper_unknown_error`

将 `helper_unknown_error` 视为基础设施故障候选,不把它当作目标路径,命令逻辑或宿主政策的结论.它也不能证明命令未开始或未产生部分效果.

- 只读命令:保留错误和范围.仅在直接证据证明原命令未执行,宿主允许且替代方式明显安全时,使用一次最小替代检查;否则停止并报告.
- 写入,移动,删除,安装,提交等状态变更命令:不要立即重放.先用只读检查核对目标存在性,内容或元数据;已完成则不重复,状态不明或可能部分完成则记为 `unknown_outcome` 并停止.
- 同一失败不要通过等价 shell,转义变体或提权循环重试.写操作结果 unknown 时重试次数为零.
- 只有错误或当前时段证据明确指向 setup refresh 时,才进入 [Windows sandbox setup refresh 诊断](windows-sandbox-setup.md);只有通用错误时保持 `unresolved_helper_failure`,不得直接读取历史 setup 日志或修改权限.

## 处理 `tool_start_failure` 并选择工具

Windows 拒绝启动 `rg` 或其他外部工具时:

1. 记录工具,原始错误,工作目录和一次尝试,不泛化为所有 shell 或工具不可用.
2. 不再次探测该可执行文件,不试多个 shell 变体,不提权运行失败工具.
3. 当前任务确需只读发现时,选择宿主已可用且范围更窄的能力,例如限定目录的 `Get-ChildItem`,指定文件的 `Get-Content` 或指定模式的 `Select-String`.
4. 替代检查也失败或结果不足时停止;不要用更宽扫描弥补证据缺口.

WindowsApps 内 bundled `rg.exe` 返回 Access Denied 是 `tool_start_failure`.即使它与 helper 错误同时出现,也要建立独立证据链;它不能证明 setup helper 失败,setup helper 失败也不能证明 bundled 工具不可执行.

把工具发现与 PowerShell 选择作为同一次操作判断:

- 当前宿主 shell 足够时直接使用,不额外寻找 shell.
- 确需显式 PowerShell 或外部工具时,使用宿主提供的发现能力核对候选当前存在,为预期 leaf 类型,并按任务需要核对身份和版本;发现路径不等于可启动,可信或已获授权.
- 在仍属安全只读且宿主允许时,最多使用一次无副作用的最小启动 probe.候选冲突,身份不符,来源不可信或状态 unknown 时停止,不按搜索顺序猜选.
- 不使用固定 PowerShell,helper 或作者目录路径,也不创建固定 fallback 或白名单.

## 处理 sandbox 异常

- 只有宿主明确说明越界或需要审批时才使用 `policy_denial`;普通失败,Windows 启动拒绝和 helper 故障都不构成提权依据.
- 将 setup refresh,command runner 和目标命令自身失败分开:setup 负责准备 sandbox 状态;runner 负责创建或管理进程;目标命令只有在已经启动后才可能返回自身失败.上一阶段成功不能证明下一阶段成功.
- 遵循宿主当前的编辑和审批流程;不要用 PowerShell shell 写入替代规定的编辑工具,不建议审批前缀或更改 sandbox 配置.
- 写入报错后先核对文件是否已经变化,再决定是否仍有获授权且安全的下一步;不得盲目重复可能有副作用的命令.
- 如果失败工具与可执行任务无关,只记录证据并继续独立的安全工作;不要为了“确认”故障而扩大读取或执行范围.

## 处理 Git `dubious ownership`

- 只有 Git 已明确返回 `dubious ownership` 时才进入本路由.核对当前用户与精确仓库 `.git` 的 Owner;Owner 不匹配时,将其作为独立的 Git `command_failure`,不推导 helper,setup 或工具启动根因.
- 不使用全局 `safe.directory` 绕过所有权检查.只有当前证据与 Owner 不匹配吻合且用户明确授权修复时,才将精确 `.git` 目录 Owner 改为预期用户,并保留 DACL.
- 修复前展示精确目标,Owner/DACL,最小变化,UAC 需求,回滚依据和验证方法.普通令牌不能更改 Owner 时才请求可见 Windows UAC;处理 0 个对象或 Owner 未变化表示修复未应用.
- 修复后在普通非提权路径复核 Owner 和 Git 只读状态.若同时存在 sandbox/helper 问题,仍需分别完成对应验证;缺少最新 setup 证据时只能报告功能恢复,不能声称 helper 已完整修复.
