# 来源与复用边界

## 来源等级

按以下顺序判断来源,但质量高于数量:

1. P1: 本人创作的完整公开材料,例如著作,论文,博客,公开信和演讲原文.
2. P2: 经核验的本人社交账号原始内容,完整访谈,公开问答和决策复盘.
3. P3: 可观察的行动和决策记录,例如发布,公开提交,听证或可核验项目结果.
4. S1: 可信媒体,编辑严谨的传记或同行直接评价.
5. L1: 已有开源 Skill,人物摘要和社区整理,仅用于发现线索.

搜索摘要,聚合转载,无上下文截图,无出处金句和模型训练记忆不构成证据.

新建或更新模型时,将实际采用的外部证据按[来源蒸馏规范](source-distillation.md)整理为方法与案例笔记.本地 Markdown 是当前 Agent 的归纳,证据等级仍由原始材料决定;更长的摘要,更多文件或更强的整理模型均不能提升来源等级.保留原始 URL 与已读范围供追溯,不把网页格式转换当作蒸馏完成.

## 公开 Skill 的复用

- 打开实际 `SKILL.md` 和它引用的来源,核对仓库,作者,license,版本和适用范围.
- 将已有 Skill 的模型视为待验证假设.追溯不到原始来源时,不得把它升级为当前人物核心模型.
- 优先独立归纳和改写,不要复制独特表述,模板,脚本,图标,品牌素材或完整目录.
- 确需复用代码或实质性文本时,先核对精确文件的 license 和归属要求,取得与当前项目规则相符的授权并记录来源.
- stars,forks,示例对话和作者自评只能反映关注度或宣称,不能证明蒸馏准确性.

## 已核对的上游设计与取舍

定向核对日期 2026-09-08,复用此前已充分核验的 Nuwa/Steamer 版本.下表只评价实际读取的相关文件,不代表整库逐行审计;链接固定本次版本.Star 只用于发现,查询值属于仓库,合集热度不等于单个人物质量,不进入模型排序.

