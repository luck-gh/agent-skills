# Windows install local settings

只有当前工作已经锁定 x64 或 x86,确实需要安装根,且当轮没有显式提供对应根时读取本说明.仅规划或只读审计不需要目标路径时不得读取 settings.

## Location and fields

从当前 `SKILL.md` 所在的 physical skill dir 读取同级 `settings.json`.不得读取环境变量来改变位置或搜索其他目录.随 skill 分发的 [settings.example.json](../settings.example.json) 只说明字段结构,不提供安装根.文件只允许以下两个 optional 字段:

```json
{"install_x64":"D:\\Program Files","install_x86":"D:\\Program Files (x86)"}
```

- 当前架构为 x64 时只选择并验证 `install_x64`;当前架构为 x86 时只选择并验证 `install_x86`.
- 不读取,要求或验证另一架构的值.所选字段必须是当前存在的绝对目录.
- 不允许 unknown 字段,package cache,staging,timeout,retry,容量下限,来源限制,动作批准,安装状态或凭据.

把实际选定的根以单键 JSON object 通过 stdin 交给 `scripts/check_install_roots.py`.只有返回 `ok` 才能作为候选;ACL,动态容量,冲突和精确目标授权仍在每次真实操作前检查.

## Missing or invalid settings

文件缺失,JSON 损坏,含 unknown 字段,缺少当前字段或当前路径不可用时,只询问当前架构的根.Example 只能用于确定字段和展示格式,不得作为安装根或自动复制为 settings.不得搜索旧 profile,其他 skill settings,环境中的其他路径或历史副本.当轮显式根始终优先,可以直接用于当前操作,不要求先持久化.

只有用户明确要求保存,且当前架构的真实值已通过 `check_install_roots.py` 时才创建 settings.不得创建空文件,占位文件或自动从 example 初始化.从当前 `SKILL.md` 精确确定同级目标;目标不存在时原子 no-clobber 创建,已存在且逻辑内容完全相同视为幂等,内容不同则停止,不得合并或覆盖.写后重新读取,选择相同架构字段并重跑 `check_install_roots.py`.

Settings 只提供路径候选,不授权创建目录,下载,校验,执行,提权,安装,修改系统,重启或清理.
