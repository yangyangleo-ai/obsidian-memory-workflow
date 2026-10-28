# 一键准备独立工作区

目标是让新人少配置：准备好笔记、AI 入口、交接示例与校验记录。
**不安装 Obsidian 软件，不登录 AI，不开通付费服务，不创建定时任务。**

## Windows：解压后双击 install.cmd

1. 从 GitHub Releases 下载版本 ZIP，先解压。不要在压缩包预览中运行。
2. 可先阅读 `install.ps1` 和 `scripts/install_workspace.ps1`，再双击 `install.cmd`。
3. 默认在当前用户目录下新建 `AI-Memory-Workspace`。输出
   `INSTALLED_FILES_VERIFIED` 代表文件准备及哈希读回通过。
4. 打开新目录的 `START_HERE.md`。在 Obsidian 选择“打开本地仓库”，指向其
   `vault-template`；在 AI 编程工具中打开工作区根目录。

Windows 路线使用系统自带 Windows PowerShell 5.1，无需 Python、Node、管理员权限或社区插件。
启动器的 `ExecutionPolicy Bypass` 仅作用于本次子进程，不修改机器／用户策略。
组织策略、SmartScreen 或安全软件仍可能阻止执行；遇到限制停止，不要求你关闭安全保护。
也可以不运行脚本，直接在 Obsidian 打开解压包的示例库。

指定另一个**尚不存在**的目录：

```powershell
powershell -NoProfile -File .\install.ps1 -Target 'D:\AI-Memory-Workspace'
```

目标父目录必须已经存在。不要选择已有知识库、磁盘根、用户目录本身或 Git 仓库内部。
不读取或修改用户的全局 AI 配置、Obsidian 全局配置、账号和环境变量。

## macOS / Linux / 已有 Python 的 Windows

需要 Python 3.11+，只用标准库，不需要 pip 安装运行依赖。在解压目录执行：

```bash
python3 scripts/install_workspace.py --preview
python3 scripts/install_workspace.py
```

Windows 可以把 `python3` 换成 `python`。自定义路径：

```bash
python3 scripts/install_workspace.py --target ../my-new-workspace
```

此示例选择解压目录的同级新目录；不能把源码子目录作为安装目标。
可直接使用默认用户目录下的新工作区，避免路径混淆。
Python 实现在 Windows 有测试；macOS / Linux 原生实际运行尚未验证，不宣传全平台已验收。

## 重复安装与失败

- 已有完整安装：返回 `ALREADY_PRESENT_USER_DATA_PRESERVED`，列出自安装以来改变的文件，
  **不覆盖你的笔记，也不自动升级**。
- 已有外国目录／缺少完整回执：拒绝。换一个新的目录，不自动合并。
- 中途失败：可能留下部分新文件，但不写完整成功标记，不删除部分文件。
  保留现场，检查错误或选择新目录，不把文件夹存在当成功。
- 新版本建议装到另一个新工作区，比较后按需迁移自己的笔记；不用删除旧目录。

安装副本的 `.gitignore` 会额外忽略 `vault-template/`；源码中的模板仍需公开。
这些忽略规则不是访问控制，也不能阻止强制上传或第三方同步软件。

## 自检

新工作区根目录中（Python 3.11+）：

```bash
python scripts/doctor.py
```

`INSTALLED_FILES_UNCHANGED` 是安装清单同路径哈希一致；写了自己的笔记后出现
`USER_CHANGES_PRESERVED` 并列出变化是正常现象，退出码 3 不触发覆盖。
源目录未安装时只检查分发结构，返回 `SOURCE_STRUCTURE_READY`。
无论哪种状态，`ai_acceptance` 都先是 `NOT_TESTED`；AI 理解要另做
[五项交接检查](ai-compatibility.md)。

回执只在本机 `runtime/setup-receipt.json`，不要上传自己的运行回执、笔记或真实交接包。
哈希可发现变化，不是数字签名、安全审计或对下载来源的独立认证。
