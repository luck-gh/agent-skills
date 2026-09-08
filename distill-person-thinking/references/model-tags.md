# 模型标签契约

标签附着在具体模型上,人物姓名和职业不是匹配标签.本文件是受控词表的唯一真源.采用多面分类:领域限定问题环境,任务说明要完成什么,方法说明如何思考.不以关键词出现次数或人物知名度排序.

索引中的中文分类是现有标签与 `scope` 所表达范围的导航视图,不增加人物分类字段,领域子目录或第二套词表.人物可出现在多个分类中,均指向同一人物文件;所属分类不代表其全部模型都适用于该领域.

## 固定字段

核心 frontmatter 的 `models` 保存每个模型的精简检索信息.正文相应模型以 `### <id>: <name>` 定位,内置模型的稳定身份为 `<person_id>/<model-id>`.内置 `person_id` 遵循[人物模型合同](profile-contract.md),中文文件名,展示姓名和导航分类不参与身份生成.跨分类按 `person_id` 去重人物,按 `(person_id, model-id)` 去重具体模型;外部文件按入口现有身份规则核验及去重,不要求普通使用时补字段或改名.

标签由维护者根据正文和证据赋予,不能因为一次对话出现新词而自动扩词或改模型.

```yaml
models:
  - id: writing-to-think
    name: 写作即思考
    summary: 用明确表达和反复改写发现推理缺口
    domains: [general, communication]
    tasks: [explain, decide]
    methods: [externalize, feedback]
    use_when: 想法含混或方案难以说清
    avoid_when: 只需查一个事实或润色措辞
```

- `id` 必须 lowercase hyphen-case,在人物内唯一,更新不重排或复用旧 ID;人物文件重命名或导航分类调整不得改变已有 `models[].id`.
- `name`,`summary`,`use_when`,`avoid_when` 都是非空短文本.摘要不承载来源或长步骤.
- 三组标签各取 1-3 个最能区分用途的值.缺证据的模型不能靠标签获得可用资格.
- 正文与摘要矛盾时停止推荐该项,报告待修复.没有 `models` 检索字段的外部文件标为未索引,推荐时不全读正文补标签或自动迁移;指定人物使用仍按原有完整性规则判断.

## 受控词表

| 字段 | 允许值及含义 |
| --- | --- |
| domains | `general` 跨领域; `engineering` 工程; `research` 研究; `product` 产品; `business` 商业; `communication` 沟通写作; `learning` 学习教学; `career` 职业; `organization` 组织; `investing` 投资 |
| tasks | `decide` 决策; `diagnose` 诊断; `explain` 解释; `learn` 学习; `design` 设计; `prioritize` 排序取舍; `validate` 验证; `create` 创作; `negotiate` 协商 |
| methods | `decompose` 拆解; `invert` 逆向; `falsify` 证伪; `experiment` 实验; `feedback` 反馈迭代; `externalize` 外化表达; `leverage` 可复制投入; `compound` 长期积累; `incentives` 激励; `subtract` 减法; `asymmetry` 非对称; `analogy` 类比; `causal` 因果建模,干预与反事实 |

`general` 不等于万能或优先匹配.自然语言按含义映射,例如排错/调试 -> `diagnose`,讲不清/解释 -> `explain`,功能堆积 -> `prioritize` + `subtract`,只看成功案例 -> `validate` + `falsify`.这里是示例,无需穷举同义词.

扩词仅在蒸馏或维护中发现现有词表无法表达真实模型用途时进行,同批更新此表及相关模型,保持英文值稳定.不增加人格标签,褒贬等级或推断用户心理状态的标签.
