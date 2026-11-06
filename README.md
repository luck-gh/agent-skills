# Agent Skills

这是一组可安装的 Agent Skills.每个 Skill 都把特定任务的操作规则,参考资料和可选脚本打包在一起,让支持 Agent Skills 的应用能够按需发现并执行对应工作流.

各版本的实质修改见 [`docs/CHANGELOG.md`](docs/CHANGELOG.md).每个 Skill 目录中的 README 提供独立的安装,示例,配置和验证边界说明;SKILL.md 及必要引用保留 Agent 执行规则,使用时不需要额外加载 README.

不知道有哪些 Skill、该怎么用?先阅读 [Skill 功能与使用示例 (`docs/SKILLS.md`)](docs/SKILLS.md),按用途选择适合当前任务的 Skill.安装后,复制对应的使用示例,把其中的占位内容替换为你的实际需求,再发给 Agent.

## 交给 Agent 安装

把下面整段提示词复制给 Agent.第一行保留 `物理目录: 默认` 时,按来源选择标准受管目录或独立 Git 目录;也可改成绝对路径,例如 `物理目录: D:\AgentSkills\agent-skills`,在该处保留完整 Git 仓库,宿主通过链接使用 Skill.

安装包含更新检查接入:使用这批 Skills 时复用缓存,默认每 24 小时最多重新联网检查一次;缓存命中不扫描 Skills,查询 Git 或输出长报告.同一会话已知未到期时连检查命令也不重复调用,手动刷新和安装变化除外.发现更新先询问,不自动覆盖;说“最近不更新,只检查”后仍检查并报告,停止升级询问,直到你要求恢复.没有运行 Agent 或没有使用这批 Skills 时不会自行定时唤醒.

```text
物理目录: 默认

请从 https://github.com/luck-gh/agent-skills 安装全部 Agent Skills,并完成可用性与自动更新检查接入.我授权创建所需目录,下载/安装指定仓库,创建必要的 Junction 或符号链接,创建 new-skills/settings.json,以及在当前 Agent 实际生效的用户级指令中新增或更新本安装专属的自动检查块.我授权安装初始化及后续按 24 小时成功缓存进行网络请求/Git fetch 和用户级更新状态写入;升级 Skill 内容仍需我的明确同意.保留其他指令和用户文件,不要覆盖既有非链接目录或未知对象,遇到冲突停止并报告.

1. 先确认当前 Agent 的官方 Skill 发现目录及用户级指令加载机制.Codex 的 usage_root 为 $HOME/.agents/skills;全局指令按实际 CODEX_HOME 下有效的 AGENTS.override.md/AGENTS.md 确定,默认 CODEX_HOME 为 $HOME/.codex.不要根据偶然存在的目录猜测,也不要写入被 override 遮蔽的文件.
2. 只把名称为 lowercase hyphen-case 且包含 SKILL.md 的顶层实体目录注册为 Skill.有 skills-manifest.json 时核对发布目录与内容哈希,没有时按实际目录核对,不补造清单.
3. 默认目录且来源为 luck-gh/agent-skills 时,使用 skills@1.5.21 CLI,明确 --global --skill "*" --agent <当前宿主ID>,不选择其他宿主.实体 physical_root 为 $HOME/.agents/skills,usage_root 按宿主确定;两者相同不建链接,不同则核对安装器创建的入口.不得把链接目录误记成实体.
4. 指定绝对路径时,完整 git clone 指定仓库到该 physical_root,保留 .git,核对 Git 根等于目标目录,origin/分支/upstream 正确.默认目录但来源不是 luck-gh/agent-skills 时,将完整 clone 放入 $HOME/agent-skill-repositories/<仓库名>,作为 physical_root.只为 Skill 创建指向唯一实体的发现入口,不复制第二份内容;Windows 用 Junction,其他系统用目录符号链接.优先使用 new-skills/scripts/ensure_skill_entry.py 的 inspect/ensure 流程.已有目录冲突时不擅自初始化或覆盖.
5. 按实体 new-skills/references/update-installation.md 完成配置,更新初始化及宿主指令接入.确认 Python 和所需依赖可用,只将已验证的 physical_root/usage_root 写入 settings.json.立即运行 manage_updates.py check --force --json,公共安装须核对真实 CLI lock 和每个已安装 Skill 的持久化基线;Git 安装须核对 upstream 和干净工作树.有阻断就报告更新接入未完成.
6. 按该引用将实际路径与解释器填入本安装的用户级指令块,保留块外内容.宿主没有可验证的用户级指令机制时不要假称支持自动触发,明确报告缺口.再次 check --automatic 应只返回简短缓存摘要和 next_check_at;新会话使用一个普通 Skill 时应实际调用检查器.当前无法新开会话时单列此项待验证.
7. 核对每个入口的准确实体与可读 SKILL.md,运行可用校验.报告实际目录,已安装 Skill,入口类型,更新模式,基线,自动检查接入与待验证项.必要时提示重启 Agent,不要仅凭安装命令成功就称自动更新流程已完成.
```

[Codex Skills 官方说明](https://developers.openai.com/codex/skills)与[全局指令规则](https://developers.openai.com/codex/guides/agents-md)分别定义发现入口和指令加载.其他 Agent 须核对自己的契约.自动接入负责触发检查,更新算法与询问规则由已安装的 new-skills 统一维护.

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

## 检查与升级

按上方提示词完成安装后,普通使用会触发带 24 小时成功缓存的检查.也可以直接告诉 Agent:

```text
使用 $new-skills,立即检查已安装 Skills 的更新,报告变化与冲突,先不要升级.
```

```text
最近不更新 Skills,只检查并报告,暂停询问是否升级.
```

```text
使用 $new-skills,升级已安装 Skills,保留本机配置并完成必要的入口交接.遇到局部修改或来源冲突先保留并报告,不要提交或推送 Git.
```

恢复升级询问时明确说“恢复 Skills 更新询问”.仅运行手动安装命令不会自动建立基线或宿主触发入口;须补完上方接入步骤.直接运行第三方 CLI 的 update 不经过本仓库的配置保留与覆盖保护,不能替代上述受保护流程.

## 发布信息

[公开发布清单](skills-manifest.json) 记录对应公开版本的 Skill 与内容哈希;它不替代当前所选仓库的安装清单.

## 贡献

欢迎提交 Issue 和 Pull Request.提交前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 许可证

本仓库使用 Apache License 2.0,详见 [`LICENSE`](LICENSE).