| 仓库与实际文件 | 值得吸收的点及所解决问题 | 当前落地与覆盖状态 | 不采用的内容及原因 |
| --- | --- | --- | --- |
| [agenmod/steamer-skill 入口](https://github.com/agenmod/steamer-skill/blob/53d44ba40caa75d620d26099c5e5665d7b268cde/SKILL.md) | 顾问定位,证据分级,方法与背景分开,保留矛盾,防止人物模仿替代判断 | 已覆盖于入口共用边界,本文件及[人物合同](profile-contract.md)的 Core models/Tensions,继续复用 | 私聊采集,数字替身和多文件人格/记忆结构不属于当前目标 |
| [alchaincyf/nuwa-skill 入口](https://github.com/alchaincyf/nuwa-skill/blob/fe0374687037c4cc51a65c1e0c145afe2981dc69/SKILL.md)及人物示例 | 多源交叉核验,模型/启发式区分,已知案例回放,外推边界;减少无证据名人标签 | 已覆盖[蒸馏流程](distill-mode.md)与[推荐流程](recommend-mode.md);本批继续补齐人物文件,具体范围见[模型索引](model-index.md) | 角色扮演,强制语气,固定六 Agent,整本语料下载及主题导师不采用;自评不当保真证明 |
| [K-Dense-AI/mimeographs Pearl](https://github.com/K-Dense-AI/mimeographs/blob/a38f5fcad0853be3e98a6cd95d8e6bf8c66f7c7b/mimeographs/judea-pearl/SKILL.md)及本批 AI 人物入口 | 按人物定位框架与研究线索,区分领域能力;补充科学和技术视角 | 本批写入 Pearl 的因果识别,Hassabis 的根问题与搜索,Hinton 的能力迁移,LeCun 的表征与规划,Sutton 的经验学习,吴恩达的数据/任务分析,李飞飞的人本/空间行动模型;只为因果方法补 causal 标签,复用单文件与有界加载 | 不移植自动触发,语录/语料目录,固定研发比例或忽略成本的指令;关于 AGI,风险,预训练和 LLM 能力的争议判断不当强制真理,上游自评分不当证据 |
| [questflowai/investorskills Marks](https://github.com/questflowai/investorskills/blob/2844d7809a73c01e769c8c1c7ae8189788db4d9e/skills/marks-cycles/invest.md)及相关人物 SKILL/invest 文件 | 将适用环境,输入,时间尺度,风险和判断失效条件结构化;减少只有观点没有使用条件的问题 | 人物原始证据复核后进入金融模型;现有 Use when/Signals/Limits 已覆盖,风暴共同问题继续固定时间尺度 | alpha 模板的空泛字段和未核实交易阈值不抄;不增加另一份 invest.md,交易执行 schema 或外部服务依赖 |
| [wbh604/UZI-Skill investor-panel](https://github.com/wbh604/UZI-Skill/blob/650788c54a9b2e042bf7f983f16dbf8d727fce1d/skills/investor-panel/SKILL.md),[investor_profile.py](https://github.com/wbh604/UZI-Skill/blob/650788c54a9b2e042bf7f983f16dbf8d727fce1d/skills/deep-analysis/scripts/lib/investor_profile.py) | 先按适用范围筛视角,明确时间尺度及改变判断条件,防止所有人物都对所有问题评分 | 筛选已由排除标签覆盖;改变判断条件进入[风暴](brainstorm-mode.md)每个视角摘要和分歧表 | 全员投票,语气模仿,每次读语录,流派默认值冒充个人方法不采用;文件人数口径不一致,不照搬,不移植分析引擎和缓存 |
| [virattt/ai-hedge-fund Buffett signal](https://github.com/virattt/ai-hedge-fund/blob/fc1bf250ead209ae5f02c39c3d0062c4bb554505/hedge_fund/signals/buffett.py) | 同一时点数据底稿与不足时保留未知,防止回放偷看未来及各视角各用一套事实 | 本批补[风暴](brainstorm-mode.md)共同事实的来源/时间/单位/版本同步,普通使用保留事实核验 | 数字置信度,买卖信号,本人身份 prompt,模型运行框架与交易能力不搬入;数据不足不强行解释为看空 |
| [tradermonty/claude-trading-skills pre-trade-discipline-gate](https://github.com/tradermonty/claude-trading-skills/blob/87010e402751531943dd44bca3e8fc35884f2594/skills/pre-trade-discipline-gate/SKILL.md) | 区分缺输入,违反约束和无可执行动作,防止未知被当通过或失败 | 本批在[风暴](brainstorm-mode.md)方案选择中区分可选/待核验/不适用/违反硬约束;分析与执行授权分开已覆盖 | 不引入交易检查脚本,持仓状态,自动日志,定时复核或券商依赖;当前 Skill 无需交易运行环境 |
| [coreyhaines31/makerskills maker-council](https://github.com/coreyhaines31/makerskills/blob/1868b816090246ced9be9ef3556726c4dc94877c/skills/maker-council/SKILL.md),[advisor-template](https://github.com/coreyhaines31/makerskills/blob/1868b816090246ced9be9ef3556726c4dc94877c/skills/maker-council/references/advisor-template.md) | 按问题选择少量互补席位,只读入选资料,把分歧还原为约束和能解决分歧的证据,保留反对方警报 | 3-5 视角与按需加载已覆盖;本批将[风暴](brainstorm-mode.md)分歧-前提-证据-改选条件表和复核信号明确化 | 不强制反对者或制造分歧;不仿语气,扫描其他记忆,自动存档,依赖相邻 Skill,另起 council 配置或把选择交给另一入口 |
| [wondelai/skills high-output-management](https://github.com/wondelai/skills/blob/eade5d170b3a593c5b6ebcaca898102134aee108/high-output-management/SKILL.md) | 从产出,瓶颈及任务成熟度判断管理动作,补充技术组织和转型视角 | 本批按原始材料核验后写入 [格鲁夫模型](../models/思维模型_安迪_格鲁夫.md),沿用既有方法/信号/局限字段 | 不把统一 10 分制,固定会议频率或整套管理模板当适合所有团队的规定 |
| [OpenDemon/jensen-huang-skill 入口](https://github.com/OpenDemon/jensen-huang-skill/blob/ef709020b00c78e6bf31a61d02b0c070d3ea2d6e/SKILL.md)及 research | 平台采用循环与战略前提重审,补充硬件之外的软件生态和客户采用约束 | 本批回到本人公开访谈归纳为 [黄仁勋模型](../models/思维模型_黄仁勋.md),风暴按实际瓶颈选用 | 不将 All-in,固定直属人数,取消一对一或强制韧性视为通用工程规则;不引入角色扮演与上游运行指令 |

本 Skill 的三面标签是当前检索合同,不是复制人格标签.所有库只提供研究与流程线索,不执行其代码,不引入向量数据库,自动画像或后台推荐.各人物文件保存自己的上游版本,许可与原始出处;没有明确复用许可时仅定位主题,从公开原始材料独立归纳,不复制实质文本.方法收录不等于采纳上游全部观点.

## 社交平台材料

- 通过人物官网,组织官网或多个一致的公开链接确认账号归属.
- 记录原始帖子 URL,日期和上下文.优先 thread,长文和持续重复的观点,降低孤立短帖权重.
- 区分本人发言,转发,引用他人和账号管理员内容.
- 已删除,付费或登录受限内容不得绕过访问控制获取.第三方存档只能作为辅助线索并明确标注.

## 隐私与安全

- 公众人物只使用与公共活动和公开思想有关的材料,不收集住址,家人隐私,账号凭据或其他敏感信息.
- 非公众人物只处理用户提供且确认有权使用的材料.不得主动搜索私人账号,泄露的聊天记录或数据经纪来源.
- 原始语料不写入人物模型目录.核心保存执行所需的结论与边界,按需来源笔记保存独立归纳的方法,案例,证据编号和原始定位;不保存网页转录,完整访谈或下载缓存.
- 不代表人物作出承诺,背书,政治表态,医疗意见,法律意见或投资决定.

## 时间与不确定性

每次蒸馏记录研究截止日期.人物观点可能变化;当前事实必须在使用时另行核对.材料不足,账号存疑,来源冲突或模型只适用于特定时期时,降低置信度并明确写入边界.
