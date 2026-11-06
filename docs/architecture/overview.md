# orchestrate-tasks 判断与交付流程

默认由当前任务拆给内部 Agent,完成一个有界交付批次;委派新负责人、拆成多个 Codex 任务和 GOAL 迭代仅在用户明确选择时启用.

[打开四页可编辑流程图](overview.drawio).本文与图使用相同节点标识;规则真源仍是 [orchestrate-tasks/SKILL.md](../../orchestrate-tasks/SKILL.md).

## 怎么读

先看第 1 页选择入口,通常只需再看第 2 页.明确选择侧栏任务时看第 3 页,明确选择迭代时看第 4 页.委派决定谁负责,拆分决定如何组织工作,迭代决定是否多轮推进,可按明确授权组合.

| 你的输入 | 判断结果 |
| --- | --- |
| “先讨论一下,不要派发” | 只讨论,不启动执行编排 |
| “使用 $orchestrate-tasks 完成这个工作” | 当前任务负责,默认内部 Agent 拆分,一批交付 |
| “继续” | 沿用已有选择,不重置为默认 |
| “在本任务执行,不要拆分” | 当前任务独立完成,两种拆分承载都关闭 |
| “委派给一个新 Codex 任务” | 新负责人 E 默认内部拆分,原任务只做总控验收 |
| “委派,但不要拆分” | E 独立完成 |
| “拆成两个 Codex 任务” | 每个任务默认再拆给内部 Agent,各自收口后交当前负责人整合 |
| “拆成两个 Codex 任务,各任务不再拆分” | 两个任务各自独立完成,关闭的是内部拆分,不撤销已选择的两个任务 |
| “委派 E,再由 E 拆成两个 Codex 任务” | 仅按明确数量和层级授权创建一层;A/B → E → 原任务 |
| “按 GOAL 迭代” | 固定契约后有界接力;每轮默认内部 Agent 拆分 |
| “按 GOAL 迭代,每轮不要拆分” | 每轮负责人独立完成,不改变唯一后继和停止门禁 |
| “允许按需创建任务” | 只有权限含义,本身不改变已选承载或默认内部拆分 |

所有示例均需结合上下文中已明确的目标和范围.自然语言示例不是独立的权限凭据,任务创建、消息、Git、设备等仍按宿主规则核验.必要缺口补齐后才执行受影响动作.

拆分选择要绑定到具体负责人及范围.例如“拆成两个 Codex 任务,各任务不再拆分”保留外层两个任务,仅关闭它们的内部拆分;“本轮不拆分”与“整批不拆分”按各自范围生效,已有选择不因后续说“继续”而重置.

内部 Agent 承担局部调查和调试,向负责人返回紧凑成果与证据,有助于减少负责人上下文中积累的过程细节.是否减少总 token 取决于任务包、历史继承与协调成本,这里不宣称已实测节省.

## 01 输入与分支选择

先判断是否执行,沿用已有选择;未选择时由当前任务负责内部拆分.

绿色为默认路径.蓝色为显式选择.箭头是条件路由,不是时间刻度.委派、承载和迭代可组合,不是互斥模式.

```mermaid
flowchart TD
    mod_discuss["仅讨论 / 解释 / 不派发"]
    mod_no_dispatch["不派发执行任务"]
    mod_execute["明确调用 Skill 执行"]
    mod_continue["已有选择后说:继续"]
    mod_choices["复用已有选择<br/>默认只补尚未选择的项"]
    mod_current["默认:当前任务负责<br/>内部 Agent 拆分 · 一批交付"]
    mod_delegate["显式:委派新负责人 E<br/>E 默认内部拆分"]
    mod_side_split["显式:多个 Codex 任务<br/>各任务进入内部拆分选择"]
    mod_iteration["显式:迭代 / GOAL 接力<br/>每轮进入内部拆分选择"]
    mod_limits["执行前核验实际权限与能力<br/>数量 · 层级 · 单写者 · 输入就绪"]
    mod_discuss -->|"讨论到此"| mod_no_dispatch
    mod_execute -->|"明确目标后"| mod_choices
    mod_continue -->|"沿用有效上下文"| mod_choices
    mod_choices -->|"未明确另选"| mod_current
    mod_choices -->|"明确委派"| mod_delegate
    mod_choices -->|"明确多任务"| mod_side_split
    mod_choices -->|"明确迭代"| mod_iteration
    mod_current -->|"进入执行"| mod_limits
    mod_delegate -->|"创建前"| mod_limits
    mod_side_split -->|"派发前"| mod_limits
    mod_iteration -->|"固定契约"| mod_limits
    classDef default fill:#E5F4EC,stroke:#278353,color:#173D29
    class mod_current default
    classDef explicit fill:#E8F1FF,stroke:#3B70AD,color:#17324D
    class mod_delegate,mod_side_split,mod_iteration explicit
    classDef gate fill:#FFF3D6,stroke:#A77C25,color:#604715
    class mod_limits gate
    classDef stop fill:#FDEBE7,stroke:#B65C49,color:#70352C
```

