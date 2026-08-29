---
name: new-skills
description: 通用 Skill 生命周期入口,覆盖首次配置,创建,安装,更新,迁移,移动,修复,metadata 维护,skill-local settings,独立分发,仓库更新检查和验收.用于初始化物理/Agent 使用地址,变更 Skill 内容或结构,安装或升级 Skill,显式查询更新,或执行生命周期验收;仅阅读,使用或解释且不要求验收时不触发.按目标平台契约处理 initializer,格式,metadata adapter,validator 和可选 discovery entry.
---

# Skill lifecycle

将本 Skill 作为 Skill 内容与结构变更及生命周期验收的入口.领域 Skill 可以补充专业规则,但不得替代这里的结构,metadata,内容风格和验收边界.

每次用于安装,创建,更新,迁移,移动,修复或验收时,按 [仓库更新契约](references/repository-updates.md) 运行 24 小时 TTL 检查.检查失败不阻塞当前任务;发现更新也先完成当前任务,再报告变化并询问是否升级.用户显式询问更新时强制检查.只有用户确认后才能带 `--authorized` 和本次 `update_id` 执行升级.

## Establish the contract

1. 从用户输入,现有目标和仓库规则确定目标平台契约.只采用契约明确声明的 initializer,入口格式,metadata adapter,validator 和 discovery 机制.
2. 用具体用例确认触发方式,输入和输出,并把所需内容分为触发 metadata,命中后常驻正文,条件引用和可执行或产物资源,再规划必要的 `scripts/`,`references/`,`assets/` 与平台 metadata.
3. 将名称规范化为小写 hyphen-case.显式 physical dir 或 physical parent 始终优先;只有路径缺失时才按 [skill-local settings](references/local-settings.md) 读取本 Skill 同级的 `settings.json`.
4. 首次配置时从当前或目标 Agent 的明确运行上下文或官方平台契约确定 usage root.展示 Agent 与该地址,并在同一个问题中让用户提供 physical root 和可选的 usage root 修改值.用户只回复 physical root 时即视为接受已展示的 usage root;不得再要求确认两个地址.不得扫描磁盘,枚举副本或从历史设置猜测 Agent 地址.
5. 得到有效 physical root 后立即按 [skill-local settings](references/local-settings.md) 把完整二字段配置写入 `settings.json` 并回读验证.用户请求“先不创建目标 Skill/文件”不阻止此首次配置;只有用户明确禁止写入 New Skills 自身配置时才保持不落盘.两者相同时直接使用 physical skill;不同时才管理独立 discovery entry.

Settings 值只提供路径候选,不构成创建,移动,删除,复制,链接或其他副作用授权.

## Modify the Skill

1. Create 时只在目标平台要求时运行其 initializer.Update 和 repair 直接编辑.Migrate 或 move 保持单一 physical source of truth,先明确目标,冲突,授权和可恢复路径.
2. 遵循目标平台的入口与 frontmatter 规则,按加载阶段组织内容.`description` 必须包含 Skill 能力,全部触发场景和必要排除条件;不得把首次命中所需信息只放在正文或 references.
3. `SKILL.md` 正文只保留命中后每次都需要的核心流程,全局约束,不可延迟的安全边界和条件路由.每条条件路由必须在正文说明读取条件并直接链接一级 `references/`;只在条件成立后需要的 schema,平台或情形分支,例外,长步骤和示例放入相应引用.信息只保留一个权威位置,不得在正文与引用重复,也不得把路由条件完全藏入引用.不要增加 README,CHANGELOG 或过程记录.
4. 每个 Skill 默认无状态且可独立分发.所有运行时实现和资源必须位于自身 physical skill dir;不得引用兄弟 Skill,`../_dev` 或仓库级运行时代码.平台 adapter 和 discovery entry 不得成为第二份内容源.
5. 只在确定性,重复调用或难以可靠手写时保留 Python.删除占位脚本,一次性迁移脚本和等价转发入口.在目标 `SKILL.md` 中用直接 Markdown 链接声明每个公开 `scripts/*.py`;fenced code,inline code 和命令示例只表达用法,不构成声明.`src/` 内部实现不要求逐文件声明.
6. 每个 Python 模块用中文模块注释说明存在理由,应用场景和用法.代码只检查直接输入契约,必要安全边界和可观察输出,不为未出现的竞态或平台分支建立框架.
7. 仅在目标平台声明 metadata adapter 时创建或更新 metadata,并只写契约要求且已有来源的字段.修改后核对 metadata 与最终 `SKILL.md` 的名称,触发和能力一致.
8. 对 skill-local settings 按 [local-settings.md](references/local-settings.md) 处理.首次流程中用户提交 physical root 即授权以已展示或同轮修改的 usage root 创建默认设置;其他 settings 创建或修改仍需用户明确要求.Example 不是默认值或 fallback.
9. 若新增第三方依赖,记录 source URL,exact version,license,integrity hash,平台和运行时边界;未新增时报告"无".独立分发表示 Skill 文件闭包完整,不表示第三方包被复制进 Skill;隔离验收必须在已声明依赖可用的运行时执行.

