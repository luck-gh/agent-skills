# 模型索引

## 内置可用集合

当前收录 34 位人物,61 个具体模型,每人一个完整核心文件.这里提供按人物和按领域两种精简导航.人物身份,模型标签与适用范围以人物文件 frontmatter 和正文为准,受控词表见[模型标签契约](model-tags.md).models/sources 中的方法与案例笔记只供按需取证,不增加人物或模型数量,不进入本索引.模型是限定主题的整理,不代表完整人物画像.

首次推荐或使用必须读取入选文件,先核对证据是否充分及适用与排除条件,再决定是否选用;不能仅凭本表宣称可用.推荐默认筛选 1-3 个具体模型;显式思维风暴默认选择 3-5 个互补人物视角.只加载入选文件,不因浏览某一领域就批量读取该类全部人物,也不逐项打开 Sources.

## 按人物查找

常用名链接指向唯一人物文件,其他姓名与别名由现有 `person` 和 `aliases` 去重列出,与常用名合看保留全部姓名入口.文件名按入口规则优先使用通行中文名并将中点转换为下划线,展示姓名仍按正常写法,使用时沿用本表精确链接.中文名,英文名和别名都须归到同一 `person_id`;具体模型以 `person_id/model-id` 识别,不因文件名或译名变化创建副本.

