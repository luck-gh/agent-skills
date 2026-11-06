# Repository update contract

在宿主自动检查有结果需处理,用户查询更新/授权升级,或调整升级询问偏好时读取.本流程管理已安装软件,不研究设计参考项目.自动触发入口和首次基线按 [安装接入](update-installation.md) 建立,不能靠本文件自行唤醒 Agent.

## Check timing

- 先核对范围:安装时授权的自动检查允许请求网络/Git fetch 并写用户级状态,不修改 Skill 内容或发现入口.用户明确只读,禁止联网或禁止状态写入时跳过并说明.命令依赖有效 `settings.json`;缺失时报告接入未完成,不得为检查补造配置.源码维护和项目级 Skill 不触发此流程.
- 自动调用使用 `check --automatic --json`,默认成功结果缓存 24 小时.本会话已有相同安装的 next_check_at 且可确定未到期时直接复用,不重复调用;时间不明时由脚本判断.脚本命中缓存只核对状态,配置路径和时间,不扫描 Skill,查询 Git,联网或写状态,只输出简短摘要.到期或配置根目录变化时才完整校验并联网.网络失败不刷新成功时间,下次使用仍可尝试;同一轮不循环重试,继续当前工作并说明未能检查.
- 用户明确要求立即检查或已知安装内容改变时使用 `check --force --json`.普通 `check --json` 保留完整结果及本地身份校准;自动摘要不展开逐文件哈希.自动缓存是注明时间的历史快照,不承诺立即发现外部手改,也不作为升级安全依据;apply 始终重新检查来源,内容与本地修改.状态文件仍保存待更新与阻断详情,cached=true 不重复自动询问.
- 同批任务共享更新状态时,只指定一个检查所有者,其他执行方接收目标范围,检查时间,结果及跳过原因.只复用同一来源且范围覆盖当前目标,仍在 TTL 内,期间配置或安装状态未变的证据;需要重查时仍由该所有者串行执行.这是任务编排约定,不代表脚本提供跨独立进程锁.
- 新检查返回 notification=ask 时,先完成当前工作,简述更新和接入影响并询问是否升级;没有用户升级授权就停止在检查结果.notification=report 时只报告变化或阻断原因,不催促升级;notification=none 时不附重复提示.网络错误单独说明,不能解释为已是最新.
- 用户明确说“最近不更新”“以后只检查”或“暂停升级询问”时,运行 `preference --mode check-only --authorized --json` 保存偏好,后续到期仍检查,有结果只报告,不自动询问或升级.没有明确期限不猜天数,直到用户要求恢复询问时写回 ask.用户后来明确要求本次升级可直接按本次授权执行,无需先恢复询问偏好.单次“这次只检查”或“这次不更新”只约束当前任务,不保存长期偏好,本次只报告结果而不追问升级.偏好不是升级授权.
- 用户已明确要求升级所选现有安装时,该授权覆盖经证据确认的改名接入,配置保留与对应旧链接清理,不为这些必要步骤逐项重问.只读,禁止安装维护或仅修改源码等显式限制仍优先.若 apply 结果包含 blocked/unmanaged/retired,必须逐项交代,不能把无可执行变化当作全部升级成功.

```text
python -X utf8 -B scripts/manage_updates.py check --automatic --json
python -X utf8 -B scripts/manage_updates.py check --json
python -X utf8 -B scripts/manage_updates.py check --force --json
python -X utf8 -B scripts/manage_updates.py preference --mode check-only --authorized --json
python -X utf8 -B scripts/manage_updates.py preference --mode ask --authorized --json
python -X utf8 -B scripts/manage_updates.py apply --expected-update-id <id> --authorized --json
```

## State and credentials

更新状态不写入 Skill 或仓库.Windows 使用 `%LOCALAPPDATA%\new-skills\update-state.json`;POSIX 使用 `${XDG_STATE_HOME:-~/.local/state}/new-skills/update-state.json`.状态保存成功检查时间,安装身份,完整结果,公开快照 ID,逐 Skill 基线,失败摘要与升级询问偏好,不保存凭据.损坏状态显式报错,不能伪装首次安装.同一用户切换来源/实体目录时不能沿用另一安装的基线和缓存.

## Modes

当 `physical_root` 位于有效 Git 工作树时使用 Git 模式.`check` 执行 fetch 并比较 upstream;只有分支可 fast-forward,工作区干净,update ID 未变化且用户明确授权时,`apply` 才执行 `git pull --ff-only`.ahead,diverged,detached 或 dirty 状态都不自动修复.

非 Git 的公共安装使用 `luck-gh/agent-skills` 的 schema v1 manifest.只管理 `.agents/.skill-lock.json` 中来源精确为该仓库,skillPath 为 `<name>/SKILL.md`,并位于 canonical `~/.agents/skills` physical root 的 Skill.检查和升级均校验该路径.自选物理目录的新安装保留完整 Git 仓库,不走公共散目录更新.只更新已安装且哈希变化的 Skill;新增 Skill 只列为 available,retired Skill 只提示而不删除.

