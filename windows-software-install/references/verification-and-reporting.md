# 验证与报告

## 验证顺序

按证据强度逐层验证,不以单一来源宣布成功.

1. **执行证据**:保存原始退出码,厂商语义,起止时间,命令和日志路径.
2. **文件证据**:确认主程序存在于目标 D 盘路径,读取文件版本,产品名,签名和架构.
3. **注册证据**:核对卸载项,包记录,服务 ImagePath,计划任务或注册组件与实际路径一致.
4. **负向路径证据**:检查 C 盘默认程序目录是否出现意外的大型主体副本;区分缓存,共享运行库和元数据.
5. **版本证据**:使用主程序文件版本,官方 CLI 版本输出或产品 About 信息确认请求的精确版本/策略.
6. **smoke test**:优先选择只读,可退出且不会创建项目,迁移配置或联网更新的厂商支持测试,例如 `--version`,诊断命令或安全启动后正常退出.
7. **健康证据**:检查日志是否存在失败,回滚,组件跳过,路径回退或待重启状态.

若 GUI 首次启动会接受许可,创建账户,下载组件,遥测联网,迁移用户数据或产生其他副作用,必须为每个动作绑定精确软件,版本,来源/可验证身份,目标,参数和当前预检并取得独立授权;安装或迁移授权不得传递.未获授权时不要代替用户完成,将 smoke test 标为待用户执行并说明步骤.

## 成功判定

仅在以下条件均满足时报告“成功”:

- 退出码被厂商定义为成功;
- 主体版本,架构和渠道符合请求;
- 主体实际位于已说明的 D 盘路径;
- 没有意外的 C 盘大型主体副本;
- 适用的 smoke test 通过;
- 没有未处理的失败或回滚日志;
- 若要求重启,状态已明确标为待重启,且不要提前报告完全成功.

信息缺失时使用“未验证”,证据冲突时使用“验证失败”,进程或重启尚未完成时使用“待完成”.不要用“看起来正常”替代状态.

## 结构化报告

使用以下结构并删除不适用字段:

`command_redacted` 只记录原本从未包含秘密的命令视图,可遮蔽非必要的个人路径或其他非秘密数据;不得用它清洗或转述含秘密的 command,shell 文本或 argv.若证据意外捕获秘密,仅保留完成诊断所需的最小脱敏证据,不要把秘密写入报告.

```yaml
status: planned | audited | success | failed | unverified | pending_reboot | blocked
mode: plan-only | read-only | authorized-implementation
operation: install | upgrade | repair
product:
  name: ""
  publisher: ""
  version_requested: ""
  version_observed: ""
  channel: ""
  architecture: ""
source:
  official_page: ""
  installer_path: ""
  signature_status: ""
  signature_publisher: ""
  hash: "algorithm:value"
execution:
  target_path: ""
  privilege: ""
  command_redacted: ""
  exit_code: ""
  exit_meaning: ""
  started_at: ""
  ended_at: ""
  log_path: ""
verification:
  path: pass | fail | not-run
  version: pass | fail | not-run
  architecture: pass | fail | not-run
  registration: pass | fail | not-run
  c_drive_duplicate: pass | fail | not-run
  smoke_test: pass | fail | not-run
  pending_reboot: false
changes:
  stopped_processes: []
  services_changed: []
  old_version: "preserved | uninstalled | not-present"
  backup_path: ""
  unavoidable_c_drive_files: []
rollback:
  available: false
  method: ""
  backup_verified: false
risks_or_gaps: []
next_action: ""
```

在面向用户的摘要中先给出状态,再给出实际版本与路径,验证结果,不可避免的 C 盘残留,日志位置,回滚可用性和下一步.不要输出许可证密钥,访问令牌或敏感日志内容.
