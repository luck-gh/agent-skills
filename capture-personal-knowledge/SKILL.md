---
name: capture-personal-knowledge
description: 从项目实施,排障过程或聊天记录中判断知识价值,并在 note,memory,no-save 三条路径间选择目标,控制证据,隐私,脱敏,写入意图,写入事务与写后验证.用于用户要求吸收,记住,记录或复盘可复用经验时;只有 note 路径调用 $markdown-note-format,不用于仅格式化已确定的 Markdown 内容.
---

# 沉淀个人知识

把用户提供的一次性上下文提炼为可检索,可复用的经验.不要机械复制聊天或日志.把知识价值,source items,目标路由,隐私,目标,写入意图和所有写入状态保留在 Capture.

## 先决定路由

1. 只分析用户在当前请求中提供或明确授权使用的材料.提取结论,适用条件,证据,验证状态,潜在关联和不确定项.剔除一次性状态,重复片段和纯个人流水.
2. 在本地判断敏感性并先脱敏.不得把凭据,token,个人地址,个人绝对路径,附件原文或受限第三方内容放入候选请求,测试夹具,shell,argv 或日志.脱敏会破坏知识价值或目标不清时,先取得用户确认.
3. 明确选择且只选择一条路径:
   - `note`:需要持久笔记,collection 结构或 Markdown 候选时选择.只有此路径可以加载 collection 配置和调用 `$markdown-note-format`.
   - `memory`:需要写入真实 memory backend 时选择.不得加载 collection,settings 或 Markdown.只有当前存在真实 memory 工具且用户授权本次写入时才执行;否则只返回建议 payload 和 `unsupported` 或 `authorization_required`,不得声称已保存.
   - `no-save`:用户只要复盘,清单或不值得保存时选择.返回结论及不保存理由,不得加载 collection,settings,Markdown 或 memory 工具.
4. 不把复盘自动升级为持久化.用户当轮明确要求记录,写入或批量生成笔记时,该指令授权符合请求范围的同批 `create` 操作,无需再次展示完整候选,审批 digest 或逐项批准 operation.仅要求复盘,预览或 `no-save` 时不得写入;覆盖,迁移,拆分,修复等非 create 动作必须已由用户明确要求,否则先询问.

## Note 路径

只有选择 `note` 后才执行以下流程:

1. 当轮显式提供的完整 `collections` object 始终优先.未提供时才从当前 physical skill dir 读取与 `SKILL.md` 同级的 `settings.json`.只接受唯一字段 `collections`,并把完整 object 通过 stdin 交给 [collection validator](scripts/validate_collections.py) 的 `--json` 模式完成结构与路径业务校验.缺失,损坏,字段不完整或路径不可用时按 [本地设置](references/local-settings.md) 只询问必要值,不得搜索其他位置.
2. 选择 collection,最小 scope,renderer/profile 和本次 operations.配置值只描述候选边界,不授权读取,搜索,建目录,写入或 Git 操作.不得猜路径,使用作者路径或读取 `.obsidian`,缓存和工作区文件.
3. 只有用户授权进行重复检查或更新定位时才读取或搜索真实 collection.每次 I/O 前执行下述预检,且只访问当前 include 并排除所有 exclude.纯 create 规划不要求先扫描 collection.
4. 完整读取 [Capture note plan 与候选绑定](references/capture-plan-contract.md).先完成选择和脱敏,再构造 canonical `capture-note-plan` v1,传入由 Capture 选择的显式 profile allowlist,交给 `$markdown-note-format` 生成候选并用 Capture 自有 adapter 校验.
5. 保留 create,migrate,split,repair 或 review 意图和 allowed transforms.Split 必须由 Capture 显式提交多个 operations/targets;不得让 Markdown 扩大操作集合.
6. 用 [note-plan validator](scripts/validate_note_plan.py) 校验候选与 request 的 ID,digest,operation,item,scope,target,profile,transform 和最终路径绑定.配对通过后才读取精确 update 目标并计算 `before_hash`,再构造 Capture 本地 write plan.`write_plan_digest` 只用于执行器核对计划在构造后未被篡改,不是用户批准凭证.
7. 将当轮写入意图绑定到允许的 operation 类型和请求范围.明确的批量写入指令可直接执行同批 `create`;无需在写入前展示完整候选,精确目标或 digest.若计划包含用户未明确要求的覆盖,迁移,拆分或修复,停止并只询问缺失的动作意图.
8. 用 `src/transaction_executor.py` 的事务实现执行 create/update,并把构造阶段返回的 `write_plan_digest` 作为内部完整性值传入.每项副作用前重新做 write preflight.Create 使用原子 no-clobber 发布;update 没有宿主提供的真实原子 before-hash CAS 时返回 `unsupported`,不写入也不虚构成功.
9. 每项成功后重新读取精确目标,核对完整内容和 `after_hash`;再只读报告相关 Git 状态.默认不 commit,绝不自动 push.

### Collection 预检

- 每次读取或搜索前调用 `preflight_collection(collection)`.Root 与实际 include/exclude 必须已存在,是目录,可读且可遍历;缺失时返回 `configured_location_unavailable`,不得创建.
- 从 root 逐段 join scope,逐段 `lstat`,拒绝 symlink/reparse,确认 canonical identity 仍位于 canonical root.不得用目录枚举代替 metadata 检查.
- 每项副作用前调用 `preflight_collection(collection, require_write=True)`,重新检查 root 与实际 scope 的读,遍历和写权限.一次结果不能复用到下一项;状态未知时 fail closed.

## 撤销与交付

用户撤销写入意图后立即停止新的 collection,文件,Git,配置,Markdown 或 memory I/O.只基于已取得且允许保留的脱敏状态报告停止结果.

交付时说明 route,候选总数,成功/冲突/跳过数量,证据状态和未决项.Note 路径默认报告实际目标和执行结果;内部 digest 与逐项 hash 仅在审计或排障需要时报告,不得要求用户批准.Memory 路径列出实际工具与授权结果;没有真实能力时明确说明未写入.No-save 路径只交付复盘和不保存理由.