实线表示条件和交付方向;虚线表示满足条件后的返修、再检查或后继接管,不表示无限循环.

<a id="mod_discuss"></a>

**仅讨论 / 解释 / 不派发**: 此输入到讨论为止.本次阅读或绘制 Skill 逻辑也不等于执行业务编排.

<a id="mod_no_dispatch"></a>

**不派发执行任务**: 未要求执行编排时,不自动创建内部 Agent 或侧栏任务.

<a id="mod_execute"></a>

**明确调用 Skill 执行**: 例如:使用 $orchestrate-tasks 完成已确认的工作.先明确目标、范围、授权和验收.

<a id="mod_continue"></a>

**已有选择后说:继续**: 保留此前的负责人、拆分选择、承载与推进方式.用户明确变更的项目才更新.

<a id="mod_choices"></a>

**复用已有选择 / 默认只补尚未选择的项**: 单纯允许按需创建任务是授权,不等于选择侧栏承载.冲突或必要缺口先澄清,不重新询问已有授权.

<a id="mod_current"></a>

**默认:当前任务负责 / 内部 Agent 拆分 · 一批交付**: 当前任务是执行负责人,可以直接调查、实施和整合.详见第 2 页.

<a id="mod_delegate"></a>

**显式:委派新负责人 E / E 默认内部拆分**: 原任务成为纯总控.用户说委派后不拆分,E 独立完成;明确授权 E 拆成侧栏任务时才走一层下级聊天.

<a id="mod_side_split"></a>

**显式:多个 Codex 任务 / 各任务进入内部拆分选择**: 按大型独立成果、就绪输入与明确所有权拆分.各负责人默认进入内部 Agent 拆分;用户明确该任务不拆分时,由该任务独立完成.当前负责人统一整合各任务成果,不另设无用收集者.

<a id="mod_iteration"></a>

**显式:迭代 / GOAL 接力 / 每轮进入内部拆分选择**: 默认每轮新建 Codex 任务,每轮都沿用固定契约中的拆分选择:默认内部 Agent,或明确不拆分.可明确指定当前任务为首轮,但当前轮授权不推出后继权限.详见第 4 页.

<a id="mod_limits"></a>

**执行前核验实际权限与能力 / 数量 · 层级 · 单写者 · 输入就绪**: 适用于所有执行分支.侧栏创建、消息、Git 和设备各有授权边界;不擅建 worktree.缺工具或权限说明限制,不静默改承载.

证据:

- `orchestrate-tasks/SKILL.md:12-28`: 执行触发、默认值、选择沿用以及显式分支.
- `orchestrate-tasks/SKILL.md:30-46`: 角色、单写者、权限和按需引用.

## 02 默认执行:内部 Agent 与一次交付

负责人一次给出完整工作包,Agent 自主闭环;负责人收齐后整合、验证、文档收口.

本页是所有执行负责人的共同拆分选择:当前任务、受委派任务、多个 Codex 任务中的每个负责人及每轮迭代负责人都适用.普通子 Agent 是叶子,不递归套用这项默认.必要修复属于同一批,不自动续轮.

