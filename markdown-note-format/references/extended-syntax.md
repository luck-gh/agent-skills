# 扩展 Markdown 语法

只在调用方已完整提供 format profile 定义,目标 renderer 支持信息和允许的变换时生成以下候选.维护既有内容时保留已工作的方言和 code fence 类型.本 reference 只约束候选文本,不读取,导出或创建任何资源.

## 公式

- 保留既有有效公式及其方言.只有 renderer/profile 已确认支持且 body transform 允许时,才新增或转换标准行内/独立公式.
- Renderer/profile 未知时保留原值并报告缺口,不要加入公式语法教程,符号对照表或推测性转换.

## 图表选择

- 新建普通流程图,时序图或甘特图时优先使用 fenced `mermaid` code block,并分别以 `flowchart`,`sequenceDiagram`,`gantt` 开始.既有 Mermaid `graph` 保持不变.
- 组件,部署,活动,Timing 等 UML 图或 Mermaid 不适合表达的 UML 意图优先使用 PlantUML.使用 renderer/profile 已确认的 fence;`puml` fence 包含 `@startuml` 与 `@enduml`,既有其他有效 fence 保持不变.
- 只有目标 renderer 明确支持且 ASCII 源文本本身需要保持可读时才使用 ditaa.保留既有 fence 参数和正文,不为统一风格改写.
- `flow` 和 `sequence` fence 只用于维护既有 legacy 内容,不作为新候选默认,也不自动迁移为 Mermaid.不同图表方言之间均不自动转换或降级.
- Renderer 能力未知时不新增或转换 renderer-dependent 图表.保留既有 fence 和正文并报告缺口;若完整候选必须依赖新图表,报告格式阻塞.

## draw.io

- 将 `.drawio` 作为可编辑源资源,不是 Markdown 图片.既有 resource ref 按适用调用契约保持原值;只有调用方提供稳定 resource ID,受控 source-to-target 映射且允许 resource-refs transform 时,才新增或调整该 ref.允许 body transform 时可加入普通源文件链接,不得把 `.drawio` 用作图片 target.
- 正文预览只引用调用方已提供并映射的 `.svg` 或 `.png` 导出.源文件和预览分别保留受控 resource refs;只有源文件时不构造图片引用,调用方明确要求预览时报告缺失映射.
- 不内嵌或解析 draw.io XML,不转码,导出,复制或创建源文件与预览.所有路径继续遵守 request 的受控相对资源布局.