## Content style

对 `SKILL.md`,`references/**/*.md` 和 `agents/**/*.{yaml,yml}` 中由当前仓库维护的中文正文执行 [scripts/check_content_style.py](scripts/check_content_style.py).将 `，。；：！？（）【】、` 改为对应英文半角标点;排除 fenced/inline code,命令,路径,URL,regex,语言语法和必须原样保留的 blockquote.工具只报告,不得自动改写.

## Test ownership

`tests/` 不属于通用 Skill 模板.`new-skills` 不提示创建,生成,复制或集中保存领域测试.目标 Skill 已有测试只覆盖其复杂领域逻辑,保留在所属 Skill 内;本轮涉及对应逻辑时才运行.不要用测试重复纯文案,标题顺序或已由通用 validator 覆盖的静态契约.

`new-skills/tests` 只测试本 Skill 的通用 validator,风格检查和 discovery entry 工具.

## Python resources

| Public entry | Implementation | Reason and use |
| --- | --- | --- |
| [scripts/check_content_style.py](scripts/check_content_style.py) | 同一文件 | 检查明确传入的 Skill 中文正文标点. |
| [scripts/ensure_skill_entry.py](scripts/ensure_skill_entry.py) | 同一文件 | 检查或创建目标平台声明的单一 discovery entry. |
| [scripts/manage_updates.py](scripts/manage_updates.py) | 同一文件 | 检查 Git 真源或公共安装并在授权后安全升级. |
| [scripts/validate_skill.py](scripts/validate_skill.py) | 同一文件 | 只读检查通用 Skill 分发契约,不执行领域行为. |

`scripts/validate_skill.py` 的外部运行时依赖是 PyYAML 6.0.2[source](https://pypi.org/project/PyYAML/6.0.2/),MIT License.当前验收平台使用 `PyYAML-6.0.2-cp312-cp312-win_amd64.whl`,SHA-256 `7e7401d0de89a9a855c839bc697c079a4af81cf878373abd7dc625847d25cbd8`,边界为 CPython 3.12,Windows x86-64;其他平台必须选择 PyPI 对应 6.0.2 artifact 并核对其哈希.分发副本不 vendoring 此依赖;调用环境必须预先提供精确版本.

## Optional discovery entry

只有 `usage_root` 与 `physical_root` 不同时才读取 [junction-safety.md](references/junction-safety.md).先运行只读 `inspect`;仅在用户明确授权且 entry 缺失时运行 `ensure --authorized`:

```text
python -X utf8 -B scripts/ensure_skill_entry.py inspect --physical-dir <physical-dir> --entry-dir <entry-dir> [--validator <validator.py>]
python -X utf8 -B scripts/ensure_skill_entry.py ensure --physical-dir <physical-dir> --entry-dir <entry-dir> [--validator <validator.py>] --authorized
```

## Validate and report

1. 对照具体用例人工核对渐进式披露:`description` 覆盖全部触发与排除信息;正文只保留常驻规则与条件路由;每个引用都在正文写明读取条件;正文与引用没有重复权威内容.不得用文件行数或字数替代这项语义验收.
2. 按 [validation-contract.md](references/validation-contract.md) 运行 `python -X utf8 -B scripts/validate_skill.py --json <physical-skill-dir> [...]`.它只检查通用契约,不导入或执行目标 Skill 的领域入口.
3. 运行目标平台明确声明的 validator.对于官方 OpenAI Skill,运行 `$skill-creator` 提供的 `quick_validate.py`.
4. 运行 `python -X utf8 -B scripts/check_content_style.py --json <physical-skill-dir> [...]`.
5. 仅在本轮修改复杂领域逻辑时运行所属 Skill 的现有测试.仓库开发工具变更运行自身测试与 `git diff HEAD --check`.
6. Settings 变更核对显式输入优先,目标冲突,所属 Skill 业务校验与隔离分发;discovery 变更核对 exact target.不要无条件叠加无关检查.
7. 报告授权范围,文件所有权,content,metadata,settings,discovery,validator,测试,第三方依赖,只读发现和未解决冲突.