```mermaid
flowchart TD
    mod_owner["执行负责人<br/>当前任务 / 新负责人 / 轮次负责人"]
    mod_split_check["明确不拆分?<br/>否则是否存在合理拆分收益?"]
    mod_solo["负责人独立完成"]
    mod_package["按独立成果派发完整任务包<br/>先满足输入、依赖和所有权"]
    mod_agents["内部 Agent 自主闭环<br/>调查 → 实施 → 自查与验证"]
    mod_wait["负责人处理独立工作<br/>等待必需结果时用事件等待"]
    mod_integrate["收齐并审查必需成果<br/>集中返修 / 整合 / 最终验证"]
    mod_document["完成必要文档收口<br/>共享文档指定唯一写者"]
    mod_delivery["统一交付这一批<br/>直接执行给用户;委派后回所属接收方"]
    mod_block["真实阻塞 / 风险 / 用户暂停<br/>说明状态并处理必要协调"]
    mod_owner -->|"确认拆分选择"| mod_split_check
    mod_split_check -->|"不拆分 / 无合理拆分点"| mod_solo
    mod_split_check -->|"默认:有收益且可派发"| mod_package
    mod_package -->|"完整工作包"| mod_agents
    mod_package -->|"负责人并行独立工作"| mod_wait
    mod_agents -->|"交付范围内成果"| mod_integrate
    mod_wait -->|"必需结果齐备"| mod_integrate
    mod_solo -->|"完成实现和自查"| mod_integrate
    mod_integrate -.->|"集中返修(适用时)"| mod_agents
    mod_integrate -->|"最终候选验证通过"| mod_document
    mod_document -->|"交付前收口"| mod_delivery
    mod_integrate -->|"无法范围内解决"| mod_block
    mod_block -->|"按部分/阻塞等实际状态交付"| mod_delivery
    classDef default fill:#E5F4EC,stroke:#278353,color:#173D29
    class mod_package,mod_agents,mod_integrate,mod_document,mod_delivery default
    classDef explicit fill:#E8F1FF,stroke:#3B70AD,color:#17324D
    classDef gate fill:#FFF3D6,stroke:#A77C25,color:#604715
    class mod_split_check gate
    classDef stop fill:#FDEBE7,stroke:#B65C49,color:#70352C
    class mod_block stop
```

实线表示条件和交付方向;虚线表示满足条件后的返修、再检查或后继接管,不表示无限循环.

<a id="mod_owner"></a>

**执行负责人 / 当前任务 / 新负责人 / 轮次负责人**: 负责人承担调查、实施、协调、最终验证、整合和文档收口,不会因名称叫主任务而放弃执行.

<a id="mod_split_check"></a>

**明确不拆分? / 否则是否存在合理拆分收益?**: 默认实施有收益的拆分,不能因为自己也能做就跳过.很小、强串行或无法划清写权时说明具体原因后直接完成.

<a id="mod_solo"></a>

**负责人独立完成**: 明确不拆分关闭内部与侧栏助手.没有合理拆分点时也可直接完成,不能为了凑数量创建工作.

<a id="mod_package"></a>

**按独立成果派发完整任务包 / 先满足输入、依赖和所有权**: 一次给出目标、路径、范围、非目标、依赖、写权、授权、验收与停止条件.依赖输入未就绪时等待,不靠频繁消息补齐.

<a id="mod_agents"></a>

**内部 Agent 自主闭环 / 调查 → 实施 → 自查与验证**: 子 Agent 只向所属负责人交付.不创建侧栏任务或套用默认递归拆分;有界内部递归需要另有明确范围.

<a id="mod_wait"></a>

**负责人处理独立工作 / 等待必需结果时用事件等待**: 不持续查看过程或催促.有必需内部结果在途不能提前结束回合,也不能假设结束后会被内部 Agent 唤醒.

<a id="mod_integrate"></a>

**收齐并审查必需成果 / 集中返修 / 整合 / 最终验证**: 先确认所有必需成果就绪、版本明确和写权归还.验收问题集中交原所有者修复,不把内部协调交回纯总控.

<a id="mod_document"></a>

**完成必要文档收口 / 共享文档指定唯一写者**: 新功能、Bug 修复、性能和测试改进都检查必要记录.复用 bootstrap 文档契约及现有真源;不要求每次更新所有文档.只读任务列出建议,不得越权写入.

