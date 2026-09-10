# markdown-note-format

把已经提供的笔记内容与明确变更意图整理成可审查的 Markdown 候选和变更计划.它处理命名,结构,frontmatter,分类,图片路径与公式图表规范,并把哪些内容可改,哪些必须保留说清楚.

适合创建,迁移,拆分,修复或审查笔记格式.它不判断知识是否值得保存,不选择笔记库或源笔记,也不读写真实文件.如果你要从聊天提取经验并保存,应由知识存储流程先完成选择与授权.

## 安装与调用

从[公共仓库](https://github.com/luck-gh/agent-skills)取得完整的 `markdown-note-format/` 目录,放入 Codex 的 `$HOME/.agents/skills` 或 Windows `%USERPROFILE%\.agents\skills`;独立实体目录也可通过精确目录链接接入,不覆盖已有目录.本地未发布版本直接使用工作区完整目录,公共下载只取已发布内容.其他 Agent 按自身发现机制安装.

输入 `$markdown-note-format` 显式调用;未刷新时重启 Agent.发现路径依据 [Codex 文档](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).使用无需 settings,Python,网络或文件权限.

## 最小示例

```text
使用 $markdown-note-format,只在回复中给出创建候选,不要写文件.
item_id: note-1; operation: create; profile: plain-v1.
我已选定逻辑 scope 为 examples,目标相对路径为 examples/idempotency.md.
无 frontmatter、日期、taxonomy 或资源引用,不新增这些字段.
允许整理标题和列表,不增加事实,不改正文含义.
标题: 幂等键
正文: 重复请求应使用同一键.服务端返回已有结果.本次验证只覆盖顺序重试,并发场景尚未验证.
```

进阶用例是显式拆分,由调用者提供全部目标而非让格式工具自行决定:

```text
使用 $markdown-note-format,按我确定的拆分生成格式候选和变更计划.
profile: plain-v1; operation: split; 逻辑 scope: examples.
source item_id: src-1; 无 metadata 或资源; 完整正文为以下两段:
同一请求的重试沿用幂等键.
并发创建未验证,需要另外设计实验.
第一段归入 examples/request-dedup.md,标题为请求去重.
第二段归入 examples/concurrency-limits.md,标题为并发边界.
允许拆分结构和新增标题,不改正文.不要增加第三篇或选择真实落盘目录.
```

## 输入,输出与流程

提供完整文本,元数据,item_id,操作意图,调用方已选定的逻辑 collection/scope,允许变更范围和所选 profile.涉及图片,公式或图表时,补上资源映射与保留要求.不要只给一个未读取的文件路径并期望它自行寻找正文.

流程是核对输入与身份,应用[基本格式规则](references/format-rules.md),只在需要时加载扩展语法,然后返回 `format-candidate-set` 与 `format-change-plan`.与 Capture 集成时采用其显式传入的 v1 计划与 profile allowlist,不会替调用者扩展操作集合.完整输出合同见 [SKILL.md](SKILL.md) 的按需引用.

## 常见问题与边界

- 为什么没有保存文件?本 Skill 交付候选,持久化由获得授权且具备对应能力的调用者完成.
- 图片链接能打开吗?它可以按已提供映射检查写法,不能证明目标资源存在或渲染成功.
- 会自动搜索来源或补足内容吗?不会.信息不完整时保留未知,不通过 shell,网络或其他 Skill 补读真实笔记.
- 格式规范有冲突怎么办?以明确 profile 和允许变更范围处理,保持语义与引用原文,不能为统一格式修改事实.

已有静态契约与格式/知识流程的有限回放证据.本次文档检查不代表所有编辑器渲染已验证,也不证明外部存储写入成功.

本 README 面向使用者,Agent 依靠入口与必要引用执行.本目录按 [Apache License 2.0](https://github.com/luck-gh/agent-skills/blob/main/LICENSE) 分发;引用与用户原文保留原有权利和格式要求.
