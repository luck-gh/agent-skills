# capture-personal-knowledge

从已获授权的项目实施,排障或聊天材料中判断什么值得长期保留,再选择笔记,真实记忆后端或不保存.它负责知识价值,脱敏,存储范围和写入状态,避免把一次性过程或未经证实的建议存成经验.

适合显式要求吸收,记住,记录或复盘经验的任务.只整理已确定 Markdown 的格式请用格式工具;只维护项目本地 EXPERIENCE 文档不属于本 Skill.

## 安装与调用

从[公共仓库](https://github.com/luck-gh/agent-skills)取得完整的 `capture-personal-knowledge/` 目录.当前工作区的未发布内容可直接接入;公共下载只含已发布版本.

Codex 从 `$HOME/.agents/skills/capture-personal-knowledge` 发现入口,Windows 对应 `%USERPROFILE%\.agents\skills\capture-personal-knowledge`.可直接安装实体目录,也可用目录链接指向唯一实体目录;已有目标先核对,不要覆盖或重复复制.其他 Agent 使用其实际发现目录.调用 `$capture-personal-knowledge`,未刷新时重启 Agent.参见 [Codex 官方说明](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).

## 最小示例

以下用例无需笔记库或记忆工具:

```text
使用 $capture-personal-knowledge,复盘这次排障:请求超时后客户端重试,服务端重复创建订单;给请求加幂等键后,相同键重复提交只返回已有结果.请区分已证实经验和仍需验证的边界,本次不保存.
```

有配置后的笔记用例:

```text
使用 $capture-personal-knowledge,把上面已证实的幂等处理经验保存为一篇新笔记,使用我已配置的 engineering collection.去掉项目名称与用户资料,先核对已有相关笔记,不覆盖已有文件.输出实际保存位置和仍未验证的边界.
```

需要记忆时可明确请求记住一条长期偏好.只有宿主提供真实记忆工具且本次写入获授权时才会保存;没有工具时返回建议 payload 和 unsupported,不会把聊天承诺当成写入成功.

## 输入与配置

输入是本轮材料,保存意图,允许使用的资料范围,以及需要笔记时的 collection.不搜索其他聊天或任意文件来拼凑来源.

笔记分支接收显式完整 `collections` object,否则读取实体目录同级 `settings.json` 的唯一字段 `collections`.每项包含 id,已存在的绝对物理 root,相对目录 include/exclude 和 format_profile.从[安全设置示例](settings.example.json)理解结构,替换占位值后按[设置说明](references/local-settings.md)验证;配置不等于读写授权.不用笔记分支时不需要这些设置.

笔记格式候选由宿主可用的 `$markdown-note-format` 生成,这是明确的协作能力,不是读取兄弟安装目录.宿主缺少它时应报告缺项,不能声称已完成格式交接.本 Skill 的 Python 校验工具使用标准库;业务写入还取决于宿主文件工具的真实原子操作能力.

## 工作流程与输出

先选择 note,memory 或 no-save,再做证据和隐私筛选.笔记分支在允许的 collection 范围内定位目标,生成绑定明确内容与操作的候选,验证后按授权保存并回读.输出可能是复盘结论,笔记与状态,或实际记忆后端返回的结果.详见[候选绑定合同](references/capture-plan-contract.md)和 [SKILL.md](SKILL.md).

- 新建要求原子 no-clobber,目标存在时停止,不覆盖.
- 更新已有笔记需要真实的原子 before-hash compare-and-swap.当前工具不能提供时返回 unsupported,即使普通文件写入可用也不能假装安全更新.
- 取消保存后停止新增资料库与记忆 I/O,只报告已知实际状态.跨文件动作失败不能只报整体成功.

## 验证与许可

已有 collection,候选绑定及写入边界的回归用例,本次核对文档与当前执行入口一致.模拟工具与静态通过不证明任意宿主后端具备原子更新,也未验证所有真实笔记库和记忆服务.

README 是使用说明,执行规则仍在入口与必要引用.本目录按 [Apache License 2.0](https://github.com/luck-gh/agent-skills/blob/main/LICENSE) 分发;用户材料保持其原有权利与授权范围,不随 Skill 分发.
