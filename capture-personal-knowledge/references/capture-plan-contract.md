# Capture note plan 与候选绑定

只在 Capture 已选择 `note` 路径时读取本文.本文件描述 Capture 自己的准备,绑定,写入意图和 write-plan 责任;不要复制 Markdown 的格式规则或冻结 schema.

## 唯一下游契约

每次调用前完整读取最终 `$markdown-note-format` 的 `references/candidate-response-v1.md`.Capture 的 `src/candidate_contract_v1.py` 是 `capture-note-plan` v1 request/response 的唯一精确 schema,canonical JSON,digest,限制和 path 校验实现.`scripts/validate_note_plan.py` 只是 CLI 入口;`src/validate_note_plan.py` 增加 Capture 本地 write-plan 绑定,不得维护第二份 request/response validator.

若下游 schema 无法表达当前输入,停止并报告接口不兼容;不要私自增加字段或把 Capture 本地状态塞进 transport.

## Capture 在调用前保留的 note plan

- 只使用已选择,已脱敏且带稳定 opaque ID 的完整 source items,metadata 和 evidence 摘要.
- 由 Capture 选择 collection,最小 scope,renderer/profile,目标 operations,时间,顺序,taxonomy 和资源映射.真实 root 不进入下游 request.
- 保留 create,migrate,split,repair 或 review 意图与 allowed transforms.冻结 v1 不传高层 intent;Capture 把它映射为一个或多个明确 operation/target,并在本地继续绑定该意图.
- Split 由 Capture 显式提交多个 operations/targets.每个 v1 operation 仍只对应一个 candidate;Markdown 不得自行拆分或扩大集合.
- 从当前选择生成非空 profile allowlist.通常只传所选 collection profile;不得读取 profile 文件,环境变量或模板补全 allowlist.

## 调用与候选绑定

1. 用 `build_request(..., allowed_format_profiles=allowlist)` 构造 canonical request.只传脱敏内容,evidence,root-relative scope/target,allowed transforms 和逻辑 profile;不传 collection identity,root,create/update,before hash,确认,授权或 write state.
2. 用唯一 Markdown adapter 校验 request,依据 Markdown 的格式 references 生成每个 operation 的完整 candidate,再把 response 与原 request 和相同 allowlist 一起交给 `validate_response`.
3. 拒绝任何 schema,digest,request ID,operation 顺序,item IDs,profile,transform,filename,scope,resource 或最终 target 不匹配.不要脱离原 request 声称 response 已配对.
4. 冻结 v1 response 只返回 candidates 和 request binding.普通 Markdown 的 `format-change-plan` 不进入该 response;Capture 用本地高层意图维护动作说明.

## Capture 本地 write plan

只有候选配对通过后才读取精确 update 目标并决定 `create` 或 `update`.把 `plan_id`,`collection_id` 和每个 operation 的本地意图交给 `construct_write_plan`:

- `create` 的 `before_hash` 必须为 null.
- `update` 的 `before_hash` 必须是当前精确目标的 SHA-256.
- Plan 绑定 request/candidate digest,collection,scope,profile,完整候选,最终 target,operation,allowed transforms 和 before/after hash.
- 对完整 canonical plan 计算 `write_plan_digest`.该值只供执行器校验构造后计划未发生变化,不展示为用户批准凭证.任何绑定值变化都必须重新规划并产生新的 digest.

本地 plan 永不发送给 Markdown.候选或 digest 不代表用户授权或执行成功.用户当轮明确要求记录,写入或批量生成笔记时,可直接执行请求范围内的同批 `create`;无需再次展示完整候选,精确目标,digest 或逐项 operation ID.覆盖,迁移,拆分和修复必须能从用户请求中直接得到动作意图,否则停止并询问.当前 executor 没有真实原子 update CAS 后端时必须返回 `unsupported`;不得降级为普通覆盖.

## I/O 边界

Markdown 不发现,读取,搜索或审计 collection,不读取 profile 或机器时间,不下载或复制资源,不写文件,不持有写入意图或授权.Capture 独立负责隐私,目标选择,访问预检,动作意图绑定,规划,执行,冲突处理和写后验证.Memory 与 no-save 路径不得使用本契约或调用 Markdown.
