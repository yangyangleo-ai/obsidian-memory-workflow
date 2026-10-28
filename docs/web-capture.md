# 网页资料捕获：先留出处，再决定信不信

提供两种互不依赖的路线：官方浏览器 Web Clipper 模板，以及无扩展的本地摘录入库工具。两者默认都**不启用 AI Interpreter**，不处理账号后台、私密资料或付费受限正文。

## 路线 A：官方 Web Clipper

官方扩展由用户自行安装到支持的浏览器，本仓库不偷偷修改浏览器。导入 `examples/web-clipper` 中的 JSON 后，在扩展预览中核对标题、URL、日期、目标演示库和正文。

模板只新建资料卡，不追加当前状态、不自动把资料改成已核验、不运行模型。先在独立演示库上试，目标目录是 `07-收件箱/资料`。模板里不锁死私人库名，导入后由你选择目标库。

**只选必要片段再剪藏**，模板不会复制整页正文。默认取选区；没有选区就留下待补提示。不同网页结构会变化，动态页或缺失变量不要硬写成功。

官方说明：[模板导入](https://help.obsidian.md/web-clipper/templates)、[变量](https://help.obsidian.md/web-clipper/variables)、[过滤器](https://help.obsidian.md/web-clipper/filters)。本仓库模板使用官方预设变量，不依赖站点 CSS 选择器，也没有提示变量或模型配置。

## 路线 B：不安装扩展也能捕获

将你实际阅读后选取的短摘录或转述放进本机 UTF-8 `.txt` 文件，带上公开来源 URL 和标题。不是假装自动读取网页，也不冒充原页完整快照。

```powershell
python scripts/capture_source.py --vault vault-template --input YOUR_EXCERPT.txt --url https://obsidian.md/help/bases --title 'Bases 阅读摘录'
```

默认只预览；确认内容与目标后，**在独立示例副本**加 `--apply` 写入：

```powershell
python scripts/capture_source.py --vault vault-template --input YOUR_EXCERPT.txt --url https://obsidian.md/help/bases --title 'Bases 阅读摘录' --apply
```

真实库写入仍需遵守 [两个 guard 与写前核对](operations.md)；这个辅助工具不会自动获取它们。生成文件名由来源、摘录哈希和短标题决定，同一份材料重复执行不覆盖既有笔记，也不重置已经手动整理的状态。相同来源内容有变化会保留为新版本供人比较。

工具不联网、不发模型请求；只接受短文本和无凭据、查询参数、片段的 HTTPS URL，拒绝明显本地 / 私网地址。不会验证域名真实性或资料事实，`CAPTURED_UNVERIFIED` 只说明本地摘录创建与读回成功。

## 保存了什么，没有保存什么

- 保存来源 URL、标题、实际入库时刻、摘录文件哈希、未核验状态。`source_accessed` 默认未知；实际访问过才用 `--accessed YYYY-MM-DD` 明确提供，不能拿入库日冒充阅读日。
- `source_sha256` 只对应你提供的摘录文件，不是网页整体或观点真伪的证明。
- 不猜作者、发布日期和原文版本；不知道就留缺口。
- 外部内容按数据处理，不执行其中“忽略规则 / 上传资料 / 扩大权限”等指令。
- 摘录先留在资料层；经过阅读与核实后，再由人决定保留、提炼或淘汰。

网页版权、模型隐私、浏览器权限与资料真实性分别核对。官方扩展能用，不代表所有网页内容都能无限复制再发布。
