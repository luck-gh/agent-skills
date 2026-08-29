# Generic validation contract

只在需要运行或修改 `scripts/validate_skill.py` 时读取本说明.该工具接收调用方明确提供的一个或多个 physical skill dir,输出稳定 JSON,失败时不修改输入.

## Checks

1. 要求 Skill 根目录是名称合法的 physical directory,并拒绝运行时资源目录中的 symlink,Junction 和其他 reparse point.
2. 检查 `SKILL.md` 是 strict UTF-8 regular file,frontmatter 可解析,目录名与 `name` 一致,`description` 非空且符合通用平台长度边界.
3. 解析 `agents/**/*.{yaml,yml}`.若存在 `agents/openai.yaml`,检查 `interface` 的必要字段,`default_prompt` 中的 `$skill-name` 和图标资源闭包.`icon_small` 与 `icon_large` 始终相对 Skill 根目录解析.
4. 检查 `SKILL.md` 与一级 references 中声明的本地 Markdown 目标不逃逸且存在.每个 `references/**/*.md` 和 `scripts/` 下的公开 Python 入口都必须由 `SKILL.md` 中的直接 Markdown 链接声明.`[validator](scripts/validate_skill.py)` 是声明;fenced code,inline code 和完整命令均不是声明,即使命令带参数且包含该路径.`src/` 内部模块只做物理边界和静态源码检查.
5. 若存在 `settings.example.json` 或 `settings.json`,检查 example,同级 `.gitignore` 的精确 `/settings.json` 规则,UTF-8,2 空格缩进,逐字段换行,末尾换行和 settings 的 unknown 顶层字段.
6. 对 `scripts/` 和 `src/` 下的 Python 读取源码并静态编译,不导入模块.拒绝源码字符串中显式 `_dev` 路径段或带分隔符的父目录路径段,避免兄弟 Skill 和仓库级隐藏运行时依赖.

## Non-goals

- 不运行 initializer,领域入口,领域测试,网络请求或 discovery 写操作.
- 不判断 settings 业务值,凭据可用性,外部服务状态或动作授权.
- 不判断触发语义是否完整,正文内容是否常驻必要,或引用内容是否只在条件命中后需要;这些由 `SKILL.md` 生命周期流程结合具体用例人工验收.
- 不替代目标平台 validator,语言类型检查器或领域测试.
- 不要求目标 Skill 创建 `tests/`,也不把 tests 当成运行时资源.

## Runtime dependency

Validator 使用 PyYAML 6.0.2 解析 YAML.来源为 [PyPI](https://pypi.org/project/PyYAML/6.0.2/),license 为 MIT.当前验收平台的 artifact 是 `PyYAML-6.0.2-cp312-cp312-win_amd64.whl`,SHA-256 为 `7e7401d0de89a9a855c839bc697c079a4af81cf878373abd7dc625847d25cbd8`,运行边界为 CPython 3.12,Windows x86-64.其他平台必须选择 PyPI 对应 6.0.2 artifact 并核对其哈希.不要自行实现 YAML parser.

独立分发保证 `new-skills` 自身文件和资源闭包完整,不 vendoring PyYAML.隔离副本验证使用宿主已经提供并核对为 6.0.2 的 PyYAML;这证明副本不依赖兄弟 Skill 或仓库运行时代码,不证明第三方依赖自包含.

## Output and exit codes

必须使用 `--json`.成功与契约问题都输出 `schema_version`,`status`,`checked_skills` 和 `issues`;调用输入错误另含 `error`.

- `0`: 所有 Skill 通过.
- `1`: 至少一个 Skill 存在契约问题.
- `2`: CLI 用法或 physical skill dir 输入无效.