没有安装基线,本地内容偏离基线,来源不匹配或目录含链接时阻止覆盖.内容哈希排除 `settings.json`,`tools/local/`,`test-output/` 和 Python/Git 缓存,这些本机状态不构成 Skill 修改.升级前临时备份目标目录,本机 `settings.json` 和 CLI lock;通过固定的 `skills@1.5.21` 和 `--agent universal` 仅替换 canonical 实体,重复 `--skill` 更新变化项,不让安装器自动选择其他宿主.成功后恢复 settings,tools/local 和 test-output,运行 validator,核对 manifest 哈希并写入新基线;失败恢复原目录和 lock.更新包含 `new-skills` 自身时,当前流程结束后提示重启 Agent.

本机目录也须可安全备份:发现链接,reparse 或非普通资源时阻止覆盖并报告,不跟随链接复制外部内容.新包与本机目录位置冲突则失败回滚,不合并未知文件.此限制包括带符号链接的本机工具环境.未绑定实体根的旧基线不直接继承,须在内容匹配当前 manifest 时重新核验建立.

## Rename is part of installation completion

更新命令只负责其声明的内容或记录操作,Agent 负责整个安装交付.对更新中删除,新增或改路径的已安装 Skill,必须读取同一目标版本的 CHANGELOG/发布说明并核对实际目录,不能把说明中的改名要求留给用户事后发现.检查时锁定的 Git commit 或公共快照变化后重新核对,不沿用旧映射.说明缺失或关系不明确时保留旧安装并报告缺口,不凭 `retired` 与 `available` 自行配对.

已确认改名时,更新前读取 [发现入口交接](junction-safety.md),记录准确旧映射和配置.按以下安装方式实施,更新后继续交接并逐项验收:

| 安装方式 | 内容与改名处理 |
| --- | --- |
| Git 真源 + 单独 usage root | 沿用干净工作区及 ff-only 门槛更新内容;Git 不维护仓库外链接或被忽略的本机配置.新实体验收后创建/复用新入口,再移除已确认旧链接. |
| 实体就是 usage root | 直接验证新实体可发现,不创建指向自身的链接.旧路径若为实体目录,不能按链接流程删除. |
| 公共受管安装 | 同名更新用 `apply`;已确认的改名由 Agent 单独安装新名称并完成下面的公共记录收口.只含改名时 `apply` 的 `no_changes` 不代表已升级. |
| 非 Git 且不满足公共纳管条件的自选物理目录 | 不用公共 apply 绕过 root/source/lock 限制.按已授权的普通安装方式取得已核验新实体,再执行入口交接;没有可执行的安装来源或范围时报告未完成. |

普通同名更新也需确认已有入口仍指向当前实体;有效链接不重建.更新前已断链的安装依据当前事实修复,不重复成功的内容更新.完成报告分别给出内容,配置,新入口,旧入口及安装记录的结果;缺任一必需项都不能称整个升级完成.

## Public rename installation and records

仅用于来源,canonical physical root,旧安装基线和明确旧名到新名都已核对的公共安装.脚本不解析发布说明,不推断改名,也不自动安装所有 `available` 项.

1. 确认旧实体内容仍匹配其安装基线,并保存旧目录,本机文件与 CLI lock 的可恢复副本.新位置必须缺失,或已是相同来源且匹配当前 manifest 的已验收新安装;冲突时停止,不能覆盖已有内容.检查新配置契约,不能把备份本身视为完成了配置保留.
2. 新名称缺失时复用已采用的安装器,只安装确认的目标: `npx skills@1.5.21 add luck-gh/agent-skills -g -y --agent universal --skill <new-name>`;Windows 使用 `npx.cmd`.安装器失败或返回不明时先核查内容和 lock,保留旧安装,不得继续删除旧项或重复执行.不因安装器选择了其他宿主就授权额外的发现入口变更.
3. 验证新实体的名称,资源和目标平台要求,CLI lock 的精确来源,以及内容哈希等于检查时 manifest.按新契约保留兼容的旧 settings 和必要本机文件,与新文件冲突时停止;不能假定安装器会跨名称转移.恢复后的内容重新核对,再运行 `check --force --json` 建立新名基线.快照变化时重新核对改名关系和新产物,不使用混合版本证据.
4. 按入口交接流程完成所有本次已纳管入口的核对.若旧实体位于发现目录,清理它属于实体操作,需要当前授权明确覆盖旧安装替换且所有本机文件已保全.准确限定旧实体,不跟随目录内的链接;有未处理的用户文件,局部修改或未知对象时保留并报告未完成,不能为消除 `retired` 提示而删数据.链接安装只清理链接,不扩展为实体删除.
5. 确认旧实体路径已不存在,新名的来源,内容及基线均正确后,调用下面的 `retire`.它仅清除该旧名的 CLI lock 条目和安装基线,不删除目录或链接.命令核对当前快照,旧名已退役,新名已纳管及本地状态;缺授权,旧路径仍在,来源/哈希冲突或状态不明时拒绝.失败不称完成,先核查记录状态;不能直接把旧基线的 hash 改名冒充新基线.新旧目录已交接但旧记录未收口时仍报告该缺口.

```text
python -X utf8 -B scripts/manage_updates.py retire --old-skill <old-name> --replacement-skill <new-name> --expected-update-id <snapshot-id> --authorized --json
```

若新内容验收失败,保留旧入口与其本地文件,只恢复已证实由本轮改变且没有并发冲突的内容和 lock.不得自动回滚整个 Git 仓库,复制旧源码到新名称冒充成功,或覆盖其他安装的并发变化.更新状态和安装器记录只是证据,不能替代从真实发现入口读取新 Skill 的验证.
