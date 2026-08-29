# Capture local settings

只有 Capture 已选择 `note`,且当轮没有显式提供完整 `collections` object 时读取本说明.`memory`,`no-save` 和纯复盘不得读取 settings.

## Location and schema

从当前 `SKILL.md` 所在的 physical skill dir 读取同级 `settings.json`.不得读取环境变量来改变位置或搜索其他目录.随 skill 分发的 [settings.example.json](../settings.example.json) 只说明字段结构,不提供 collection 值.文件必须是只含 `collections` 的 JSON object.每个 collection 精确为:

```json
{
  "id": "opaque-collection-id",
  "root": "local absolute directory",
  "scope": {"include": ["root/relative/scope"], "exclude": []},
  "format_profile": "plain-v1"
}
```

- `collections` 至少 1 项,最多 64 项.
- `id` 是本机非敏感逻辑 ID,忽略大小写后唯一.
- `root` 必须是当前存在,可读,可遍历且非 symlink/reparse 的绝对目录;不得自动创建.
- `include` 至少 1 项.`include` 与 `exclude` 都使用唯一的 root-relative POSIX 目录路径,且物理目录必须已存在并留在 canonical root 内.
- `format_profile` 只允许 `plain-v1` 或 `yaml-frontmatter-v1`.
- 不允许 unknown 字段,凭据,敏感正文,运行时状态,确认,批准或动作授权.

读取成功后,把完整 object 通过 stdin 交给 `scripts/validate_collections.py --json`;只有返回 `ok` 才能作为 note 路由候选.随后每次真实 collection I/O 仍执行 `preflight_collection`.

## Missing or invalid settings

文件缺失,JSON 损坏,字段缺失,unknown 字段或路径不可用时,只询问完整 `collections` 或失效项.Example 只能用于确定字段和展示格式,不得作为 collection 或自动复制为 settings.不得搜索旧 profile,其他 skill settings,环境中的其他路径或历史副本.当轮显式 object 可以直接用于当前 note 路由,不要求先持久化.

只有用户明确要求保存,且完整真实值已通过 `validate_collections.py` 时才创建 settings.不得创建空文件,占位文件或自动从 example 初始化.从当前 `SKILL.md` 精确确定同级目标;目标不存在时原子 no-clobber 创建,已存在且逻辑内容完全相同视为幂等,内容不同则停止,不得合并或覆盖.写后重新读取并运行 `validate_collections.py`.

Settings 只描述候选 collection 边界,不授权读取笔记,搜索,建目录,写文件或 Git 操作.
