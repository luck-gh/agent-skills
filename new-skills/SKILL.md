---
name: new-skills
description: 创建,安装,修改和验收 Skill 的生命周期入口,包括配置物理与使用地址,迁移,分发及查询或升级已安装 Skill.用于变更 Skill 内容,结构或接入方式及其规划;不用于仅阅读,使用或解释现有 Skill,也不用于普通项目初始化.
---

# Skill lifecycle

将本 Skill 作为 Skill 内容与结构变更及生命周期验收的入口.领域 Skill 可以补充专业规则,但不得替代这里的结构,metadata,内容风格和验收边界.

## Establish the contract

1. 从用户输入,现有目标和仓库规则确定目标平台契约.只采用契约明确声明的 initializer,入口格式,metadata adapter,validator 和 discovery 机制.
2. 先区分规划,只读审查与实施.规划,预览或只读任务不写 settings,不运行 initializer,不 fetch,不写更新状态,也不创建 discovery entry.用户提供路径可用于当轮任务,不等于要求保存默认配置.
3. 用具体用例确认触发,输入,成果,文件所有权与验收范围.改进已有 Skill 时先定位真实使用问题或明确的新需求,固定当前工作区基线和成功标准,不按评分或篇幅寻找修改理由.检查现有能力,调用方和职责重叠后再决定保留或修改;合并或删除整个 Skill,改名或显著改变职责需要用户确认,不为减少入口而强行重构.
4. 新名称使用小写 hyphen-case.先根据显式路径,已有 Skill 实体及用户指定的归属确定项目级或系统级.显式 physical dir 或 physical parent 始终优先;项目级按下节确定路径,不读取全局路径设置.已有系统级 Skill 默认原地编辑,不因当前工作目录是项目而改为项目级.只有系统级任务缺少必需路径,或用户明确要求配置系统级默认值时,读取 [skill-local settings](references/local-settings.md);不为已确定的目标强制补建设置.归属或项目根确实不明时只询问缺失信息,不猜测或搬迁.
5. 系统级安装需按 [安装与自动检查接入](references/update-installation.md) 建立安装基线和宿主触发入口.收到宿主自动检查结果,用户明确查询更新/升级,或要求暂缓/恢复升级询问时,读取 [仓库更新契约](references/repository-updates.md).已接入安装在使用时按 24 小时成功缓存自动检查,发现更新先询问;用户说近期不更新则只检查并报告.源码维护,项目级创建/修改和设计参考研究不触发安装更新,显式只读,禁止联网或禁止写状态时跳过.

Settings 值只提供路径候选,不构成创建,移动,删除,复制,链接或其他副作用授权.

## Project scope

- 用户要求项目自有 Skill 时,新建实体默认位于已确定项目根下的 `skills/<name>`,显式项目内路径优先.编辑已有项目 Skill 时使用其当前实体目录,保留用户改动,不重新初始化或迁移.不读取或写入本 Skill 的全局 `settings.json`,不从其中取得 physical root 或 usage root,也不为作用域增加配置字段.
- 项目创建,编辑和调试不创建或更新用户级 `.agents`,`.codex` 等发现链接,不因缺少宿主自动发现而进入系统安装流程.使用显式 `SKILL.md` 路径加载本轮规则和执行验证;这不保证宿主自动发现该目录,实际发现能力须单独报告.
- 命名,frontmatter,README,渐进加载,资源闭包,内容风格和验证沿用本 Skill 的共同标准,项目级不降低门槛.项目资料可作为用户明确提供或项目契约声明的输入,注明读取范围与缺失时的处理;项目事实保留在项目真源,不复制进 Skill,不通过硬编码绝对路径,父目录导入或隐含读取制造跨目录运行时依赖.可复用方法和自有脚本/资源仍闭包在 Skill 内.
- 先在项目中调试并报告验证与未验证项.只有用户确认项目及 Skill 调试成功,并另行明确授权提升到系统级后,才进入迁移/安装流程,核对目标,冲突及唯一物理真源.测试通过或用户仅确认调试成功均不构成提升授权;不预建系统目录,链接或第二份副本.

## Modify the Skill

