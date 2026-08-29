# Agent Skills

这是一个公开、可安装的 Agent Skills 仓库.内容由私有真源按白名单自动生成、校验并发布.

## 安装

推荐使用最新版 `skills` CLI 安装指定 Skill:

```powershell
npx skills@latest add luck-gh/agent-skills --skill new-skills
```

如需安装多个 Skill,可重复使用 `--skill`:

```powershell
npx skills@latest add luck-gh/agent-skills --skill new-skills --skill markdown-note-format
```

如需固定工具版本以获得可复现的安装结果,使用仓库当前验证过的版本:

```powershell
npx skills@1.5.21 add luck-gh/agent-skills --skill new-skills
```

建议安装 `new-skills`,以使用本仓库统一的更新检查和受保护升级流程.

## 升级

使用最新版 CLI 升级一个已安装的 Skill:

```powershell
npx skills@latest update new-skills
```

升级全部已安装的 Skills:

```powershell
npx skills@latest update
```

如需明确升级范围,使用 `-g` 只升级全局 Skills,或使用 `-p` 只升级当前项目 Skills.

## 已发布 Skills

[`skills-manifest.json`](skills-manifest.json) 是已发布 Skill 列表、文件哈希、目录哈希和当前快照 ID 的权威清单.

本仓库是自动生成的公共镜像.公开提交会在此接受审查,被采纳的变更将人工应用到私有真源,再通过标准快照发布流程同步回来.

## 许可证

本仓库使用 Apache License 2.0,详见 [`LICENSE`](LICENSE).
