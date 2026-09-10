# diagram-codebase

把代码或文档中的真实结构整理成可编辑 draw.io 速览与可独立阅读的 Markdown 详解.先用离线工具提取关系,再由 Agent 解释和绘制,避免仅凭目录名猜架构.

适合 Python,嵌入式 C,数字 HDL,Skill 条件路由与 Markdown 笔记关系的架构分析和局部更新.只解释函数,修改实现,统计关键词或绘制装饰插画不属于本 Skill.

## 安装与发现

从[公共仓库](https://github.com/luck-gh/agent-skills)取得完整 `diagram-codebase/`,包括脚本,src,引用和随包工具清单.公共下载为已发布内容;当前未发布版本可直接接入工作区实体目录.

Codex 使用 `$HOME/.agents/skills/diagram-codebase`,Windows 为 `%USERPROFILE%\.agents\skills\diagram-codebase`.可放入完整实体目录或创建指向唯一实体目录的链接,先检查冲突,不覆盖已有目录.其他 Agent 按其发现契约配置.调用 `$diagram-codebase`,必要时重启刷新.参见 [Codex 文档](https://developers.openai.com/codex/skills#where-codex-loads-local-skills).

## 最小用例

在一个 Python 项目工作区中发送:

```text
使用 $diagram-codebase,分析当前 Python 项目的模块依赖和入口流程.先离线扫描,再生成默认的 draw.io 速览和 Markdown 详解,说明静态分析无法确认的动态调用.不要运行项目程序或查询 Git 历史.
```

进阶用例:

```text
使用 $diagram-codebase,按当前 C 固件已有的构建配置分析所选板型,采用 configured 模式.先复用并核对实际编译参数,只更新 docs/architecture/overview.drawio 和 overview.md 中受影响的中断与 DMA 关系,保留手调布局.关键配置缺失时报告,不要猜宏定义.
```

也可要求只输出一种格式.无文件的系统描述会标记为用户设计,不会被当成已扫描的实现.

## 环境与输入

输入包括目标根目录,范围,所需关系,已有成果及可选输出位置.无需 Git 仓库.默认 source 模式不探测 SDK 或消费构建配置;configured 才要求目标构建变体的真实参数.

Python 脚本基线为 CPython 3.12 / Windows x64.Python 源码使用标准库 ast;其他分支按需使用下列现有清单,不要把所有解析器作为每次画图的前提:

| 分支 | 依赖入口 |
| --- | --- |
| Markdown/Skill/笔记 | [Markdown 锁文件](tools/bundled/markdown-win-cp312.txt) |
| C source | [Tree-sitter 锁文件](tools/bundled/c-source-win-cp312.txt) |
| C configured | [libclang 锁文件](tools/bundled/c-win-cp312.txt) |
| 数字 Verilog/SystemVerilog | [pyslang 锁文件](tools/bundled/hdl-win-cp312.txt) |

环境检查和获准后的按需安装见[初始化](references/initialization.md).本机环境通常位于本目录被忽略的 `tools/local/`;普通绘图请求不自动授权下载和安装.没有必要的解析器时停止并报告,不退回全量读码.不需要 Node,服务器或浏览器自动化.其他平台的原生包与版本需要独立验证.

## 工作流程与成果

inventory 清点后必须 scan,再 query/context 定向读取证据,生成两份候选并核验.默认输出到目标项目的 `docs/architecture/overview.drawio` 和 `overview.md`,自定义位置优先;更新已有成果沿用其路径.必要的配置按需保存为同目录 `analysis-config.json`,过程文件限 `_work/<主文件名>/`,内部索引保留在工具环境.详见[离线流程](references/offline-analysis.md)和[分析配置](references/analysis-configuration.md).

覆盖既有成果前保留可恢复副本,不修改无关手调内容.输出报告区分扫描事实,推断,结构检查,语义核对和实际视觉复核.最终图文可独立于过程目录阅读.

## 限制与验证

source 模式不能证明宏条件真值或目标 ABI;Python 动态分派可能未知;数字 HDL 只提供语法结构,不等于 elaboration.Verilog-A 尚未接入.扫描失败不静默换模式,也不运行用户程序,烧录或上传源码.

已有离线扫描与图文结构回归,不同本机环境互补覆盖 C 和 Markdown,部分原生解析器测试可能缺包跳过.最新完整图文流程,真实视觉效果与整体耗时仍需实际任务验证;结构 PASS 不代表画面可读或架构语义正确.详见[验收要求](references/acceptance.md).

本 README 是用户说明,Agent 的执行合同在 [SKILL.md](SKILL.md).本目录采用 [Apache License 2.0](https://github.com/luck-gh/agent-skills/blob/main/LICENSE);上述第三方解析器沿用各自许可,来源和固定版本见随包锁文件及初始化说明.
