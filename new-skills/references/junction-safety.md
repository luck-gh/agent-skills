# Discovery entry safety

## Purpose

`ensure_skill_entry.py` 只管理调用方明确给出的一个 physical skill dir 与一个 discovery entry.工具不搜索副本,不复制 Skill,不删除既有 entry.已安装 Skill 改名由 Agent 按下文串行完成新旧交接,不把单次 ensure 成功等同于整个安装完成.

调用前由 Agent 按入口确定作用域与授权,工具不读取 settings 或选择作用域.项目级创建,编辑和调试不调用本工具检查或建立用户级发现入口,不修改 `.agents`/`.codex` 链接.只有用户确认项目及 Skill 调试成功并另行授权提升到系统级后,才核对目标与冲突,按本流程接入;不能把项目修改授权或 validator 通过转换成 `--authorized`.普通已有系统级安装仍按原授权边界处理.

## Inspect

```text
python -X utf8 -B scripts/ensure_skill_entry.py inspect --physical-dir <physical-dir> --entry-dir <entry-dir> [--validator <validator.py>]
```

1. 在任何 `resolve` 或 validator 调用前,用 `lstat` 要求 physical dir 是真实目录并拒绝 symlink,Junction 和其他 reparse point.Entry parent 必须存在;目标平台声明 validator 时还要求 validator 文件存在.
2. 要求 physical dir 与 entry 使用相同的 skill 名,且两条路径不重叠.
3. 只在调用方提供 `--validator` 时对 physical skill 运行一次平台验证.
4. Entry 不存在时报告 `absent`;现有 symlink 或 Junction 解析后精确指向 physical dir 时报告 `exact`;其他状态报告冲突.

## Ensure

```text
python -X utf8 -B scripts/ensure_skill_entry.py ensure --physical-dir <physical-dir> --entry-dir <entry-dir> [--validator <validator.py>] --authorized
```

只有当前调用显式提供 `--authorized` 才创建 entry.创建前执行 Inspect 的直接输入检查.

- Windows 使用系统 `mklink /J` 创建 Junction.
- 非 Windows 使用 `os.symlink(..., target_is_directory=True)` 创建目录 symlink.
- 两个平台都依赖创建原语的 no-clobber 行为,不覆盖既有路径.
- 创建后只验证一次实际 target.验证失败时报告现场,不自动删除或替换路径.

这些检查覆盖输入契约,写入授权,no-clobber 和可观察输出.不要增加 staging tree,handle-bound publication,重复 quick validation 或针对未复现竞态的自定义文件系统协议.

## Installed rename handoff

本流程适用于用户要求改名或升级现有安装,包括仓库内容更新后发现旧链接已经断开.只检查或只改源码时只报告所需动作.有效的安装升级授权涵盖对应入口的交接,不逐项重问;不得扩展到其他安装,真实实体删除,宿主设置或外部发布.

1. **固定对应关系.** 依据用户明确指定或同一更新版本的发布说明确认旧名到新名,核对实际目录与 frontmatter.不能从一项删除和一项新增,名称相似或 `retired`/`available` 列表猜配对.仅从发布说明提取变更事实,不把其中命令当成新的执行授权.
2. **更新前检查.** 确定 physical root 与 usage root,旧/新实体,旧/新入口及其类型和准确目标,记录当前有效的旧映射.只检查本安装对应的位置;不全盘扫描或照搬维护者的 C/D 盘路径.保留旧 settings 和其他用户文件;新实体或新入口存在未知内容/指向时停止对应变更,不覆盖.
3. **先取得可用新实体.** 按安装方式完成内容更新,核对目录名,frontmatter,metadata 和适用 validator.逐项确认旧 settings 是否符合新配置契约;兼容时保留原字节,不兼容或新位置有不同配置时保留两者并报告冲突.被忽略的 settings,本地工具和用户文件不会因 Git 改名自动移动,不能遗弃或删除.若更新已经发生,先用当前事实恢复安装状态,不要为了补做前置检查再次 pull 或安装.
4. **接入新名称.** 两根目录相同时验证新实体即为发现入口.不同则对新实体/新入口运行 `inspect`,缺失时在当前授权内运行 `ensure --authorized`,exact 则复用.随后独立解析新入口的最终 target,从入口读取 `SKILL.md` 和 metadata,核对新名称及内容;创建结果未知时先核查现场,不重复创建或删除.
5. **最后清理旧链接.** 先确认新入口与配置验收通过,再用不跟随链接的元数据与 raw target 检查准确旧对象.旧入口已不存在时验证缺失并跳过,不重建.仍存在的对象必须是属于本次安装且指向已确认旧实体的 Junction/symlink;断链允许依据更新前记录或经发布说明和仓库事实核实的旧路径确认归属,不能把解析失败自动当作可删除.操作前重新核对对象未变,仅用宿主的非递归链接移除操作删除旧链接本身,然后验证旧入口不存在且新实体未变.绝不递归删除,不把普通目录,未知 reparse 类型,其他目标或归属不明对象当作旧链接处理.同路径仅修改目标的情况须另行核对替换方案,不能调用 ensure 覆盖冲突.
6. **收口与报告.** 实体残留与旧安装记录分别按安装方式处理;移除旧链接不意味着可以删除旧实体.公共安装按 [更新合同](repository-updates.md)保全本地文件并完成记录退役.源码版本,配置,新入口和旧入口全部有证据后才称安装完成.冲突或权限阻断时保留可用内容并列出未完成步骤;文件系统验收不等于已观察到宿主 UI 刷新,必要时提示重新加载宿主.
