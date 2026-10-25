# 安全操作：先在示例副本上练习

## 前提与责任

Python 3.11+，Python 工具只用标准库。作业门／写锁支持基线是 Windows + PowerShell 7；不是跨机器分布式锁，也没有可靠性承诺可替代测试。所有协作写入者必须共用同一 `LockRoot`。

这些是可组合的低层工具，不是自动化执行器。备份和安全写入脚本**不自动持有两个 guard，也无法认证调用者是否持有它们**；必须由你在同一工作流里保持 guard 会话。如果 AI 工具不能保持标准输入／后台会话，请停止，不要把“启动过脚本”当作锁仍然有效。

## 1. 准备隔离路径

下面变量均在你自己解压的仓库目录内计算。控制目录、镜像、快照和恢复目录放到仓库外；不得指向磁盘根目录、主目录或重叠目录。生产使用时改成你自己的明确路径。

```powershell
$vaultPath = (Resolve-Path '.\vault-template').Path
$parentPath = Split-Path (Get-Location).Path -Parent
$controlPath = Join-Path $parentPath 'obsidian-workflow-control'
$mirrorPath = Join-Path $parentPath 'obsidian-workflow-mirror'
New-Item -ItemType Directory -Path $controlPath -ErrorAction Stop
```

控制目录已存在时先核对用途，不用 `-Force` 掩盖路径选错。不要把真实知识库复制进这个公开 Git 仓库。

## 2. 先取得整轮作业门

在能持续存活的 PowerShell 7 会话 A 执行，所有参数按实际传入：

```powershell
pwsh -NoProfile -File scripts/vault-job-gate.ps1 -Job daily -LockRoot $controlPath -Owner 'demo-daily' -WaitTimeoutSeconds 0
```

取得 `JOB_ACQUIRED` 且进程仍活着才继续；在会话退出前，它一直持有锁。会话内变量不会自动跨终端共享，B/C 会话请重新设置同样的绝对路径。

| 事件／退出码 | 处理 |
| --- | --- |
| JOB_ALREADY_RUNNING / 73 | 同类已运行，退出 |
| JOB_BUSY / 75 | 全局作业忙且不等待，退出 |
| JOB_WAITING | 只是排队，不算已取得锁 |
| JOB_WAIT_TIMEOUT / 74 | 等待超时，记 DEFERRED_LOCK，不写库／推游标 |

每周／每月可传 `-WaitTimeoutSeconds 3600`。周期按首次 `AnchorUtc` 和 `TimeZoneId` 固定；默认 Asia/Shanghai。`-ContextOnly` 可只查看周期，不取锁。未知实际触发时间保持 null。

## 3. 写前再取得独占写锁

在持续存活的 PowerShell 7 会话 B 执行：

```powershell
pwsh -NoProfile -File scripts/vault-write-guard.ps1 -LockRoot $controlPath -Owner 'demo-daily'
```

取得 `LOCK_ACQUIRED` 后，在会话 C 做备份、写入与镜像。仍须逐文件读哈希、先备份、写前重读；guard 不阻止不合作的编辑器。

`safe_write.py` 默认只预检；加 `--apply` 才写。候选稿必须先由你审阅。新文件用 `--expected MISSING`，旧文件用实际读到的 SHA-256。内容未变返回 NO_CHANGE，不刷新日期。写入后的恢复不能自动覆盖主库。

```powershell
python scripts/safe_write.py --vault $vaultPath --relative '02-项目/示例项目/当前状态.md' --candidate 'YOUR_REVIEWED_CANDIDATE_FILE' --expected 'YOUR_READ_SHA256' --backup-root (Join-Path $controlPath 'before-write')
```

占位符不是有效路径或哈希，必须替换。该工具只能比较已发现的变化，不提供对不合作写入者的原子 CAS 保证；发现冲突时保留候选，不覆盖。

## 4. 非破坏性镜像与快照

保持两个 guard 存活：

```powershell
python scripts/vault_backup.py mirror --source $vaultPath --target $mirrorPath --receipts (Join-Path $controlPath 'receipts')
```

镜像保留目标多出的文件，不使用 MIR／PURGE 或任何删除。复制前后重新计算清单和 SHA-256；源变化、不可读、符号链接／重解析点或任何差异均失败，不签 VERIFIED。回执是机器生成的私有控制资料，不能提交到仓库。

```powershell
$snapshotPath = Join-Path $parentPath 'obsidian-workflow-snapshot-demo'
python scripts/vault_backup.py snapshot --source $vaultPath --target $snapshotPath --receipts (Join-Path $controlPath 'receipts')
```

快照目标必须不存在。成功回执给出独立 manifest 的路径和哈希；保存它，不能只信文件夹名字。

## 5. 隔离恢复

从**自己刚得到的成功回执**填入 manifest 与 SHA-256，恢复到全新测试目录：

```powershell
$restorePath = Join-Path $parentPath 'obsidian-workflow-isolated-restore-demo'
python scripts/vault_backup.py restore-check --source $snapshotPath --target $restorePath --receipts (Join-Path $controlPath 'receipts') --manifest 'YOUR_MANIFEST_FILE' --manifest-sha256 'YOUR_MANIFEST_SHA256'
```

只有清单哈希匹配、快照每文件匹配、恢复副本每文件匹配、源前后稳定才成功。测试恢复不允许覆盖生产知识库；路径保护无法识别一个用户故意填写的全新“生产路径”，仍需人工核对目标用途。

所有测试目录保留，不自动清理。真正回退生产版本需要另行选择范围、保护当前文件并审阅差异。

## 6. 最后才推进状态并释放

报告与最终字节核验完成后，才推进本任务已覆盖游标；未检查范围保持原值。库外回执记录 started / scan_until / completed、覆盖、写入、镜像与恢复，不循环在笔记里保存自身最终哈希。

先在会话 B 输入 `release` 并确认 `LOCK_RELEASED`／退出，再在 A 输入 `release`，确认 `JOB_RELEASED`／退出。崩溃后由操作系统释放句柄；`.guard` 文件保留，**不凭存在或文件年龄判断活跃，也不删除它“解锁”**。
