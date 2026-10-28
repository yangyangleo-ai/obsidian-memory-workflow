# 致谢与借鉴

只取适合的方法，不要求整套使用。以下来源于 2026-10-26 核对，外部项目后续可能变化。

| 来源 | 借鉴点 | 没有照搬 |
| --- | --- | --- |
| [kepano/kepano-obsidian](https://github.com/kepano/kepano-obsidian)（MIT）与[作者说明](https://stephango.com/vault) | 文件优先、少量一致属性、类别视图、资料与自己写的内容分开 | 不复制其主题、整库或个人组织偏好 |
| [Obsidian Web Clipper](https://github.com/obsidianmd/obsidian-clipper)（源码 MIT）与[kepano/clipper-templates](https://github.com/kepano/clipper-templates)（MIT） | 来源元数据与捕获／整理分层 | 不打包扩展、品牌素材或全文抓取，不启用 Interpreter／模型 |
| [obsidian-tasks-group/obsidian-tasks](https://github.com/obsidian-tasks-group/obsidian-tasks)（MIT） | 视图回到同一个源任务 | 未内置 Tasks 查询或跨视图打勾功能 |
| [Vinzent03/obsidian-git](https://github.com/Vinzent03/obsidian-git)（MIT） | 版本、可读差异和历史可恢复 | 不打包插件，不初始化／推送用户私人知识库 |
| [Obsidian Bases 文档](https://obsidian.md/help/bases/syntax) | 原生 YAML 视图语法 | 不依赖 DataviewJS，不把视图当权限隔离 |

本仓库公开文件为重新编写／通用化的模板、脚本与虚构示例；不分发上述项目源码包、图标或营销素材，也不把其功能称为我们已经实现的功能。未来若引入第三方实质代码，需要另行保留其许可证与署名。

Obsidian 及其他产品名称属于各自权利人；项目没有官方关联或背书。

2026-10-28 新增的选区模板遵循 [官方模板导入说明](https://help.obsidian.md/web-clipper/templates)、[变量](https://help.obsidian.md/web-clipper/variables) 与 [过滤器](https://help.obsidian.md/web-clipper/filters)，为本项目重新编写；没有把第三方扩展脚本捆绑进仓库。可选 QuickAdd 只在兼容性文档说明，不作为默认依赖或已通过实测的声明。

## v0.2.0 AI 入口资料

2026-10-28 对照官方公开文档整理上下文发现格式：
[AGENTS.md](https://agents.md/)、
[Claude Code](https://code.claude.com/docs/en/memory)、
[Gemini CLI](https://geminicli.com/docs/cli/gemini-md/)、
[Cursor](https://cursor.com/docs/rules)、
[GitHub Copilot](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)。
只有短入口与普通 Markdown，没有第三方插件或模型代码。文件格式有官方依据，
但本项目不声称已在每个产品、每个版本中完成真实加载或模型理解验收。
