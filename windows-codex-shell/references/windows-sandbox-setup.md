# Windows sandbox setup refresh 诊断

仅在错误或当前故障时段的直接证据明确指向 Windows sandbox setup refresh 时读取本引用.只有通用 `helper_unknown_error` 时返回一般诊断,不要预防性扫描日志.

## 诊断顺序

1. 记录原始错误签名,操作类型,工作目录,精确目标,诊断授权范围和当前授权层级.先判断失败发生在进程创建前,命令执行中还是命令执行后.
2. 只有已观察到 setup refresh 错误后,才在宿主允许的当前 Codex sandbox 诊断目录中检查与当前故障时段对应的证据.不要猜测固定目录或版本路径.
3. 检查 setup error 文件是否存在;再检查 setup marker 是否存在,当前进程能否读取及其 ACL 状态.存在不等于可读,可读不等于内容有效.
4. 优先读取有限尾部或围绕错误模式的最小上下文.日志过大,结果被截断或时间边界不清时记录证据不完整,不得导出全部历史日志或声称已经完整检查.
5. 从有限片段提取精确失败阶段,对象,Windows API 或错误码.保留完成分类所需的最小脱敏内容,不要保留完整命令,环境变量,用户名,私有路径,工作区名或文件内容.
6. 只有日志明确指向工作区 DACL 时,才读取已解析并验证的精确工作区根目录 Owner 和 DACL.不要因为工作区可读写或位于移动硬盘就扩大检查范围.
7. 分开判断普通文件读写能力,目录 `WRITE_DAC`,Owner,当前令牌和 Windows 管理员令牌.必须保持:

```text
用户能正常读写文件
!=
用户能修改目录 DACL
!=
Codex sandbox 账户已经获得所需 ACE
```

8. 输出直接证据,缺失项,诊断结论,授权层级,修复门禁,最小 handoff 和验证要求.版本相关签名只能作为当前机器的已观察证据,不能成为唯一判断依据.

## 诊断映射

| 直接证据 | 分类 | 结论 |
| --- | --- | --- |
| `write ACE grant failed` 和 `SetNamedSecurityInfoW failed: 5` | `workspace_dacl_failure` | setup 进程不能修改精确工作区 DACL |
| marker 存在但当前进程无法读取 | `marker_acl_failure` | 正常 Codex 进程无法验证 setup 状态 |
| setup 日志为 `errors=[]`,但 runner 仍失败 | `command_runner_failure` | setup refresh 已完成,故障位于进程启动阶段 |
| WindowsApps 内 bundled `rg.exe` 返回 Access Denied | `tool_start_failure` | bundled 工具不可执行,不等于 helper 失败 |
| 只有通用 `helper_unknown_error` | `unresolved_helper_failure` | 证据不足,不能直接修改权限 |
| 写命令返回 helper 错误且无法确认执行状态 | `unknown_outcome` | 必须先检查 post-state,不得立即重放 |
| 外部执行成功,普通 sandbox 失败 | `sandbox-path-specific_failure` | 目标命令本身可能正常,但不能直接推断具体 ACL 根因 |
| ACL 修改命令报告处理 0 个文件 | `repair_not_applied` | 修复没有生效,不能声称已修复 |

`write ACE grant failed` 或 `SetNamedSecurityInfoW failed: 5` 单独出现时可以形成 DACL 故障候选,但要明确缺失的配对证据.普通文件可写而 `WRITE_DAC` 缺失时,应归类为 DACL 能力不足,而不是普通文件权限失败.工作区位于移动硬盘不等于硬盘故障;没有磁盘或文件系统直接错误时不得作硬件归因.NTFS Owner 和 ACL 可能来自其他系统或旧账户,但只能作为待核对解释.旧版本曾正常也不能排除当前 ACL 问题,因为 sandbox 所需 group,capability SID 或 ACE 刷新要求可能变化.

## 日志读取和隐私边界

- 只读取当前故障时段内完成分类所需的有限尾部或错误模式上下文.没有时间边界时先缩小范围,不要默认读取完整文件.
- 路径,用户名,SID,命令,环境变量,工作区名和私有文件名在输出前脱敏.测试只保存匿名字段和最小错误签名.
- 截断输出,不完整 tail,无法读取的区段或过大的日志必须记录为 `evidence_incomplete`;不得把局部片段描述为完整历史.
- 不把完整日志,命令内容,环境变量或用户文件内容复制到 fixture,报告或修复 handoff.
- setup error 文件和 marker 都是诊断状态,不自动删除,改写或重建.

