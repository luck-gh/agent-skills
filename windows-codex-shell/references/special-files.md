# Windows 特殊文件与复杂目录

仅在用户明确指定 junction,symbolic link,reparse point,或请求评估复杂目录,跨卷,链接边界风险时读取本引用.保持只读,不把诊断授权扩展成维护授权.

## 只读核对特殊文件

1. 对用户提供的路径做不解析链接的绝对规范化,确认脱敏后的精确 link object.不存在,拒绝访问或类型不明时报告 `unknown`,不要猜替代路径.
2. 使用 literal-path 的只读元数据检查,记录 `FullName`,`Attributes`,`LinkType` 和未经解释的 raw `Target`.raw target 可能是相对路径,数组或 NT 路径,不能单独证明最终身份.
3. 在授权范围内使用真正解析 link target 的 API 独立取得 resolved identity,例如 PowerShell 7/.NET 的 `FileSystemInfo.ResolveLinkTarget(true)` 或语义等价的 Windows API.`Resolve-Path` 只能规范化 provider 路径,不得充当最终 identity.
4. 始终分开记录用户指定的 link object,raw target 和 resolved target;不要把解析目标误写成用户指定路径.
5. 检查前后再次读取并比较 link object 的类型,raw target 与 resolved identity.对象消失,值变化,解析失败或证据冲突时,视为竞态或 `unknown` 并 fail closed.
6. 只报告最小化且脱敏的证据;不创建,删除,移动,改写或修复 entry.

## 评估复杂目录风险

- 递归目录操作遇到 junction,symbolic link 或其他 reparse point 时可能越过字面目录边界;不要把解析后的子树自动纳入用户授权范围.
- 跨卷移动通常不等同于同卷原子重命名,可能包含复制与删除阶段;失败时不能仅凭源或目标存在性判断完整成功.
- 在任何专门实施流程之前,分别明确字面源和目标,resolved identities,卷边界,链接边界,名称冲突策略,恢复路径和内容/元数据验证方式.
- 任一边界,冲突,恢复或验证条件不明确时停止并报告,不猜测覆盖,合并,跟随链接或删除源的策略.
- 本 skill 只提供风险取证,不执行复杂目录移动,跨卷迁移,junction 改写或冲突合并;如用户要求实施,交由符合当前宿主破坏性操作规则的专门流程重新确认授权.
