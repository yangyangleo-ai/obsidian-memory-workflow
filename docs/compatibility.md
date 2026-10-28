# 版本、插件与验证边界

记录日期：2026-10-28。v0.2.0 主要针对 Obsidian 1.12.7、Windows 与 Python 3.11+；一键文件安装使用 Windows 自带 PowerShell 5.1，真实知识库持续写锁仍需 PowerShell 7。真实运行结果存于维护者本机，不把这些环境扩展成全平台兼容声明。不同 AI 的发现形式与理解验收见 [跨 AI 使用](ai-compatibility.md)。

| 路线 | 必需条件 | 降级方式 |
| --- | --- | --- |
| 阅读模板与交接练习 | 能读 Markdown | 普通编辑器也能读，不依赖插件 |
| 交接导出 / 摘录捕获 | Python 3.11+，标准库 | 手动选择文件 / 填来源卡 |
| 原生 Bases 表格 | 官方文档列 1.9 起；本项目只使用表格 | 直接打开 Markdown 链接 |
| Canvas 分镜 | 原生 Canvas 启用 | 用文字列出论点与镜头 |
| 官方 Web Clipper 模板 | 支持的浏览器与实际扩展版本，能导入模板 | 无扩展的本地摘录工具 |
| 原生 Bases Kanban | 官方文档列 1.14 起 | 1.12.7 不假装有新版看板，用表格即可 |

[Bases 官方版本表](https://help.obsidian.md/bases/views)、[Web Clipper 模板](https://help.obsidian.md/web-clipper/templates)。

## 插件只做可选增强

QuickAdd 能提供快速捕获入口，但不能把最新开发分支直接装进旧软件。公开版本映射显示 2.12.3 最低要求 1.11.4，2.13.0 起要求 1.13.0。最低要求匹配不是安全审计或本机功能通过；确需测试时固定版本、保留原件与来源，先用独立无敏感材料的库。

本公开仓库不捆绑第三方 main.js、插件账号或 `.obsidian` 设置，不自动安装或启用它们。插件基础功能免费不代表可选 AI、托管和外部服务免费。不要为本演练开启云 AI、脚本宏或自动推送。

来源：[QuickAdd 版本映射](https://github.com/chhoumann/quickadd/blob/master/versions.json)、[2.12.3 manifest](https://github.com/chhoumann/quickadd/blob/2.12.3/manifest.json)、[官方插件安全说明](https://help.obsidian.md/plugin-security)。

## 三种通过要分开

1. JSON / YAML / 单元测试通过：结构和受测边界成立，不说明浏览器已成功导入。
2. 本机界面导入、命令、文件读回通过：只对应这次记录的安装环境。
3. 某个 AI 理解交接包通过：必须真的在该工具上回答并人工核对，不能由脚本哈希通过代替。

CI、远端、Linux、手机、外部 AI 没有实际执行时都记未测试，不借本地候选改写历史发布验收。
