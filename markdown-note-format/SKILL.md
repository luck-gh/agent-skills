---
name: markdown-note-format
description: 为调用方已提供的内容生成或审查不落盘的 Markdown 格式候选与变更计划.用于创建,迁移,拆分或修复笔记时规范文件名,目录结构,YAML front matter,taxonomy,正文,图片路径,公式和图表;不发现或读取真实笔记库,不选择源笔记,目标 collection 或 memory backend,不判断知识价值或写入授权,不执行写入.
---

# Markdown 笔记格式候选

只处理调用方显式提供且已按上游要求脱敏的内容,约束和资源映射.生成完整候选与纯格式变更计划,不要读取或改变任何真实笔记.

## 必读引用

- 每次创建,迁移,拆分,修复或审查候选时,完整读取 [references/format-rules.md](references/format-rules.md).
- 涉及公式,图表语法或图表资源时,再完整读取 [references/extended-syntax.md](references/extended-syntax.md).
- 只有调用方显式使用 `capture-note-plan` v1 时,才完整读取 [references/candidate-response-v1.md](references/candidate-response-v1.md).严格 transport 的 adapter 由 Capture 所有并校验;本 skill 不持有调用方协议 Python,也不获得 I/O 或动作权限.

## 接受输入

要求调用方提供完成本次格式判断所需的最小集合:

- 已选择的 source item 及其稳定 opaque ID,完整正文和需要保留的 metadata.
- 操作意图:create,migrate,split,repair 或 review,以及本次允许改变的格式部分.
- 已选择的目标 collection/scope 和 renderer/format profile,或足够明确的现有格式惯例.
- 已知的时间,taxonomy,相邻顺序和资源映射.路径只作为调用方提供的逻辑相对标识,不得据此读取目标.

信息不足时保留既有值并列出缺口.若缺口使完整候选不可能,只返回缺失输入,不要扫描 collection,读取模板,猜测机器当前时间或伪造剩余正文.

## 生成流程

1. 核对 source item,操作意图,caller-selected scope/profile 和 allowed transforms.不要替调用方选择要吸收的笔记,目标 collection 或 memory backend.
2. 依据 `format-rules.md` 判断 filename,目录结构,frontmatter,taxonomy,正文和 resource references.只在必要时加载扩展语法规则.
3. 先建立 source-to-candidate 内容映射,再应用允许的格式变换.保留有效内容,metadata,链接语义,代码块和资源标识.
4. 对 create 或 repair 生成一份完整候选;对 migrate 或 split 生成全部完整候选和逐项内容归属.不要返回 patch,省略号或要求执行后才能补齐的正文.
5. 生成纯格式变更计划,描述拟议的 create/rename/move/split/repair 关系,资源引用调整,依赖和未决输入.把所有动作明确标成 proposal;不要生成写入步骤,事务计划或授权状态.
6. 检查名称,结构,frontmatter,标题,taxonomy,摘要,路径,公式/图表 fence 和内容保留.发现冲突时修正候选或报告格式阻塞,不得扩权解决.

## 普通调用输出

返回两个逻辑部分:

- `format-candidate-set`:为每个拟议文件给出绑定的 source IDs,operation,调用方 scope 内的相对 filename/location,完整 frontmatter,taxonomy,body,受控 resource refs 和内容保留说明.
- `format-change-plan`:给出 source-to-candidate 映射,拟议的格式变化,资源映射,前置依赖,未决输入和逐项验证结果.它只是候选说明,不是 write plan.

创建,迁移,拆分和修复都遵循相同边界.不得把候选,文件名或 change plan 表述为已获批准,已确认可写或已经执行.严格 Capture v1 响应保持其冻结 schema,不额外加入普通调用字段;由 Capture 保留并承担任何目标选择,确认,授权和写入计划.

## 边界

- 不发现,搜索,索引,读取或审计真实笔记库,collection,memory backend,机器 profile,环境变量或模板.
- 不判断知识是否值得吸收,不选择 source note,目标 collection/scope 或记忆体.只可在调用方已选 scope 内提出格式化的相对名称与结构.
- 不下载,复制,移动,重命名,创建,拆分,修复,删除或写入文件和资源.不验证链接目标是否存在.
- 不获取,推断,持有或回显 confirmation,authorization,approval,grant,permission,write state 或 callback.
- 不调用 shell,网络,其他 skill 或外部程序完成格式任务.严格 Capture adapter 只校验调用方传入的内存 JSON.
- 不把 format profile,路径,候选或变更计划当成 I/O 能力或动作授权.

## 中文标点

中文正文的标点风格由调用方 profile 决定.只有显式选择半角中文 profile 时才转换候选 prose;skill 指令和结构化说明统一使用英文半角标点.
