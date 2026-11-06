# Installation and automatic check integration

系统级新安装或用户明确要求为现有安装接入自动检查时读取.安装须同时交付实体,发现入口,配置,更新基线和宿主触发入口.普通源码修订不改当前机器的全局指令,也不自动安装本轮未发布内容.

## Physical installation

- 默认公共安装使用已验证的 `skills@1.5.21 add <repository> --skill "*" --global --agent <agent-id>`.先核对当前宿主的 CLI agent ID 和发现目录,不选择其他宿主.实体位于 `~/.agents/skills`,usage root 按宿主确定;Codex 两者相同,其他宿主可能通过链接发现.安装后从真实路径核对,不能把链接入口当成实体.公共受管模式只接受来源为 `luck-gh/agent-skills` 的 version 3 CLI lock,其中 `skillPath` 为 `<name>/SKILL.md`.
- 用户指定其他 physical root,或来源不是上述公共仓库时,在该准确目录完整 clone 指定仓库,保留 `.git`,核对 Git 根精确等于 physical root,origin,当前分支和 upstream.不要下载 ZIP 或复制成无法更新的散目录.目标已有内容时检查归属,不覆盖或擅自初始化 Git.只为顶层实际 Skill 创建发现链接,不把根文档或 docs 注册为 Skill.更新复用 Git fast-forward 流程.
- 使用 [入口交接](junction-safety.md) 的冲突检查与授权边界.配置仅保存已验证的 physical_root 和 usage_root;两者相同不创建自链接.按 [设置合同](local-settings.md) 保留既有配置,不要把更新偏好塞入 settings.
- 确认 Python 与脚本可运行,公共安装升级时还需可用的 Node/npm,Git 和 validator 的已声明依赖.固定实际解释器路径,避免未来由不同 PATH 选择解释器.

## Initialize and verify

安装授权包含本轮更新初始化时,运行实体目录中的 `scripts/manage_updates.py check --force --json`.公共模式必须为本轮安装的每个 Skill 核对来源,manifest 哈希与持久化 baseline;结果不得包含这些 Skill 的 blocked/unmanaged/retired.仅“命令退出码为 0”或 `no_changes` 不足以验收.若安装期间远端版本变化而无法建立基线,报告安装更新接入未完成,不得伪造基线或删除覆盖保护.

Git 模式核对正确的 upstream 和干净工作树.被忽略的 settings 保留,配置文件不得使仓库持续 dirty.非 Git 自选目录报告不支持该更新方式,不要伪装为公共受管安装.

## Host instruction entry

只有宿主实际加载的指令才能触发检查.单独安装 `new-skills` 或只修改它的 description 不足以让普通 Skill 使用触发更新.将下面短块接入当前宿主的用户级指令,所有执行逻辑仍在本 Skill 中;其他 Skill 保持独立分发,无需引用兄弟目录.

安装提示词须明确授权新增/更新本安装的指令块,以及后续检查所需的网络请求/Git fetch 和用户状态写入.这不授权升级内容,也不授权覆盖其他指令.先读取目标,保留块外内容;已有同名块仅在路径与归属确认后原位更新.多个安装不能互相替换,发现归属冲突时报告.

Codex:按实际 `CODEX_HOME` 定位用户级配置,未设置时使用 `~/.codex`.按照 [官方 AGENTS.md 规则](https://developers.openai.com/codex/guides/agents-md),优先核对有效的 `AGENTS.override.md`,否则使用 `AGENTS.md`;不要把块写入被 override 遮蔽的文件,也不要为本功能新建 override.其他宿主先核验其官方用户级指令机制,不能假设它读取 AGENTS.md.没有该能力或用户不允许接入时,交付可用 Skill,但明确自动检查未接入,仍可手动调用.

以下占位符须替换为已验证的绝对路径,命令按宿主 shell 正确引用;PowerShell 调用带引号的解释器需前置 `&`.不要保留占位符或把本机路径写回分发包.

```text
<!-- new-skills:update-check:start -->
每轮首次使用实体位于 <physical_root> 的已安装 Skill 前,若本会话已有相同安装的 next_check_at 且可确定尚未到期,直接复用,不调用检查器;否则运行:
"<python_executable>" -X utf8 -B "<physical_root>/new-skills/scripts/manage_updates.py" check --automatic --json
本安装已授权此检查的网络请求/Git fetch 和用户级更新状态写入.来源由检查器按安装记录过滤,不凭 Skill 名称猜测.脚本按默认 24 小时成功缓存判断,命中只读少量本机状态并返回简短结果,不扫描 Skill 或运行 Git/网络检查;同一轮只由一个执行者检查.已知安装内容/配置改变或用户要求立即检查时,改用 check --force --json,不沿用会话结果;时间不明时不猜测缓存有效.
若 notification 不是 none 或检查失败,读取 <physical_root>/new-skills/references/repository-updates.md 并按结果处理,完成当前任务后告知用户.检查不授权升级.
源码维护,项目级 Skill 和其他安装不触发此检查;用户明确只读,禁止联网或禁止状态写入时跳过并说明.不要创建后台任务.
<!-- new-skills:update-check:end -->
```

## Acceptance

1. 从 usage entry 实际读取每个 SKILL.md,核对实体与入口,配置与来源,完成内容/平台校验.
2. 首次 `check --force` 成功且初始化证据完整;再次 `check --automatic` 返回 cached=true 与 next_check_at 的简短结果,不执行 Git,内容扫描,网络请求或状态写入.手动 `check` 仍可取得完整结果.
3. 回读宿主实际生效文件,确认只存在本安装的准确指令块,路径和解释器可用,无未知覆盖.
4. 在新会话使用一个已安装的普通 Skill,观察它在业务工作前执行检查,不能只在显式调用 new-skills 的会话验收.无法启动新会话时报告此项待验证,不声称已证明宿主加载.
5. 默认 24 小时指成功结果缓存:过期后的下一次使用会重新联网检查.宿主未运行或没有使用这批 Skills 时不会自行唤醒;这套接入不创建定时任务或后台进程.
