# new-skills

创建,安装,修改和验收 Skill 的统一生命周期入口.它把目标平台规则,物理存放位置,Agent 发现入口,内容质量和升级边界放在同一流程中,让改动形成可检查的实际成果.

适合新建或修订 Skill,修复发现问题,迁移安装位置,查询更新及获准升级.仅阅读/解释现有 Skill,正常使用领域 Skill 或初始化普通项目不需要启动生命周期实施.

## 安装与发现

从维护者提供的分发包或现有工作区取得完整 `new-skills/`,保留 scripts,references 与 metadata.当前工作区的未发布版本应直接接入当前目录,公共下载只取已发布版本.

Codex 用户级目录为 `$HOME/.agents/skills`,Windows 为 `%USERPROFILE%\.agents\skills`.把实体目录安装为其中的 `new-skills`,或创建精确指向现有唯一实体的目录链接.先检查冲突,不覆盖未知文件或普通目录,不通过复制制造第二编辑源.其他 Agent 先核对自身平台发现契约.输入 `$new-skills` 调用,必要时重启刷新.参见 [Codex 官方说明](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).

已有完整目录但不能发现时,可以请求:

```text
使用 $new-skills,检查当前 Skill 的实体位置和 Codex 用户级发现入口.我授权为缺失入口创建精确目录链接,但不覆盖已有目标.核对最终指向,报告冲突与尚未完成项,不要搬迁实体或升级内容.
```

## 创建和改进示例

```text
使用 $new-skills,在当前获准目录创建 summarize-build-errors Skill,用于从我提供的编译错误中定位根因和下一步检查.不运行构建或自动修改代码.先核对近邻能力,交付入口、必要引用和用户 README,完成 Codex 与内容验收,不提交 Git.
```

真实问题驱动的修改:

```text
使用 $new-skills,修复指定 Skill 在“生成文件”请求下只给建议的问题.先保留当前工作区版本和已有用户改动,固定正常用例与只读负例.实施最小修复,用相同输入验证实际交付和授权边界;出现退步时只恢复本轮相关改动.达标后停止,不要全库优化或自动提交.
```

只读审查可以明确要求安装/配置说明或 README 正文候选;此时不写 settings,不初始化,不检查远端更新或创建发现入口.

## 设置,依赖与输出

当轮明确的物理目录和使用目录优先;已有信息足够时不强制补配置.只有需要保存默认值或缺少必要路径时,才按[设置合同](references/local-settings.md)使用同级 `settings.json`,字段仅为 `physical_root` 与 `usage_root`.两者相同时直接安装,不同才按宿主约定创建入口.参见[安全示例](settings.example.json);设置不是修改文件或链接的额外授权.

脚本基线为 CPython 3.12 / Windows x64.通用 validator 需要 PyYAML 6.0.2,精确来源,许可与 artifact hash 见[验收合同](references/validation-contract.md);其余工具按实际分支使用标准库,系统链接能力,Git 或受约束的 skills CLI.平台 initializer/validator 由目标平台提供,不假设每个宿主都自带 Codex 工具.不要求运行第三方 Skill 来改进本 Skill.

输出是实际修改的 Skill,必要 metadata/入口与验证结果.检查工具可以独立使用,在本目录运行,把目标占位路径替换为实体目录:

```text
python -X utf8 -B scripts/validate_skill.py --json <physical-skill-dir>
python -X utf8 -B scripts/check_content_style.py --json <physical-skill-dir>
```

工具只检查,不自动格式化或修复.通用校验涵盖入口,资源闭包,metadata,settings 结构和存在的 README 链接;风格检查保留代码/原文引用.平台验证与真实业务行为仍需分别完成.

## 修订与停止

固定当前工作区基线和成功标准,区分规则缺陷与输入/环境问题,完成一个可运行改动后对照真实成果.需要独立评审时匿名比较前后答卷,不让答题方看另一版答案.保留实际有效且无新增退步的修改;只涨分或更长不构成改善.恢复仅涉及本轮内容,并发归属不清时停止该段操作.达到目标,没有可检验新假设或达到用户预算后结束,不默认后台运行,无限迭代或提交代码.

README 面向使用者,SKILL.md 面向执行.项目要求的 README 应说明真实安装,调用和能力边界,但不能代替入口的运行规则或资源声明.通用工具允许无 README 的外部 Skill,本项目的分发验收要求每个实际 Skill 都有 README.

## 更新与限制

普通创建,修改和验收只使用本地规则,不检查远端版本或读取设计参考项目.只有明确要求检查已安装 Skill 更新或升级时才进入[更新合同](references/repository-updates.md);该操作会联网并写用户状态.网络不可达时保留本地版本,报告检查失败;发现更新不会自动升级.手工目录副本不因“已安装”就自动纳入公共更新管理,公共模式要求指定来源,lock 与安装基线;Git 模式拒绝脏工作区的自动覆盖.

已有 validator,风格,发现和更新工具回归,本次新增 README 链接/声明边界与风格检查回归,并做有限独立模拟对照.模拟退步处理不等于真实并发恢复验证,分数不证明持续进化,新机器及所有 Agent 的安装仍需各自验证.

## 许可与执行依据

本目录按 [Apache License 2.0](LICENSE) 分发,依赖及原始材料保留各自权利.README 面向使用者,Agent 执行依据 [SKILL.md](SKILL.md) 与必要引用,无需查阅设计参考仓库.
