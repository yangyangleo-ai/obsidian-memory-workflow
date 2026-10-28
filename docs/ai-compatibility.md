# 不同 AI 如何使用同一份资料

核心做法是 **一个普通 Markdown 入口，多种工具入口文件，聊天场景手动交接**。
不依赖某个模型，不需要装 Skill，也不是所有服务自动打通账号或共享聊天。

## 工具入口

所有入口指向根目录 `AI_START_HERE.md`，不各自复制一份项目最新状态。

| 工具类型 | 提供的入口 | 实际使用条件 |
| --- | --- | --- |
| 支持 AGENTS.md 的编程助手，例如 Codex | `AGENTS.md` | 打开工作区根目录，有权读取文件，并实际确认加载 |
| Claude Code | `CLAUDE.md` 导入共用入口 | 项目规则未被产品／组织设置禁用；不是 Claude 聊天网页自动读本机 |
| Gemini CLI | `GEMINI.md` 导入共用入口 | 工作区受信任、上下文加载开启；不是 Gemini 网页自动读本机 |
| Cursor | `.cursor/rules/project-memory.mdc` | `alwaysApply: true` 让短规则常驻，仍需助手读取共用入口；文件提及不是自动全文导入 |
| GitHub Copilot | `.github/copilot-instructions.md` | 支持的 Copilot 场景且自定义指令已启用；不能把私人笔记提交到公开仓库求读取 |
| ChatGPT、Claude、Gemini、DeepSeek、通义、豆包等聊天产品 | `prompts/chat-handover.md` + 已审阅选定资料 | 由本人粘贴／附文件；产品上传、上下文和费用各不相同 |
| 其他能阅读文本的模型 | 共用入口或短交接提示 | 由本人显式提供，不能只给一个不可访问的本机路径 |

核查日期 2026-10-28。以上区分**官方文档支持这种文件形式**与**已经在该产品实测**：
本次分发结构／安装／静态链接有测试，不将其写成所有产品的加载和理解均已通过。
没有替使用者登录多家 AI，也不承诺未来版本、所有模型、所有语言或每次都理解一致。

## 聊天网页最简单的方式

1. 先打开 `prompts/chat-handover.md`。
2. 只为当前项目准备三类必要内容：当前状态、采用决定、未知与下一步。
3. 手动粘贴，或按 [跨 AI 交接演练](cross-ai-handover.md) 导出有界 `handover.md`。
4. 提供前自己检查隐私与服务数据条款。**上传是你的单独选择，安装器和导出器都不上传。**
5. 要求先只读回答五道题，核对通过后再下达真正的工作指令。

如果产品不支持附件，直接粘贴短的必要摘要；太长时减少范围，而不是让它假装读完。

## 五项理解验收

使用全虚构的创作者案例，合格答案见 [交接练习](cross-ai-handover.md)。检查：

1. 是否知道只是“假设已有粗剪”，没有发布或收入？
2. 是否保留原声、横屏与旧版，而非采用已被替代的 AI 旁白？
3. 是否把音乐许可保留为未知，而非以已下载推断可商用？
4. 是否只提出原主笔记上的一个下一步，而非另造待办或直接发布？
5. 是否列出三份来源和本轮边界，不虚构读过全部聊天？

答错就说明需要缩小范围或改进交接资料，不能因为文字流畅就算通过。
可把 `examples/ai-acceptance.example.json` 复制到本地 `runtime/`，由你填写产品、日期、
五项结果与实际答复出处。只有五项逐项核对后才把该次状态改为 `PASSED_THIS_EXERCISE`；
不要由脚本自动认证“所有 AI 兼容”。

## 官方资料

- AGENTS.md 开放说明：https://agents.md/
- Claude Code 项目上下文：https://code.claude.com/docs/en/memory
- Gemini CLI 上下文：https://geminicli.com/docs/cli/gemini-md/
- Cursor 规则：https://cursor.com/docs/rules
- Copilot 仓库指令：https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions

这些是上下文发现格式，不是秘密保护或权限隔离。跨工具的真正共同部分仍然是你能看懂、
能核对和维护的资料，而不是某个“万能模型记忆插件”。
