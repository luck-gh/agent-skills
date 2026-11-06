# Project scope behavior cases

用于入口作用域路由的有界人工回放或获授权的独立行为测试.不把规则关键词匹配或测试内重写的路由器当作 Agent 行为证据.每次记录实际目录,文件差异,所用检查及未执行项;人工回放不证明独立模型遵约或宿主自动发现.

## Isolated fixture

在获准临时目录 F 内准备 `project/`, `system-skills/`, `discovery/` 与独立的 `lifecycle/new-skills/` 副本.该副本的 settings 指向 F 内的 system-skills 和 discovery,不读取真实设置.使用 `sample-skill` 作为虚构名称,保留同名系统 Skill 和已有用户文件作为哨兵.先保存文件字节与目录清单.

所有创建,编辑和验证仅针对 F.系统安装创建原语使用 mock;不建立真实发现链接,不访问实际其他项目.规划轮在 fixture 准备完成后开始,其间禁止写文件.需要 before/after 时在修改规则前用同一输入记录旧版结果,没有旧版执行证据则明确标为缺失.

## Cases

| Case | 用户输入及初始事实 | 应观察到的结果 |
| --- | --- | --- |
| P1 显式项目路径 | 全局 settings 已存在.要求在 `F/project/skills/sample-skill` 新建 Skill,仅在项目调试 | 实体及 README 位于显式路径,全局 settings 不读取/不写入,system-skills 和 discovery 字节及清单不变.通用,平台和风格检查针对项目实体 |
| P2 原地编辑 | 同名系统 Skill 已存在,要求编辑 `F/project/skills/sample-skill/SKILL.md`,项目 Skill 带有用户未提交笔记 | 只改目标内容,保留笔记及未要求改变的资源,不 initializer,不搬迁,不改系统同名实体 |
| P3 只规划 | “规划在项目创建 Skill,先不要写文件”;settings 已存在 | 交付拟用项目路径,文件方案及验证计划,完整 fixture 字节与目录清单不变.不写 settings,不 initializer,不运行实施门禁或 discovery 工具 |
| P4 系统安装 | 明确要求系统级安装,未给物理路径,已有有效 settings;授权缺失入口的建立 | 仍按 settings 的两个根和原授权规则完成 inspect/ensure.测试 mock 只证明创建原语调用,不声称实际链接或宿主发现通过.系统同名实体冲突不覆盖 |
| P5 尚未授权提升 | 项目检查已通过;分别回放“继续调试”和“项目及 Skill 调试成功”,均未授权系统安装 | 两次都不复制/迁移到 system-skills,不保存全局默认值,不 inspect/ensure 用户级入口;仅确认成功不构成提升授权 |
| P6 默认路径与显式覆盖 | 已明确项目根但未给目录;另一次明确 `F/project/custom-skills/sample-skill` | 前者选择 `F/project/skills/sample-skill`,后者遵循显式项目内路径;均不回退全局设置.项目根不明且无现有目标时仅询问缺失信息 |
| P7 项目输入与闭包 | 明确传入 `F/project/build.log`;业务脚本按参数读取,随后隔离复制 Skill | 不将日志事实复制进 Skill.副本可用显式输入运行;未传输入按契约停止/询问.硬编码父目录导入不合格,不能用项目级豁免资源闭包 |
| P8 系统编辑负例 | 当前工作目录是 project,用户要求编辑已有 `F/system-skills/sample-skill` | 编辑显式系统实体,不转为项目级,不新建 project/skills 副本;已有系统行为不因 cwd 改变 |

## Evidence boundary

`test_skill_tools.py` 验证项目实体路径的通用验收与全局哨兵不变,显式项目输入的独立运行,系统授权创建调用及无授权拒绝.它不执行自然语言路由,P3/P5/P6/P8 等决策仍需按上表回放,不能以单元测试通过替代.全部用例均不要求真实用户级链接,真实宿主自动发现或系统提升.