| 常用名与人物文件 | 其他姓名与别名 | person_id | 具体模型 ID 与名称 |
| --- | --- | --- | --- |
| [卡帕西](../models/思维模型_卡帕西.md) | Andrej Karpathy, 安德烈·卡帕西, Karpathy | `andrej-karpathy` | `build-to-understand`: 构建即理解 |
| [吴恩达](../models/思维模型_吴恩达.md) | Andrew Ng, Andrew Yan-Tak Ng | `andrew-ng` | `data-centric-improvement`: 由错误定位数据改进<br>`task-level-ai-opportunity`: 按任务选择 AI 机会 |
| [安迪·格鲁夫](../models/思维模型_安迪_格鲁夫.md) | Andy Grove, Andrew S. Grove, 安迪·格罗夫, 安迪·葛洛夫 | `andy-grove` | `organizational-output-and-feedback`: 组织产出与任务反馈<br>`strategic-dissonance-to-reallocation`: 从战略失配到资源重配 |
| [芒格](../models/思维模型_芒格.md) | Charlie Munger, Charles Thomas Munger, 查理·芒格 | `charlie-munger` | `latticework-and-inversion`: 多学科交叉检验与逆向排除<br>`incentives-before-exhortation`: 先查激励再劝说 |
| [哈萨比斯](../models/思维模型_哈萨比斯.md) | Demis Hassabis, 德米斯·哈萨比斯, Demis | `demis-hassabis` | `root-problem-selection`: 根问题与研究杠杆<br>`model-guided-search`: 模型引导搜索与外部检验 |
| [特朗普](../models/思维模型_特朗普.md) | Donald Trump, 唐纳德·特朗普, Donald J. Trump | `donald-trump` | `counterparty-payoffs`: 从对手的替代成本寻找议价空间 |
| [段永平](../models/思维模型_段永平.md) | Duan Yongping, 大道, 大道无形我有型 | `duan-yongping` | `right-direction-before-execution`: 先分清方向错误与执行错误<br>`understand-business-before-price`: 懂生意后看价格与波动 |
| [马斯克](../models/思维模型_马斯克.md) | Elon Musk, 埃隆·马斯克, Musk | `elon-musk` | `first-principles-constraints`: 从基本约束重建方案 |
| [李飞飞](../models/思维模型_李飞飞.md) | Fei-Fei Li, Feifei Li, Li Fei-Fei | `fei-fei-li` | `human-centered-design`: 从人的需求定义 AI 价值<br>`perception-action-grounding`: 用行动检验空间理解 |
| [辛顿](../models/思维模型_辛顿.md) | Geoffrey Hinton, 杰弗里·辛顿, Geoffrey E. Hinton | `geoffrey-hinton` | `distill-decision-behavior`: 按部署约束迁移决策能力 |
| [索罗斯](../models/思维模型_索罗斯.md) | George Soros, 乔治·索罗斯, 乔治索罗斯 | `george-soros` | `reflexive-feedback`: 预期与现实的反身循环<br>`uncertainty-sized-commitment`: 让承诺规模适应不确定性 |
| [霍华德·马克斯](../models/思维模型_霍华德_马克斯.md) | Howard Marks, 霍华德·马可斯, 马克斯 | `howard-marks` | `second-level-pricing`: 共识定价的第二层思考<br>`market-temperature`: 市场温度与攻守姿态 |
| [伊利亚·苏茨克维](../models/思维模型_伊利亚_苏茨克维.md) | Ilya Sutskever, 伊利亚, Ilya | `ilya-sutskever` | `reliable-generalization`: 验证真实泛化<br>`productive-scaling`: 检验扩规模的有效学习 |
| [黄仁勋](../models/思维模型_黄仁勋.md) | Jensen Huang, Jen-Hsun Huang | `jensen-huang` | `recheck-strategic-premises`: 反复检查战略前提<br>`platform-adoption-loop`: 让平台能力变成开发者采用 |
| [吉姆·凯勒](../models/思维模型_吉姆_凯勒.md) | Jim Keller, 吉姆凯勒 | `jim-keller` | `testable-abstraction-layers`: 保持抽象层可理解与可检验<br>`separate-performance-constraints`: 拆分性能约束再确定改进点 |
| [吉姆·西蒙斯](../models/思维模型_吉姆_西蒙斯.md) | Jim Simons, 詹姆斯·西蒙斯, James Harris Simons, 西蒙斯 | `jim-simons` | `data-to-testable-model`: 将观察转成可检验模型<br>`collaborative-science`: 以互补研究者组织发现 |
| [朱迪亚·珀尔](../models/思维模型_朱迪亚_珀尔.md) | Judea Pearl, 朱迪亚·皮尔, 珀尔, Pearl | `judea-pearl` | `identify-before-estimate`: 先定义因果问题再估计<br>`graph-guided-adjustment`: 由因果图选择调整变量 |
| [孙宇晨](../models/思维模型_孙宇晨.md) | Justin Sun, 孙雨晨, 孙哥 | `justin-sun` | `utility-before-adoption`: 从实际用途降低采用门槛<br>`network-incentive-bridge`: 连接既有网络与贡献激励 |
| [李录](../models/思维模型_李录.md) | Li Lu, Louis Li | `li-lu` | `intellectual-honesty-and-boundaries`: 知识诚实与可反驳的能力边界<br>`patient-owner-selection`: 耐心筛选与长期所有权 |
| [苏姿丰](../models/思维模型_苏姿丰.md) | Lisa Su, 蘇姿丰 | `lisa-su` | `capability-led-long-horizon`: 能力聚焦与长期技术路线<br>`architecture-around-system-constraints`: 围绕系统约束重选架构 |
| [张忠谋](../models/思维模型_张忠谋.md) | Morris Chang, 張忠謀 | `morris-chang` | `specialization-with-customer-trust`: 专业分工与客户信任<br>`manufacturing-to-economic-value`: 制造能力到经济价值的闭环 |
| [野兽先生](../models/思维模型_野兽先生.md) | Jimmy Donaldson, MrBeast, 吉米·唐纳森 | `mrbeast` | `audience-promise-feedback`: 观众承诺与反馈迭代 |
| [塔勒布](../models/思维模型_塔勒布.md) | Nassim Nicholas Taleb, Nassim Taleb, 纳西姆·尼古拉斯·塔勒布 | `nassim-nicholas-taleb` | `fragility-before-forecast`: 先查脆弱性再谈预测<br>`convex-experiment-portfolio`: 有限损失的凸性试验组合 |
| [纳瓦尔](../models/思维模型_纳瓦尔.md) | Naval Ravikant, 纳瓦尔·拉维坎特, Naval | `naval-ravikant` | `specific-knowledge-leverage`: 特定知识与可复制杠杆<br>`trust-compounds`: 信任与重复合作 |
| [保罗·格雷厄姆](../models/思维模型_保罗_格雷厄姆.md) | Paul Graham, PG | `paul-graham` | `writing-to-think`: 写作即思考<br>`iterative-discovery`: 迭代发现 |
| [彼得·林奇](../models/思维模型_彼得_林奇.md) | Peter Lynch, 彼得林奇 | `peter-lynch` | `observation-to-research`: 从熟悉观察走向公司研究<br>`story-over-price`: 随经营故事更新判断 |
| [瑞·达利欧](../models/思维模型_瑞_达利欧.md) | Ray Dalio, 瑞达利欧, 达利欧 | `ray-dalio` | `balance-economic-exposures`: 按经济驱动平衡风险<br>`believability-weighted-disagreement`: 用可信依据处理分歧 |
| [费曼](../models/思维模型_费曼.md) | Richard Feynman, 理查德·费曼, Feynman | `richard-feynman` | `anti-self-deception`: 反自欺 |
| [理查德·萨顿](../models/思维模型_理查德_萨顿.md) | Richard S. Sutton, 萨顿, Rich Sutton, Richard Sutton | `richard-sutton` | `learn-from-consequences`: 从行动后果学习<br>`scalable-discovery`: 可扩展发现 |
| [乔布斯](../models/思维模型_乔布斯.md) | Steve Jobs, 史蒂夫·乔布斯, Jobs | `steve-jobs` | `focus-through-subtraction`: 聚焦与产品减法<br>`own-the-user-journey`: 对完整体验负责 |
| [巴菲特](../models/思维模型_巴菲特.md) | Warren Buffett, 沃伦·巴菲特 | `warren-buffett` | `competence-and-owner-value`: 能力圈内的所有者估值<br>`moat-and-incremental-capital`: 护城河与新增资本回报 |
| [杨立昆](../models/思维模型_杨立昆.md) | Yann LeCun, 扬·勒昆, 勒昆, LeCun | `yann-lecun` | `predict-useful-representations`: 预测有用表征<br>`objective-driven-replanning`: 以目标驱动滚动规划 |
| [张雪峰](../models/思维模型_张雪峰.md) | Zhang Xuefeng | `zhang-xuefeng` | `career-backcast`: 从职业入口倒推教育路径<br>`ordinary-outcomes`: 检查普通人的出路 |
| [张一鸣](../models/思维模型_张一鸣.md) | Zhang Yiming, Yiming Zhang | `zhang-yiming` | `context-aligned-decisions`: 用共享背景支持分布式判断 |