## 授权层级与修复门禁

默认授权层级为 `diagnose_only`.必须明确区分:

| 授权层级 | 允许内容 |
| --- | --- |
| `diagnose_only` | 最小只读取证,分类,缺失项和验证要求 |
| `repair_plan` | 生成精确目标,前置条件,回滚依据和 post-state 验证的 handoff,不执行 |
| `repair_execution` | 仅在全部门禁满足且宿主允许时,交给宿主允许的专门执行器 |

只有同时满足以下条件,才能生成可执行修复 handoff 或实际执行最小修复:

- 用户在当轮明确授权相应层级;读取授权不能推导出计划或执行授权.
- 当前时段日志明确指出精确失败对象,且不是只有通用 helper 错误.
- 已记录修复前 Owner 和 DACL,并区分普通文件写权限与 `WRITE_DAC`.
- 目标是经过解析和验证的单一精确工作区根目录;拒绝盘符根目录,用户目录,WindowsApps,相对路径,未解析变量,通配符和范围不明的路径.
- 宿主规则允许该动作,方法具有明确 post-state 验证和基于修复前 ACL 的回滚依据.
- 已确定外部执行只是离开 Codex sandbox,还是确实需要 Windows 管理员令牌.`require_escalated` 成功不等于获得管理员令牌,更不等于 ACL 已改变.

本 Skill 默认采用以下执行边界:

```text
诊断完成
-> 生成精确修复 handoff
-> 等待用户当轮明确授权
-> 交给宿主允许的专门执行器
```

如果当前宿主没有合适的专门执行器,停在 handoff.真正需要管理员令牌时,授权步骤必须向用户显示精确目标和拟议权限变化,由用户可见确认 Windows UAC;不得静默触发或把可提权运行当作目标权限已经修复.

### 禁止动作

- 修改整个盘符,或递归给整个移动硬盘或用户目录授予完全控制.
- 获取 WindowsApps 所有权,禁用 Defender,防火墙或 EDR,删除整个 `.codex` 目录.
- 自动删除 setup marker 或 sandbox 状态,永久以管理员身份运行 Codex.
- 在没有精确日志证据时修改 ACL,或修复失败后扩大范围重试.
- 用 PowerShell,Python 或其他写入方式绕过宿主规定的编辑工具或审批边界.
- 因为工作区位于移动硬盘就修改整盘权限或执行磁盘修复.

## 最小权限修复 handoff

日志明确证明工作区根目录缺少 DACL 修改能力时,修复目标只能描述为:

```text
使当前用户能够修改精确工作区根目录的 DACL,
从而允许 Codex sandbox setup helper 添加所需的 sandbox group 和 capability SID ACE.
```

不要默认递归授予完全控制.如果专门执行器提供命令候选,必须:

1. 参数化并再次解析精确目标,拒绝盘符根目录,用户目录,WindowsApps,相对路径,变量和通配符.
2. 先读取并记录修复前 Owner 和 DACL,说明回滚依据.
3. 说明命令只是离开 sandbox,还是确实需要 Windows UAC.
4. 检查真实退出状态和实际处理对象数量.处理 0 个文件时分类为 `repair_not_applied`.
5. 重新读取精确目标 ACL 验证期望变化;不能仅根据退出码,可提权运行或 UAC 出现推断修复完成.

任何命令都只是当前机器直接证据支持下的候选,不能声称适用于所有机器.不得硬编码用户名,SID,盘符,工作区路径,安装版本或私人目录.

## 修复后验证

全部验证都在普通,非提权路径完成,并分别记录 setup,runner,目标命令,文件写入和写后内容:

1. 连续 3 次启动普通非提权最小 sandbox 进程;任一次失败都重新开始连续计数,不能判定稳定修复.
2. 最新相关 setup refresh 日志明确显示 `errors=[]`.
3. 精确工作区文件读取成功.
4. Git 只读状态查询成功.
5. 宿主规定的编辑工具完成一次小范围受控写入.
6. 写后内容和 Git 状态核对成功.
7. setup error 文件已经消失,已更新,或可证明不再对应当前失败.
8. 无关警告单独记录,不扩大修复范围.

`require_escalated` 成功但 ACL 未改变,修复命令处理 0 个对象,证据被截断,或上述任一验证缺失时都不能声称修复完成.一次成功不能证明稳定修复.