<a id="mod_delivery"></a>

**统一交付这一批 / 直接执行给用户;委派后回所属接收方**: 交付状态、结论、修改范围、验证证据、必要文档以及未完成和在途项.完成一个有界批次后结束,不自动接力.

<a id="mod_block"></a>

**真实阻塞 / 风险 / 用户暂停 / 说明状态并处理必要协调**: 只有无法自主解决的阻塞或授权缺口、有证据的冲突/风险及用户变更/暂停允许中途协调.失败或未知不能冒充完成.

证据:

- `orchestrate-tasks/references/subagents.md:3-21`: 默认内部拆分、完整工作包、叶子职责、事件等待与结果归属.
- `orchestrate-tasks/SKILL.md:52-61`: 交付前整合、回合结束与协调条件.
- `orchestrate-tasks/SKILL.md:63-81`: 共同文档职责及有界恢复规则.

## 03 显式侧栏任务:回传与整合

先核验交付路径,各任务向所属负责人回传;必要结果就绪后才整合或汇总.

返回路径:直接拆分 A/B → 当前负责人;委派 E → 原任务;委派再拆分 A/B → E → 原任务.不越级回传.

```mermaid
flowchart TD
    mod_sidebar["已明确选择侧栏任务<br/>固定负责人、批次和必要成果"]
    mod_channel["核验交付方式<br/>准确 ID · 能力 · 人类授权"]
    mod_callback["回传已核验<br/>无本地在途工作可先结束回合"]
    mod_wait_choice["用户明确等待 / 仅交接<br/>遵守该选择"]
    mod_path_missing["能力或授权不足<br/>报告具体限制,补必要缺口"]
    mod_result["执行方完成后交付紧凑结果<br/>子结果先由所属负责人整合"]
    mod_ready["按批次与任务标识去重<br/>全部必要成果是否真的就绪?"]
    mod_partial["部分结果:记录并等余项<br/>重复/迟到:不重复计数或派发"]
    mod_merge_choice["需要合并、联调或组合验证?"]
    mod_merge["执行负责人整合<br/>新整合任务仅在明确授权内创建"]
    mod_accept["汇总并最终验收<br/>独立结论可直接汇总"]
    mod_side_choice["每个 Codex 执行负责人<br/>沿用自己的内部拆分选择"]
    mod_side_agents["默认:拆给内部 Agent<br/>子结果只交所属任务负责人"]
    mod_side_solo["明确不拆分<br/>该 Codex 任务独立完成"]
    mod_sidebar -->|"派发前核验"| mod_channel
    mod_channel -->|"使用回传且条件齐备"| mod_callback
    mod_channel -->|"已选等待 / 仅交接"| mod_wait_choice
    mod_channel -->|"必要条件缺失"| mod_path_missing
    mod_callback -->|"执行任务启动后"| mod_side_choice
    mod_wait_choice -->|"执行任务启动后"| mod_side_choice
    mod_result -->|"接收真实交付"| mod_ready
    mod_ready -->|"未齐 / 重复 / 未就绪"| mod_partial
    mod_partial -.->|"新有效成果到达"| mod_ready
    mod_ready -->|"必要成果齐备且可用"| mod_merge_choice
    mod_merge_choice -->|"需要组合验证"| mod_merge
    mod_merge_choice -->|"独立结论"| mod_accept
    mod_merge -->|"统一交付"| mod_accept
    mod_side_choice -->|"默认:有实际拆分收益"| mod_side_agents
    mod_side_choice -->|"明确不拆分 / 无合理拆分点"| mod_side_solo
    mod_side_agents -->|"收齐、验证及文档收口"| mod_result
    mod_side_solo -->|"自查、验证及文档收口"| mod_result
    classDef default fill:#E5F4EC,stroke:#278353,color:#173D29
    class mod_side_agents,mod_side_solo default
    classDef explicit fill:#E8F1FF,stroke:#3B70AD,color:#17324D
    class mod_sidebar explicit
    classDef gate fill:#FFF3D6,stroke:#A77C25,color:#604715
    class mod_channel,mod_ready,mod_merge_choice,mod_side_choice gate
    classDef stop fill:#FDEBE7,stroke:#B65C49,color:#70352C
    class mod_path_missing stop
```

