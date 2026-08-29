# New-skills local settings

只在当轮没有收到所需 physical root 或 usage root 时读取本说明.显式路径始终优先.

## Location and fields

从当前 `SKILL.md` 所在的 physical skill dir 读取同级 `settings.json`.不得读取环境变量来改变位置,也不得搜索 discovery entry,仓库根或其他目录.随 skill 分发的 [settings.example.json](../settings.example.json) 只说明字段结构,不提供运行时值.文件必须精确包含以下字段:

```json
{
  "physical_root": "<absolute-existing-directory>",
  "usage_root": "<absolute-existing-directory>"
}
```

- `physical_root` 必填,必须是当前存在的绝对目录,表示 consumer skill physical parent 候选.
- `usage_root` 必填,必须是当前存在的绝对目录,表示当前或目标 Agent 实际发现 consumer skill 的 parent.
- 不允许 unknown 字段,凭据,敏感正文,运行时状态,确认,批准或动作授权.

## First use

`settings.json` 缺失时执行一次首次配置:

1. 从用户指定的目标 Agent,或当前 Agent 的明确运行上下文与官方平台契约,确定该 Agent 的 canonical personal skill root.只允许核对这一条明确候选;不得扫描用户目录,搜索同名 skill,读取其他 settings,枚举历史位置或依据偶然存在的目录猜测.若无法可靠确定,把 usage root 与 physical root 一并询问,不得伪装成已检测.
2. 在一个简短问题中展示 Agent 和检测到的 usage root,要求用户提供 physical root,并说明只有需要改变时才同时给出 usage root.不要先单独询问 physical root,再追加一次地址确认.
3. 用户只回复 physical root 时即接受已展示的 usage root;用户同时修改 usage root 时采用修改值.验证两者都是现有绝对目录.用户提交 physical root 即授权创建这份首次默认配置,无需再确认最终二字段.
4. 立即原子 no-clobber 创建完整配置,重新读取,严格核对字段与当前路径可用性.任一步失败都不得留下空文件或部分配置.

“先不要创建文件”,“只预览”或类似限制默认约束用户请求创建的目标 Skill 与产物,不阻止完成 New Skills 启动所必需的 `settings.json`.只有用户明确说不要创建或修改 New Skills 的配置时才不写 settings,并报告本轮仅使用临时值.

Physical root 与 usage root 相同时,consumer skill 直接位于 Agent 使用地址,不创建 discovery entry.两者不同时,settings 仍只保存两个 parent;具体 skill entry 需要按主流程另行检查冲突并取得创建授权.

文件存在但 JSON 损坏,字段不符合契约或路径当前不可用时,报告失效项并询问本轮仍需要的值;不得把它当成首次缺失而自动覆盖.可用 example 确定字段和展示格式,但不得把占位符当成值或自动复制为 settings.

## Write boundary

首次配置按上述 physical root 回复创建 settings.其他场景只有用户明确要求保存或修改默认值,且完整真实值已通过验证时才能写入.不得创建空文件,占位文件或自动从 example 初始化.写前从当前 `SKILL.md` 核对精确的同级目标.文件使用 UTF-8 JSON,2 空格缩进,逐字段换行并保留末尾换行,不得压成单行.目标文件已存在时,完整 object 相同才视为幂等;内容不同时必须先展示变化并取得修改确认,然后以单文件原子替换写入,不得字段级合并.写后重新读取验证.

Settings 只提供路径候选.每次使用仍须检查当前目录状态,并为创建,移动,删除,复制,链接和其他副作用取得当轮授权.
