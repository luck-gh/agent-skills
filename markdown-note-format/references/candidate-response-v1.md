# Capture candidate adapter v1

仅在调用方显式提交 `capture-note-plan` v1 时加载本 reference.公共 Markdown 调用使用 `SKILL.md` 的普通候选输出.本 adapter 只冻结脱敏内存 JSON transport;它不选择 source item,scope,collection,operation 或权限.

## Capture 在调用前完成的决定

Capture 必须先完成并显式提供:

- 已选择且已脱敏的 source items,完整内容和稳定 opaque IDs.
- caller-selected collection/scope,目标 operations 和 root-relative POSIX targets.
- 每个 operation 的 allowed transforms,逻辑 `format_profile` 和显式 profile allowlist.
- 已知 evidence 摘要,metadata,taxonomy,资源映射与 canonical request digest.

Markdown 层不得补做来源发现,知识价值判断,collection 选择,隐私确认,授权或写入计划.

## Frozen request

Capture 的 `src/candidate_contract_v1.py` 是 exact schema 和限制的唯一实现.Request 顶层固定为:

```text
schema,version,direction,max_hops,request_id,scope,items,operations,request_digest
```

固定值为 `capture-note-plan`,v1,`capture-to-markdown`,`max_hops=1`.每个 item 只含 `item_id`,`content`,`evidence`;content 只含 `title`,`body`,`frontmatter`,`taxonomy`,`resource_refs`.每个 operation 只含 `operation_id`,`item_ids`,`target`,`transform`,`format_profile`.

Transforms 只允许 `filename`,`frontmatter`,`taxonomy`,`body`,`resource-refs`,必须唯一且包含 `body`.Profile 必须是调用方 allowlist 中的 logical ID,无默认值.需要 split 时由 Capture 显式提供多个 operations/targets;Markdown 不自行扩大 operation 集合.

## Frozen response

成功响应固定为 `markdown-note-candidate` v1,方向 `markdown-to-capture`,`max_hops=1`.它只包含 request binding,candidates 和 `candidate_digest`.每个 operation 按原顺序恰好绑定一个 candidate;candidate 只含:

```text
operation_id,item_ids,filename,frontmatter,taxonomy,body,resource_refs
```

Body 必须是完整候选,不能是 patch,diff 或省略内容.未允许 filename transform 时保持 request basename;未允许 frontmatter,taxonomy 或 resource-refs 时返回对应空结构.最终 targets 经 Unicode case-fold 后不得冲突.

普通调用的 `format-change-plan` 不进入该冻结响应.Capture 根据自身已选 operations 和返回 candidates 维护任何上游计划,确认和动作语义.

## Fail closed

任何 parse,schema,profile,path,binding,digest 或 limit 错误只返回:

```json
{"direction":"markdown-to-capture","error":"invalid-contract-input","max_hops":1,"schema":"markdown-note-candidate","version":1}
```

错误不得回显 reason,field,path,input,ID,digest,question 或 callback.

## Canonical and safety rules

- 只接受无 BOM,无多余空白的 canonical strict UTF-8 JSON.拒绝 duplicate/unknown key,`null`,bool-as-int,NaN/Infinity,控制字符和非 NFC 文本.
- 拒绝嵌套的 root/privacy/confirmation/authorization/profile/write/callback/pair/execute/commit/push 和 secret-like keys.`format_profile` 只是冻结 schema key.
- Path 只接受 scope 内 root-relative POSIX 形式.拒绝 absolute,UNC,drive,URL,反斜杠,percent encoding,空 segment,`.`/`..`,device name 和尾随空格/点.
- `request_digest` 和 `candidate_digest` 只绑定内存 canonical JSON,不读取文件,不计算 before/after 或 write-plan hash.
- 统一上限由实现中的只读 `LIMITS` 固化:input `262144` bytes,depth `16`,nodes `4096`,单容器 `128`,普通 string `32768` UTF-8 bytes,body `131072` UTF-8 bytes,resource refs `64`.窄字段上限以实现为准.

## Capture 调用方式

1. Capture 选择 items,scope,collection,operations 和 authority boundary,完成脱敏后构造 request.
2. Capture 传入 canonical request bytes 和非空 logical profile allowlist,调用 `parse_request`.
3. Markdown 只依据 request 已允许的 transforms 和格式 references 生成完整 candidates.
4. Capture 调用 `parse_response` 校验 binding,digest,paths 和 exact shape.
5. Capture 独立决定是否展示,确认,规划或执行任何动作.候选响应本身永远不授予这些能力.