实线表示条件和交付方向;虚线表示满足条件后的返修、再检查或后继接管,不表示无限循环.

<a id="mod_sidebar"></a>

**已明确选择侧栏任务 / 固定负责人、批次和必要成果**: 单委派、多任务拆分和委派后一层拆分,均按用户明确选择与数量/层级授权创建.不强制增加收集聊天.

<a id="mod_channel"></a>

**核验交付方式 / 准确 ID · 能力 · 人类授权**: 默认回传需验证发送并开启接收任务新回合的能力及每条真实消息路径.创建任务权限不等于消息权限.

<a id="mod_callback"></a>

**回传已核验 / 无本地在途工作可先结束回合**: 派发后完成必要初始核验.仅剩侧栏结果时可结束回合,但整合责任保留;持有内部 Agent 未完成结果时不能提前结束.

<a id="mod_wait_choice"></a>

**用户明确等待 / 仅交接 / 遵守该选择**: 等待用事件等待;仅交接不承诺通知原任务.不为未使用的回调强求消息授权.

<a id="mod_path_missing"></a>

**能力或授权不足 / 报告具体限制,补必要缺口**: 不得虚构后台唤醒,不得静默高频轮询或新增服务.不擅自切换交付方式.

<a id="mod_side_choice"></a>

**每个 Codex 执行负责人 / 沿用自己的内部拆分选择**: 多任务拆分后,每个任务仍是其分配成果的负责人,默认内部拆分.用户明确某任务或本批各任务不再拆分时,在指定范围内关闭.

<a id="mod_side_agents"></a>

**默认:拆给内部 Agent / 子结果只交所属任务负责人**: A 的 Agent 只向 A 交付,B 同理.各任务收齐并整合、验证、文档收口后,再向上级交付紧凑结果.

<a id="mod_side_solo"></a>

**明确不拆分 / 该 Codex 任务独立完成**: 该任务自己完成调查、实施、自查、验证和必要文档.没有合理拆分点时说明原因后也可直接完成.

<a id="mod_result"></a>

**执行方完成后交付紧凑结果 / 子结果先由所属负责人整合**: 交付身份、状态、结论、范围、验证依据、文档、未完成与在途项.回调只尽力发送一次;发送未知不得盲目重发.

<a id="mod_ready"></a>

**按批次与任务标识去重 / 全部必要成果是否真的就绪?**: 收到不等于可用.版本与依据要明确,相关写者结束;失败、部分、取消或未知不能充当就绪依赖.

<a id="mod_partial"></a>

**部分结果:记录并等余项 / 重复/迟到:不重复计数或派发**: 不因部分回传催促正常执行者.重复消息不触发重复整合.缺失字段仅在反向消息授权内核实一次.

<a id="mod_merge_choice"></a>

**需要合并、联调或组合验证?**: 当前执行负责人默认自行整合.纯总控不代改项目,返交原负责人;确需新整合任务必须已有相应明确授权.

<a id="mod_merge"></a>

**执行负责人整合 / 新整合任务仅在明确授权内创建**: 先确认输入、版本和写者就绪,处理集成问题、验证最终候选、自查并收口共享文档.

<a id="mod_accept"></a>

**汇总并最终验收 / 独立结论可直接汇总**: 创建成功、回合结束或单项测试通过不能替代完整成果验收.验收问题集中交对应负责人.

证据:

- `orchestrate-tasks/references/new-task-callbacks.md:3-23`: 回传归属、能力授权、一次发送及所有权释放.
- `orchestrate-tasks/references/new-task-callbacks.md:36-51`: 部分结果、真正就绪与重复/迟到处理.
- `orchestrate-tasks/references/mixed-carriers.md:3-11`: 一层混合承载以及 A/B、E 和原任务之间的交付路径.
- `orchestrate-tasks/references/new-tasks.md:23-30`: 依赖写者结束、回传和事件等待.
- `orchestrate-tasks/references/new-tasks.md:52-56`: 整合责任与新整合任务的授权条件.

## 04 显式迭代:GOAL 有界串行接力

每轮从项目资料接续;只有验收提交完成、写者结束且边界允许,才创建唯一后继.