1. Create 时只在目标平台要求时运行其 initializer.Update 和 repair 直接编辑.Migrate 或 move 保持单一 physical source of truth,先明确目标,冲突,授权和可恢复路径.改名已安装 Skill 时,先读取 [发现入口交接](references/junction-safety.md),核对旧实体,旧入口和本机配置;实施包含新名称接入与旧入口收口,不能只改仓库目录或版本说明.用户明确仅改源码或禁止安装维护时保留该限制,把未完成接入单列报告.
2. 遵循目标平台的入口与 frontmatter 规则.`description` 保留核心能力,高辨识触发意图与防止近邻误触的必要排除,不穷举同义词或实现细节;首次命中所需信息不得只放正文或 references.每次修改 Skill 后,若 description 发生变化,必须整体重新梳理表达,不能只在原描述末尾追加信息.它可能进入模型的可用 Skill 清单并占用上下文,应在保持触发准确性和必要边界的前提下尽量精炼,不设置机械字数目标.
3. `SKILL.md` 正文保留共同约束,不可延迟的安全边界,明确的分支读取条件和完成标准.每条条件路由在正文直接链接一级 `references/`;条件流程,平台差异,schema,长步骤和示例放入对应引用,但保留该分支必需的步骤,检查点,失败处理和验证.信息只保留一个权威位置,不将路由藏入引用,不预设目录或文件数量.按项目分发契约维护面向使用者的 `README.md`,介绍场景,安装发现与调用,输入输出,配置依赖,实际示例及验证边界,按需要说明流程,常见问题和来源许可.运行规则仍由入口与必要引用完整表达,Agent 不必加载 README 才能正确执行;两份文档不整篇复制.不新增无用途的 CHANGELOG 或过程记录.
4. 指导强度按风险决定.安全边界和验收标准对所有模型一致;开放性任务说明目标,约束与质量判断,允许自主选择实现和工具.常规任务给推荐路径而非唯一顺序;高风险,易出错或顺序敏感操作才规定严格步骤.不为减少 token 删除必要指导,测试或 review.
5. 每个 Skill 默认无状态且可独立分发.所有运行时实现和资源必须位于自身 physical skill dir;不得引用兄弟 Skill,`../_dev` 或仓库级运行时代码.平台 adapter 和 discovery entry 不得成为第二份内容源.
6. 只在确定性,重复调用或难以可靠手写时保留 Python.检查调用方后删除占位脚本,一次性迁移脚本和等价转发入口.在目标 `SKILL.md` 中用直接 Markdown 链接声明每个公开 `scripts/*.py`;fenced code,inline code 和命令示例只表达用法,不构成声明.`src/` 内部实现不要求逐文件声明.
7. 每个 Python 模块用中文模块注释说明存在理由,应用场景和用法.代码检查直接输入契约,必要安全边界和可观察输出,不为未出现的竞态或平台分支建立框架.
8. 仅在目标平台声明 metadata adapter 时创建或更新 metadata,保留未要求改变的调用策略及其他已有字段.核对 metadata 与最终 `SKILL.md` 的名称,触发和能力一致.
9. 若新增第三方依赖,记录 source URL,exact version,license,integrity hash,平台和运行时边界;未新增时报告"无".独立分发表示 Skill 文件闭包完整,不表示第三方包被复制进 Skill;隔离验收使用已声明依赖可用的运行时.
10. 吸收参考项目时,把有用的方法,步骤,条件和失败处理整理为本地可执行内容.设计参考的仓库链接,固定版本与比较过程只放 Skill 之外不公开分发的维护资料,可按项目契约纳入私有版本管理,不在公开入口,README 或模型正文中推荐回读.只有用户明确要求才重新研究参考项目;必要版权和许可仍随包保留,实际运行依赖的来源按上一条管理.

## Content style

对 `SKILL.md`,存在的顶层 `README.md`,`references/**/*.md` 和 `agents/**/*.{yaml,yml}` 中由当前仓库维护的中文正文执行 [scripts/check_content_style.py](scripts/check_content_style.py).将 `，。；：！？（）【】、` 改为对应英文半角标点;排除 fenced/inline code,命令,路径,URL,regex,语言语法和必须原样保留的 blockquote.工具只报告,不得自动改写.

## Python resources

| Public entry | Implementation | Reason and use |
| --- | --- | --- |
| [scripts/check_content_style.py](scripts/check_content_style.py) | 同一文件 | 检查明确传入的 Skill 中文正文标点. |
| [scripts/ensure_skill_entry.py](scripts/ensure_skill_entry.py) | 同一文件 | 检查或创建目标平台声明的单一 discovery entry. |
| [scripts/manage_updates.py](scripts/manage_updates.py) | 同一文件 | 检查 Git 真源或公共安装,授权后升级,并收尾已完成的公共改名安装记录. |
| [scripts/validate_skill.py](scripts/validate_skill.py) | 同一文件 | 只读检查通用 Skill 分发契约,不执行领域行为. |

## Optional discovery entry

当前任务明确涉及系统级安装发现,已安装 Skill 改名,或升级使名称/实体路径变化时,读取 [junction-safety.md](references/junction-safety.md).项目内创建,编辑和调试按 Project scope 执行,不进入本分支.普通缺失入口先 `inspect`,授权内且 entry 缺失时 `ensure --authorized`;同一名称的有效链接不重建.改名必须按引用完成先验证新入口,再清理准确旧链接的交接.两根目录相同时直接使用实体,不创建指向自身的链接.用户已授权升级或改名现有安装时,与该安装对应的入口维护一并执行,不逐项重复索要授权;只检查,只改源码或其他显式限制优先,宿主审批仍须满足.

## Validate and report

1. 修改前确定本轮验收用例;修改前需要行为对照,验证 Skill 或修改验收流程时读取 [validation-contract.md](references/validation-contract.md),按其静态检查,相关测试和风险选择行为验证.改进按同一契约完成问题定位,有界修改,前后对照,保留或恢复及停止判断,不另起进化系统.规划仅交付方案与未验证项,不执行实施门禁.
2. 实施完成后运行通用 validator,目标平台 validator 与内容风格检查.对官方 OpenAI Skill 使用 `$skill-creator` 的 `quick_validate.py`;领域逻辑变更运行相关既有测试并补必要回归.不无条件叠加无关测试.
3. 完成标准:保留或明确获准调整的能力成立,触发与分支可辨识,必要安全指导未丢失,范围与授权未越界,适用验证有结果,冲突和未验证项如实列出.已安装 Skill 改名还须核对配置保留,新入口实际 target 与可读内容,旧入口及安装记录收口;任一步未完成就区分“内容已更新”和“安装未完成”,不能用 `updated` 或 `no_changes` 代替整体验收.不以文档变短或静态通过代替行为正确.
4. 报告授权范围,文件所有权,content,metadata,settings,discovery,validator,测试,第三方依赖及未解决冲突.安装验收包含基线,实际生效的自动检查入口与新会话验证;未验证时不能宣称自动检查已启用.自动检查仅按 notification 报告新结果,缓存命中不重复询问.只有相关证据充分时才宣称完成.
