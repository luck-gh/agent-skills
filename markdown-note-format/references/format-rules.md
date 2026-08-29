# Markdown format rules

将本规则只用于调用方提供的内容和已选择的 collection/scope.优先级为:调用方精确约束 > 调用方提供的既有内容与 collection 惯例 > 本文的 profile 规则.只生成候选和纯格式变更计划,不执行任何动作.

## Contents

- [内容保留](#内容保留)
- [Profile 与允许变换](#profile-与允许变换)
- [文件名与目录结构](#文件名与目录结构)
- [YAML front matter,标题与摘要](#yaml-front-matter标题与摘要)
- [Taxonomy](#taxonomy)
- [正文 Markdown](#正文-markdown)
- [中文半角标点](#中文半角标点)
- [链接,图片与资源](#链接图片与资源)
- [候选验收](#候选验收)

## 内容保留

- 保留既有有效 frontmatter,日期,taxonomy,文件名,正文,EOL,末尾换行,代码块类型,链接语义,图片引用和资源标识.
- 只改 allowed transforms 覆盖的部分.不得为了统一风格静默删除,概括,合并,重排或改写未授权内容.
- Repair,migrate 和 split 必须基于调用方提供的完整必要内容.缺少完整基文时不得用 patch,diff,省略号或推断补齐.
- Split 前建立 source-to-candidate 映射;每一段有效 source 内容必须恰好归入至少一个明确候选.有意重复的公共上下文要标明,不能靠复制掩盖遗漏.
- 对不确定的 renderer 行为,metadata 语义或资源状态保留原值并报告缺口,不要通过读取真实 collection 验证.

## Profile 与允许变换

- `plain-v1`:普通 Markdown.不强制 frontmatter,date,taxonomy,一级标题或 `<!--more-->`;保持调用方提供的惯例.
- `yaml-frontmatter-v1`:为调用方已选择的 collection 或显式迁移目标应用本文定义的 YAML front matter 笔记结构.
- `plain-halfwidth-zh-v1`:使用 `plain-v1`,并只对允许改变的中文 prose 应用半角标点映射.
- `yaml-frontmatter-halfwidth-zh-v1`:使用 `yaml-frontmatter-v1`,并只对允许改变的中文 prose 应用半角标点映射.
- `numbered-tree-v1`:采用两位编号和可选的统一拆分目录惯例.它可与 plain/YAML front matter 规则组合,但必须由调用方显式选择或完整定义.
- 其他 profile 只有在调用方提供完整定义和 renderer 约束时才能应用.不得从文件,模板,profile 或环境 fallback 获取定义.

Filename,structure,frontmatter,taxonomy,body 和 resource refs 分别视为独立 transform.未允许改变的部分保持原值.当某一候选必须同时改变未授权部分才成立时,报告格式阻塞.

## 文件名与目录结构

默认保持调用方提供的安全文件名和结构.若调用方显式采用编号惯例并允许 filename/structure 变换,使用:

```text
%02d_文件名.md
```

编号从 `00` 开始,按调用方提供的知识层级,阅读顺序或同层逻辑顺序分配.不得扫描目录寻找空号或自行选择参与重排的笔记.`title` 不含数字前缀.

扁平结构适用于无需拆分的同层主题:

```text
scope/
  00_知识点A.md
  01_知识点B.md
```

拆分结构适用于调用方已选择拆分的主题:

```text
scope/
  00_知识点A/
    00_概览.md
    01_子主题.md
```

将 `10 KB` 或 `3` 个以上独立子主题只作为拆分建议阈值.以内容内聚和读者理解为准,不要机械拆分.可以根据调用方提供的完整内容提出 split 候选,但是否接受拆分和哪些 source items 进入本次操作由调用方决定.

只有 `numbered-tree-v1` 明确要求同层统一结构时,才在纯格式变更计划中把同层正式知识点统一为同名子目录.不得读取同层目录发现其他文件,不得擅自扩大迁移集合.若调用方未提供完整 sibling 清单,将统一化标为未决输入.

所有机器字段中的 location/target 使用 NFC,collection-relative POSIX path.拒绝绝对路径,UNC,盘符,反斜杠,空 segment,`.`/`..`,Windows device name,尾随点/空格和 scope escape.候选 filename 只含一个安全 `.md` basename.这些路径规则不授权读取或创建目标.

## YAML front matter,标题与摘要

修复已有笔记时优先保留有效 frontmatter.只在字段缺失,格式错误,调用方允许改变或明显与已提供内容冲突时提出修复.

`yaml-frontmatter-v1` 的候选结构为:

```yaml
---
title: 文件标题
date: 2026-07-30 09:00:00 +08:00
tags: [具体标签]
categories: 知识管理
---

# 文件标题

简介内容

<!--more-->

正文内容
```

- `title` 使用不含编号前缀的文件标题.一级标题与 title 精确一致,filename 的语义保持一致.
- 保持调用方提供的有效 date.新建时只使用调用方提供且时区明确的时间;不得读取文件创建时间或使用机器当前时间.缺少该 profile 必需的 date 时报告缺口.
- `tags` 使用字符串数组.`categories` 保持调用方提供的 scalar/array 惯例;逻辑 taxonomy 输出可统一表达为 string arrays,但不得静默改变最终 frontmatter 形态.
- 简介后只放一个摘要分隔标记 `<!--more-->`;其前为摘要,其后为正文.只在 `yaml-frontmatter-v1` 及其派生 profile 中强制该标记.
- Plain profile 不得自动补齐或要求上述结构.

YAML scalar 必须在目标解析器中无歧义.对包含冒号,井号,首尾空白或类型歧义的值使用安全引号.不要执行 YAML tag,模板或嵌入命令.

## Taxonomy

- 根据调用方提供的正文,metadata 和 collection 惯例提出具体 tags/categories.不得读取或统计 collection,也不得从目录路径推断敏感属性.
- `tags` 反映具体技术,主题,项目,工具或知识点;避免 `待整理`,`其他` 等泛化占位词.
- `categories` 反映调用方已选择的大类或知识领域.目标 collection 未选定或分类惯例未知时,保留现值或报告缺口.
- 保持既有语言,大小写,去重和 scalar/array 惯例.新建议必须在 change plan 中标明是从已提供内容归纳的格式候选.

## 正文 Markdown

- 使用 ATX `#` 标题层级;列表使用 `-` 或 `1.`;代码使用 fenced code block 并保留或标注目标 renderer 支持的语言.
- 表格使用标准 Markdown pipe table;左/中/右对齐分别使用 `:---`,`:---:`,`---:`.
- 链接使用 `[文本](target)`,图片使用 `![说明](target)`.不要批量生成无需求锚点.
- 保留既有可工作的 Markdown 方言和 code fence.只有调用方明确要求迁移且 renderer 已知时才转换.
- 公式和图表按 [extended-syntax.md](extended-syntax.md) 处理.

## 中文半角标点

只有半角中文 profile 或调用方明确给出同等规则时,才在允许改变的中文 prose 中使用:

```text
。 -> .
， -> ,
、 -> ,
； -> ;
： -> :
？ -> ?
！ -> !
（） -> ()
【】 -> []
“” -> ""
‘’ -> ''
… -> ...
—— -> -
```

不要改写 fenced/indented/inline code,HTML attribute,URL,Markdown link destination,本地路径,YAML scalar 的语义值,数学公式或 renderer 指令.未选择该 profile 时保留原标点.

## 链接,图片与资源

- 保持远程 URL 原样.不得下载,跟随重定向,检查 MIME 或声称已复制资源.
- 保持调用方提供的本地资源语义和相对布局.若 profile 明确采用本 skill 的 Map 惯例,Markdown 引用使用:

```text
Markdown image target: ./Map/<当前Markdown文件名去扩展名>/图片名
```

- Machine candidate 中的 `resource_refs[].target` 使用 scope 内 collection-relative POSIX path;正文中的相对链接从候选文件位置计算.区分这两种表示,不要把 `./` 形式写入 machine target.
- 只有调用方提供稳定 resource ID,source-to-target 映射和完整候选资源名时,才能提出把绝对路径或远程资源改为 Map 引用.下载,复制,创建目录和核验目标存在性均保留给上游动作层.
- Rename/move/split 引起的链接,图片和锚点变化只写入格式 change plan.不得读取其他笔记寻找反向链接,不得声称副作用已完成.

## 候选验收

- Filename 和结构符合调用方选定的惯例,且所有相对路径保持在 caller-selected scope 内.
- YAML front matter,title,一级标题,摘要和 taxonomy 彼此一致.
- 每个 create,migrate,split 或 repair 输出都是完整候选;source-to-candidate 映射能说明所有有效内容的去向.
- 本地图片,公式和图表语法符合已知 renderer/profile,未知项明确列为缺口.
- 未允许部分与既有内容保持一致,没有静默删除或错误改写.
- Change plan 只描述拟议格式变化,不包含确认,授权,write state,执行步骤或已完成声明.
