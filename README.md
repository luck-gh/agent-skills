# Agent Skills

这是一组可安装的 Agent Skills.每个 Skill 都把特定任务的操作规则,参考资料和可选脚本打包在一起,让支持 Agent Skills 的应用能够按需发现并执行对应工作流.

各版本的实质修改见 [`docs/CHANGELOG.md`](docs/CHANGELOG.md).每个 Skill 目录中的 README 提供独立的安装,示例,配置和验证边界说明;SKILL.md 及必要引用保留 Agent 执行规则,使用时不需要额外加载 README.

不知道有哪些 Skill、该怎么用?先阅读 [Skill 功能与使用示例 (`docs/SKILLS.md`)](docs/SKILLS.md),按用途选择适合当前任务的 Skill.安装后,复制对应的使用示例,把其中的占位内容替换为你的实际需求,再发给 Agent.

## 交给 Agent 安装

推荐把下面整段提示词复制给你的 Agent.提示词第一行是唯一需要按安装位置修改的部分:

- 保持 `物理目录：默认`:Agent 会把 Skill 实体文件直接安装到自身要求的用户级 Skill 目录.
- 需要把主体文件放到其他磁盘:只把第一行改成绝对路径,例如 `物理目录：D:\AgentSkills\agent-skills`.此时 Skill 主体文件保存在该目录,Agent 的应用目录只保留 Junction 或符号链接入口,不会在 C 盘重复保存主体文件.

```text
物理目录：默认

请从 https://github.com/luck-gh/agent-skills 安装全部 Agent Skills,并完成可用性验证.我授权你创建本次安装所需的目录,下载指定仓库,安装 Skill,创建必要的 Junction 或符号链接,以及创建 new-skills/settings.json;不要覆盖、删除或替换任何既有的非链接目录或未知文件,遇到冲突时停止并报告.

请按以下要求执行:

1. 先确认当前 Agent 实际支持的用户级 Skill 发现目录,把它作为 usage_root,不要根据偶然存在的目录猜测.如果当前 Agent 是 Codex,用户级目录使用 `$HOME/.agents/skills`;Windows 对应 `%USERPROFILE%\.agents\skills`.
2. 只把名称为 lowercase hyphen-case 且包含 SKILL.md 的顶层实体目录视为 Skill,不要安装 docs 或仓库根文件.若仓库提供 skills-manifest.json,用它核对发布目录和哈希;没有 manifest 时按实际 Skill 目录核对,不要猜测或补造清单.
3. 如果第一行是“物理目录：默认”,把 physical_root 设为 usage_root,直接使用最新版 skills CLI 将全部 Skill 安装到当前 Agent 的用户级目录.不再询问物理目录,也不创建额外链接.
4. 如果第一行给出了绝对路径,把该路径作为 physical_root.将仓库内容安装为该目录下的实体 Skill,并为每个 Skill 在 `<usage_root>/<skill-name>` 创建指向 `<physical_root>/<skill-name>` 的目录入口.Windows 使用 Junction,其他系统使用目录符号链接.优先使用仓库中 `new-skills/scripts/ensure_skill_entry.py` 的 inspect 和 ensure 流程;创建前检查冲突,不得用复制产生第二份 Skill.
5. 在实体 `new-skills` 目录内创建 settings.json,只写入已验证的 physical_root 和 usage_root 两个绝对目录.如果文件已存在且内容不同,先报告差异,不要直接覆盖.
6. 安装后核对每个入口都精确指向对应实体目录,每个 Skill 都包含 SKILL.md,并运行可用的 Skill 校验.报告实际 physical_root、usage_root、已安装 Skill、入口类型、冲突和未完成项.如果当前 Agent 没有立即发现新 Skill,提示我重启 Agent.
```

