# Discovery entry safety

## Purpose

只管理调用方明确给出的一个 physical skill dir 与一个 discovery entry.工具不搜索副本,不复制 skill,不删除既有 entry.

## Inspect

1. 在任何 `resolve` 或 validator 调用前,用 `lstat` 要求 physical dir 是真实目录并拒绝 symlink,Junction 和其他 reparse point.Entry parent 必须存在;目标平台声明 validator 时还要求 validator 文件存在.
2. 要求 physical dir 与 entry 使用相同的 skill 名,且两条路径不重叠.
3. 只在调用方提供 `--validator` 时对 physical skill 运行一次平台验证.
4. Entry 不存在时报告 `absent`;现有 symlink 或 Junction 解析后精确指向 physical dir 时报告 `exact`;其他状态报告冲突.

## Ensure

只有当前调用显式提供 `--authorized` 才创建 entry.创建前执行 Inspect 的直接输入检查.

- Windows 使用系统 `mklink /J` 创建 Junction.
- 非 Windows 使用 `os.symlink(..., target_is_directory=True)` 创建目录 symlink.
- 两个平台都依赖创建原语的 no-clobber 行为,不覆盖既有路径.
- 创建后只验证一次实际 target.验证失败时报告现场,不自动删除或替换路径.

这些检查覆盖输入契约,写入授权,no-clobber 和可观察输出.不要增加 staging tree,handle-bound publication,重复 quick validation 或针对未复现竞态的自定义文件系统协议.
