---
name: fixture-router
description: >-
  用于软件或固件的文档绘图.
  不用于仅解释函数或修改实现.
---

# 文档绘图入口

- 如果任务涉及固件,读取 [固件](references/firmware.md);否则读取 [软件](references/software.md).
- 当需要导出时,加载 [交付](references/export.md).
- 若只需解释,不读取 [交付](references/export.md).
- 普通背景参考 [说明](references/guide.md).

下面的代码只是示例,不能成为实际文档关系:

```markdown
如果条件成立,读取 [不存在的示例](fake-example.md).
```