[Codex 官方文档](https://developers.openai.com/codex/skills#where-codex-loads-local-skills)支持从 `$HOME/.agents/skills` 发现用户级 Skill,并支持链接形式的 Skill 目录.其他 Agent 的目录可能不同,所以提示词要求 Agent 先按自身契约确认 `usage_root`.

## Python 环境与依赖

仅阅读 Skill 的 Markdown 不需要 Python;运行 Python 脚本、校验器或离线解析器时才需要.当前仓库统一采用 **CPython 3.12.x** 作为运行与验收基线,精确实测版本为 **3.12.4 / Windows x86-64**.这不是对所有脚本逐项证明的理论最低版本.

| Python / 平台 | 当前兼容结论 |
| --- | --- |
| CPython 3.12 / Windows x64 | 当前支持基线;3.12.4 已实测,其他 3.12 补丁版本未逐一回归. |
| CPython 3.11 | 部分代码或依赖允许,但没有仓库整体验收;绘图的非 Python 解析器环境检查不接受它. |
| CPython 3.13、3.14 及更高版本 | 未验证,不声明兼容;现有绘图解析器锁定流程也不接受这些版本. |
| Python 3.10 及更低版本 | 不作为整仓支持环境,不根据个别脚本能运行推断全部可用. |
| Linux、macOS、ARM64、PyPy、free-threaded Python | 不由 Windows x64 实测覆盖;特别是原生解析器需要匹配平台的包及独立验证. |

所以“当前兼容到哪个版本”的准确回答是:支持基线到 **3.12 系列**,本机精确验证到 **3.12.4**;不是“Python 3.11+ 均已兼容”.无需为复现旧补丁号而主动降级现有安全更新,但更换解释器后应重新验证所用分支.

### 通用依赖

仓库根的 [requirements.txt](requirements.txt) 安装通用脚本校验所需的 PyYAML,不包含大型可选解析器.它固定现有版本,不是整套传递依赖的 hash lock,也不会安装 Python 本身或改变 Agent 的 Skill 发现入口.

先确认 `python --version` 是所需的 3.12 解释器.以下 Windows PowerShell 示例在仓库根执行,新环境路径必须尚不存在;已经有隔离环境时直接使用其解释器,不要覆盖重建:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -X utf8 -B new-skills/scripts/validate_skill.py --json new-skills
```

每条成功后再执行下一条.无需激活环境或修改系统 PATH;后续脚本也必须使用同一个环境里的 Python,否则仍可能报缺包.其他系统的 venv 解释器通常位于 `.venv/bin/python`,但这不等于已获得本仓库跨平台验收.

只安装了单个 Skill、没有完整仓库时,以该 Skill 的依赖说明为准;仓库根清单是安装便利入口,不是 Skill 的运行时文件依赖.没有脚本的 Skill 不应为此强制安装全部依赖.

### 绘图解析器,按需安装

`diagram-codebase` 已有可直接交给 pip 的 TXT 锁文件,继续复用,不复制包版本到另一份总清单:

| 分支 | TXT 清单 | 包 |
| --- | --- | --- |
| Python 源码解析 | 无第三方包 | Python 标准库 ast |
| Markdown / Skill / 笔记 | [markdown-win-cp312.txt](diagram-codebase/tools/bundled/markdown-win-cp312.txt) | markdown-it-py、mdurl |
| C 源码结构 | [c-source-win-cp312.txt](diagram-codebase/tools/bundled/c-source-win-cp312.txt) | tree-sitter、tree-sitter-c |
| C 配置感知 | [c-win-cp312.txt](diagram-codebase/tools/bundled/c-win-cp312.txt) | libclang |
| 数字 Verilog / SystemVerilog | [hdl-win-cp312.txt](diagram-codebase/tools/bundled/hdl-win-cp312.txt) | pyslang |

这些 hash 锁和环境检查的已验收边界是 CPython 3.12 / Windows x64.不把 Windows hash 用于 Linux,也不通过忽略 hash 或源码编译绕过不匹配.例如只需要 C 源码结构时,在所选工具环境中执行:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: --require-hashes -r diagram-codebase/tools/bundled/c-source-win-cp312.txt
.\.venv\Scripts\python.exe -I -B diagram-codebase/scripts/check_analysis_env.py --profile c-source
```

按表替换所需 TXT 和 profile 即可,不要把无 hash 的通用清单混入同一次强制 hash 安装.已有 Skill 专属工具环境时优先复用,目录、离线包及国内镜像说明见 [按需初始化](diagram-codebase/references/initialization.md).探测通过仅证明解析器可用,不证明目标 SDK、工程语义、仿真或图文视觉正确;Verilog-A 目前没有对应可用解析依赖.

TXT 的 `-r` 语法和隔离环境方式分别采用 [pip requirements 规范](https://pip.pypa.io/en/stable/reference/requirements-file-format/) 与 [Python venv 文档](https://docs.python.org/3/library/venv.html).

## 手动安装

以下命令使用 [`skills` CLI](https://github.com/vercel-labs/skills).列出仓库内可安装的 Skill:

```powershell
npx skills@latest add luck-gh/agent-skills --list
```

安装全部 Skill:

```powershell
npx skills@latest add luck-gh/agent-skills --skill "*" --global
```

只安装指定 Skill:

```powershell
npx skills@latest add luck-gh/agent-skills --skill new-skills --skill markdown-note-format --global
```

如需固定工具版本以获得可复现的安装结果,使用仓库当前验证过的版本:

```powershell
npx skills@1.5.21 add luck-gh/agent-skills --skill new-skills --global
```

建议安装 `new-skills`,以使用本仓库统一的安装位置管理,更新检查和受保护升级流程.

## 升级

使用最新版 CLI 升级一个已安装的 Skill:

```powershell
npx skills@latest update new-skills --global
```

升级全部全局 Skill:

```powershell
npx skills@latest update --global
```

## 发布信息

[公开发布清单](skills-manifest.json) 记录对应公开版本的 Skill 与内容哈希;它不替代当前所选仓库的安装清单.

## 贡献

欢迎提交 Issue 和 Pull Request.提交前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 许可证

本仓库使用 Apache License 2.0,详见 [`LICENSE`](LICENSE).