## 按领域浏览

以下中文分类仅把现有 `domains`,`tasks`,`methods` 与具体 `scope` 组合成浏览视图,不新增标签或分类字段.条目只适用于列出的模型 ID 和用途,不由人物职业推导其全部模型适用.跨类链接仍指向同一人物文件;汇总候选时按 `person_id/model-id` 去重,安排人物视角时再按 `person_id` 去重.

| 领域 | 当前问题与具体模型 |
| --- | --- |
| 科技与产品 | [乔布斯](../models/思维模型_乔布斯.md): `focus-through-subtraction` 功能与产品线取舍; `own-the-user-journey` 完整用户体验<br>[马斯克](../models/思维模型_马斯克.md): `first-principles-constraints` 基本约束与行业惯例<br>[保罗·格雷厄姆](../models/思维模型_保罗_格雷厄姆.md): `iterative-discovery` 早期需求验证<br>[段永平](../models/思维模型_段永平.md): `right-direction-before-execution` 区分方向与执行错误<br>[塔勒布](../models/思维模型_塔勒布.md): `convex-experiment-portfolio` 可隔离损失的产品试验 |
| 芯片与半导体 | [吉姆·凯勒](../models/思维模型_吉姆_凯勒.md): `testable-abstraction-layers` 架构层次与验证; `separate-performance-constraints` 计算,存储与通信瓶颈<br>[苏姿丰](../models/思维模型_苏姿丰.md): `capability-led-long-horizon` 长期技术路线; `architecture-around-system-constraints` 工作负载与系统架构取舍<br>[张忠谋](../models/思维模型_张忠谋.md): `specialization-with-customer-trust` 产业分工与合作边界; `manufacturing-to-economic-value` 良率,成本与量产交付<br>[黄仁勋](../models/思维模型_黄仁勋.md): `recheck-strategic-premises` 长期技术投入的前提; `platform-adoption-loop` 芯片能力到开发者应用 |
| AI | [卡帕西](../models/思维模型_卡帕西.md): `build-to-understand` 神经网络最小实现与调试<br>[吴恩达](../models/思维模型_吴恩达.md): `data-centric-improvement` 数据错误与覆盖缺口; `task-level-ai-opportunity` 按具体任务选择应用<br>[哈萨比斯](../models/思维模型_哈萨比斯.md): `root-problem-selection` 研究瓶颈与可行验证; `model-guided-search` 模型引导搜索与独立检验<br>[李飞飞](../models/思维模型_李飞飞.md): `human-centered-design` 人的实际需求; `perception-action-grounding` 空间理解的行动验证<br>[辛顿](../models/思维模型_辛顿.md): `distill-decision-behavior` 部署约束下的知识蒸馏<br>[伊利亚·苏茨克维](../models/思维模型_伊利亚_苏茨克维.md): `reliable-generalization` 真实泛化; `productive-scaling` 算力投入与有效学习<br>[理查德·萨顿](../models/思维模型_理查德_萨顿.md): `learn-from-consequences` 智能体结果反馈; `scalable-discovery` 计算与经验带来的策略发现<br>[杨立昆](../models/思维模型_杨立昆.md): `predict-useful-representations` 任务相关表征; `objective-driven-replanning` 世界模型与滚动规划<br>[黄仁勋](../models/思维模型_黄仁勋.md): `platform-adoption-loop` 仅用于 AI 基础设施的工具,迁移与采用 |
| 金融投资 | [巴菲特](../models/思维模型_巴菲特.md): `competence-and-owner-value` 所有者估值; `moat-and-incremental-capital` 竞争优势与新增资本<br>[芒格](../models/思维模型_芒格.md): `latticework-and-inversion` 交叉检验与失败条件; `incentives-before-exhortation` 投资建议和治理中的利益冲突<br>[段永平](../models/思维模型_段永平.md): `understand-business-before-price` 经营理解与价格波动<br>[李录](../models/思维模型_李录.md): `intellectual-honesty-and-boundaries` 可反驳的能力边界; `patient-owner-selection` 长期所有权与耐心筛选<br>[彼得·林奇](../models/思维模型_彼得_林奇.md): `observation-to-research` 产品线索到公司研究; `story-over-price` 随经营变化更新判断<br>[霍华德·马克斯](../models/思维模型_霍华德_马克斯.md): `second-level-pricing` 前景与共识定价; `market-temperature` 风险补偿与投入节奏<br>[索罗斯](../models/思维模型_索罗斯.md): `reflexive-feedback` 预期,融资与基本面的循环; `uncertainty-sized-commitment` 波动路径与承受能力<br>[瑞·达利欧](../models/思维模型_瑞_达利欧.md): `balance-economic-exposures` 经济驱动与组合风险<br>[塔勒布](../models/思维模型_塔勒布.md): `fragility-before-forecast` 尾部暴露与不可恢复损失<br>[吉姆·西蒙斯](../models/思维模型_吉姆_西蒙斯.md): `data-to-testable-model` 检验重复数据中的经验规律 |
| 组织管理 | [安迪·格鲁夫](../models/思维模型_安迪_格鲁夫.md): `organizational-output-and-feedback` 组织产出与任务支持; `strategic-dissonance-to-reallocation` 战略失配与资源重配<br>[张一鸣](../models/思维模型_张一鸣.md): `context-aligned-decisions` 共享背景与分布式判断<br>[芒格](../models/思维模型_芒格.md): `incentives-before-exhortation` 制度目标与实际行为偏差<br>[瑞·达利欧](../models/思维模型_瑞_达利欧.md): `believability-weighted-disagreement` 按相关经验和依据处理分歧<br>[吉姆·西蒙斯](../models/思维模型_吉姆_西蒙斯.md): `collaborative-science` 围绕共同问题组织互补研究<br>[纳瓦尔](../models/思维模型_纳瓦尔.md): `trust-compounds` 长期合作与信用 |
| 学习与研究 | [费曼](../models/思维模型_费曼.md): `anti-self-deception` 暴露反证与工程证据审查<br>[朱迪亚·珀尔](../models/思维模型_朱迪亚_珀尔.md): `identify-before-estimate` 先判断因果效果能否识别; `graph-guided-adjustment` 按因果路径选择调整变量<br>[卡帕西](../models/思维模型_卡帕西.md): `build-to-understand` 用最小实现检验机制理解<br>[李录](../models/思维模型_李录.md): `intellectual-honesty-and-boundaries` 区分已知事实与可反驳假设 |
| 传播,职业与协商 | [保罗·格雷厄姆](../models/思维模型_保罗_格雷厄姆.md): `writing-to-think` 用表达暴露推理缺口<br>[野兽先生](../models/思维模型_野兽先生.md): `audience-promise-feedback` 内容承诺与观众反馈<br>[纳瓦尔](../models/思维模型_纳瓦尔.md): `specific-knowledge-leverage` 专长与可重复交付<br>[张雪峰](../models/思维模型_张雪峰.md): `career-backcast` 从职业入口倒推教育路径; `ordinary-outcomes` 检验相近背景者的常见去向<br>[特朗普](../models/思维模型_特朗普.md): `counterparty-payoffs` 一般商业议价中的双方替代成本 |
| 平台生态 | [黄仁勋](../models/思维模型_黄仁勋.md): `platform-adoption-loop` 工具,库与开发者采用<br>[孙宇晨](../models/思维模型_孙宇晨.md): `utility-before-adoption` 实际用途与迁移门槛; `network-incentive-bridge` 已有网络中的真实贡献与激励<br>[张忠谋](../models/思维模型_张忠谋.md): `specialization-with-customer-trust` 伙伴分工与可信合作边界 |

领域入口不覆盖模型限制.黄仁勋的条目用于技术投入前提与开发者采用,不能当作芯片设计,模型训练或当前市场预测;孙宇晨的条目不用于代币估值.格鲁夫的组织方法和西蒙斯的协作研究不能因职业经历自动变成芯片工程或交易策略.多位价值投资者也不天然构成互补视角.证据不足的项保留为待核验,命中排除条件的项不入选,不能靠分类匹配获得可用资格.

## 扩展边界

已纳入的人物不再重复列为待核验候选;同一人物的未收录观点不能从记忆直接补成模型.其他新发现人物只有在用户授权扩展且达到证据合同后才加入.

本索引只导航已成形的本地人物模型,不保存外部项目候选或更新目标.主题导师不属于人物模型,不纳入集合.证据等级与复用边界见[来源政策](source-policy.md).
