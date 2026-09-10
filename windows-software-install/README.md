# windows-software-install

为 Windows 大型第三方软件规划,审计并按授权实施下载,安装,升级和修复.适合 IDE,SDK,数据库,虚拟化与设备工具等可独立选择安装目录的软件,关注来源,安装位置,已有状态与真实可用性.

项目/语言依赖,普通小型 CLI,Windows Update 和解压即用的便携工具不属于本流程.它不自动决定版本,接受许可或执行系统范围变更.

## 安装与调用

从[公共仓库](https://github.com/luck-gh/agent-skills)取得完整 `windows-software-install/`.已发布下载与本地未发布内容可能不同,后者直接使用当前工作区实体目录.

Codex 用户级发现入口为 `%USERPROFILE%\.agents\skills\windows-software-install`.把完整目录安装于此,或创建精确指向唯一实体目录的链接;先核对既有目标,不覆盖或重复保存.其他 Agent 按其实际发现目录配置.调用 `$windows-software-install`,未刷新时重启 Agent.参见 [Codex 文档](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).

## 从只读规划开始

```text
使用 $windows-software-install,为当前 Windows 机器规划安装 Android Studio.先核对官方发行来源、架构、现有安装和可选目录,说明依赖与最终验证方法.本次只给具体方案,不下载、不安装、不修改设置.
```

实施用例应提供已经明确的选择和授权:

```text
使用 $windows-software-install,按刚才核验的官方版本和架构实施安装,只使用已确认的目标目录与安装器.我授权本次下载和安装,保留现有用户配置,不额外修改系统 PATH 或注册表重定向.完成后核对安装位置、版本与最小启动结果,重启未完成时如实报告.
```

该示例不替代实际软件所需的信息;存在真实冲突或需要超出本次范围时,先把具体差异说明清楚.

## 配置与依赖

输入包括软件/发行通道,目标架构,已选版本,现有状态,目标目录和授权范围.版本与下载来源在本次执行前按官方渠道核验,不把 README 中的软件示例当作推荐版本.

显式目录优先.确需默认目录时才按当前架构读取同级 `settings.json` 的 `install_x64` 或 `install_x86`,参见[安全示例](settings.example.json)与[设置规则](references/local-settings.md).目录必须是 D 盘现有绝对物理目录,盘符为可用的本地固定 NTFS 卷,不接受 reparse 或 SUBST.这反映本 Skill 当前路径合同,不是所有 Windows 软件的通用要求;环境不符合时应报告,不自行搬盘或制造 fallback.

只读[目录检查器](scripts/check_install_roots.py)使用 Python 标准库,从 stdin 校验本次需要的字段.本机基线为 CPython 3.12 / Windows x64.实际安装需要软件官方安装器及对应系统能力,不捆绑安装程序,不引入统一第三方安装框架.设置值不授权创建目录或启动安装.

## 流程,输出与常见问题

按[来源与预检](references/source-and-preflight.md)固定版本,来源,架构和安装器证据,确认已有文件与动作范围;再按[实施恢复](references/execution-and-recovery.md)执行获准动作,最后按[验证与报告](references/verification-and-reporting.md)检查实际结果.

交付实际位置,版本,安装器/进程状态,最小功能验证和剩余项.命令返回成功不等于软件可用,安装完成与等待系统重启也应分开报告.

- 不知道静默参数时不猜,先查该版本官方支持方式.
- 要管理员权限,接受协议或修改系统设置时不能仅凭路径配置推断已获授权.
- 安装结果未知时先核实实际状态,不盲目重跑或删除目录.
- 不通过命令参数或报告泄露凭据,也不自动改变已有用户配置.

已有路径检查与状态边界测试;本次核对说明与当前实现.未进行示例软件的真实安装,不保证任意安装器,版本或机器都能自动完成.

本 README 面向使用者,Agent 规则在 [SKILL.md](SKILL.md) 与必要引用.本目录按 [Apache License 2.0](https://github.com/luck-gh/agent-skills/blob/main/LICENSE) 分发;目标软件许可由其发行方决定,不因安装本 Skill 获得使用授权.