每轮都进入拆分选择:默认拆给内部 Agent,明确不拆分则由本轮任务独立完成.选择按本轮或整批约定沿用,不逐轮重新询问.轮次之间仍串行,普通一批交付或已有 GOAL 文件都不会自动触发迭代.

```mermaid
flowchart TD
    mod_goal_contract["明确迭代并固定契约<br/>目标 · 验收 · 上限 · 授权 · 交付方式"]
    mod_round["本轮负责人接管<br/>读取 GOAL、规则与当前证据"]
    mod_slice["自主完成可验收切片<br/>收齐结果、验证、文档收口"]
    mod_stop_check["达标 / 无有价值下一项 / 必须停止?"]
    mod_handoff_gate["未达标:续轮条件全部满足?<br/>验收提交 · 就绪输入 · 授权 · 边界"]
    mod_freeze["确认写者结束并冻结仓库操作<br/>创建唯一下一轮,初始核验后退出"]
    mod_stop_report["终止轮汇总整批状态与停止原因<br/>按固定方式向原主任务或用户交付"]
    mod_round_choice["本轮负责人的拆分选择<br/>沿用本轮 / 整批明确约定"]
    mod_round_agents["默认:拆给内部 Agent<br/>结果先交本轮负责人"]
    mod_round_solo["明确不拆分<br/>本轮任务独立完成"]
    mod_goal_contract -->|"首轮启动"| mod_round
    mod_round -->|"所有权与输入确认"| mod_round_choice
    mod_slice -->|"本轮评估"| mod_stop_check
    mod_stop_check -->|"是"| mod_stop_report
    mod_stop_check -->|"否"| mod_handoff_gate
    mod_handoff_gate -->|"条件不满足"| mod_stop_report
    mod_handoff_gate -->|"全部满足"| mod_freeze
    mod_freeze -.->|"唯一后继接管"| mod_round
    mod_round_choice -->|"默认:有实际拆分收益"| mod_round_agents
    mod_round_choice -->|"明确不拆分 / 无合理拆分点"| mod_round_solo
    mod_round_agents -->|"本轮负责人收齐并整合"| mod_slice
    mod_round_solo -->|"自主实施后收口"| mod_slice
    classDef default fill:#E5F4EC,stroke:#278353,color:#173D29
    class mod_round_agents,mod_round_solo default
    classDef explicit fill:#E8F1FF,stroke:#3B70AD,color:#17324D
    class mod_goal_contract explicit
    classDef gate fill:#FFF3D6,stroke:#A77C25,color:#604715
    class mod_stop_check,mod_handoff_gate,mod_round_choice gate
    classDef stop fill:#FDEBE7,stroke:#B65C49,color:#70352C
    class mod_stop_report stop
```

实线表示条件和交付方向;虚线表示满足条件后的返修、再检查或后继接管,不表示无限循环.

<a id="mod_goal_contract"></a>

**明确迭代并固定契约 / 目标 · 验收 · 上限 · 授权 · 交付方式**: 固定 GOAL 唯一路径、起止编号、首轮位置、后继及提交授权、实际指定预算.不自行填轮数或预算;缺必要项先补缺口.

<a id="mod_round"></a>

**本轮负责人接管 / 读取 GOAL、规则与当前证据**: 默认新 Codex 任务;用户可指定当前任务为首轮.首轮安全确认 GOAL 初始缺失时按授权创建;后轮缺失先恢复核查.

<a id="mod_round_choice"></a>

**本轮负责人的拆分选择 / 沿用本轮或整批明确约定**: 拆分是轮内组织方式,与是否继续下一轮分开判断.默认内部拆分,明确不拆分时独立完成;不重置既定选择,不逐轮重复索取许可.

<a id="mod_round_agents"></a>

**默认:拆给内部 Agent / 结果先交本轮负责人**: Agent 只完成本轮分配成果,不持有迭代后继权;本轮负责人负责最终整合、验证和文档.

<a id="mod_round_solo"></a>

**明确不拆分 / 本轮任务独立完成**: 不创建内部助手,由本轮负责人完成切片.没有合理拆分点时也可说明原因后直接完成.这不改变续轮授权与停止规则.

<a id="mod_slice"></a>

**自主完成可验收切片 / 收齐结果、验证、文档收口**: 默认评估合理内部拆分;用户不拆分则独立完成.不将内部协调交回原主任务,不逐轮催促或汇报流水.

<a id="mod_stop_check"></a>

**达标 / 无有价值下一项 / 必须停止?**: 必须停止包括到达编号或预算边界、必需失败、缺输入、状态未知或用户要求.可范围内解决的普通失败由本轮处理.

<a id="mod_handoff_gate"></a>

**未达标:续轮条件全部满足? / 验收提交 · 就绪输入 · 授权 · 边界**: 续轮需完成获授权提交,真实后继授权及交付能力有效.当前执行授权不推出提交或后继权限;条件不足停止.

<a id="mod_freeze"></a>

**确认写者结束并冻结仓库操作 / 创建唯一下一轮,初始核验后退出**: 冻结后不再读写仓库或运行测试/Git.后继只接固定契约与递增编号;动态事实从项目资料接续.创建未知先核查,不重复创建.

<a id="mod_stop_report"></a>

**终止轮汇总整批状态与停止原因 / 按固定方式向原主任务或用户交付**: 正常交棒不逐轮回调.达标或必须停止时才汇总;需要原主任务解决的真实阻塞可提前反馈.回传、等待、仅交接沿既定选择.

证据:

- `orchestrate-tasks/references/goal-relay.md:3-13`: 显式进入、固定契约、预算和首轮位置.
- `orchestrate-tasks/references/goal-relay.md:39-49`: 接管证据与 GOAL 初始化、恢复和维护.
- `orchestrate-tasks/references/goal-relay.md:53-68`: 收口提交、冻结、唯一后继、停止及整批交付.

## 按需文档读取

这些是条件读取关系,不是执行阶段或自动调用链.

| 条件 | 读取内容 | 条件不成立时 |
| --- | --- | --- |
| 派发内部 Agent | `references/subagents.md` | 不为未采用的内部承载预读 |
| 创建侧栏或整合任务 | `references/new-tasks.md` | 默认当前内部拆分不进入该分支 |
| 侧栏任务使用内部 Agent,或委派后再拆侧栏 | `references/mixed-carriers.md` | 普通内部拆分不加载 |
| 使用侧栏任务 | `references/new-task-callbacks.md` | 内部 Agent 不走侧栏消息路径 |
| 明确选择迭代 | `references/goal-relay.md` | 不因已有 GOAL 文件自动进入 |
| 内部自动选模或复评能力 | `references/model-selection.md` 和 `references/model-routing.json` | 已指定有效值或要求继承时不加载 |
| 所有执行方式交付前 | 按项目路由检查必要文档;通用职责引用 bootstrap-project-context 现有契约 | 不强制全部更新,不因该规则扩大写权 |

证据:

- `orchestrate-tasks/SKILL.md:38-48`: 最小任务包和条件读取入口.
- `orchestrate-tasks/SKILL.md:63-72`: 文档共同规则与只读边界.

## 证据与验证边界

本图核对的是当前指令文档,不是宿主运行时的自动路由实测.输入示例是对已核对规则的归纳,不表示已执行真实业务派发.

离线清点后以 source 模式扫描 `orchestrate-tasks/SKILL.md` 及上述五份执行分支文档,共 6 份 Markdown,扫描状态为 `ok`.未扫描 README、测试和模型策略;模型条件仅依据主入口已核对的引用说明.系统现有 Python 的 Markdown 解析依赖已通过探测;Skill 自带虚拟环境缺少该分支依赖,未安装或改变环境.

内部索引位于 `diagram-codebase/tools/local/scans/84f6751ad2bba4832722/index.json`,仅用于本机取证,不属于交付依赖.查询了入口标题与引用;定向读取子 Agent、侧栏创建、混合承载、回调和 GOAL 接力的相关条件.未分析业务项目,未启动真实编排,未修改 Skill 规则.

图文结构由 `check_diagram.py` 检查;语义逐项对照上述证据,不以结构检查代替业务运行验证.实际 draw.io 画布与 Mermaid 渲染的视觉效果未复核.
