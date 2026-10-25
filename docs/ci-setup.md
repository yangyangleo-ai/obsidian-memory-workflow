# 可选 CI：首版默认未启用

本地验证与远端 CI 是不同的验收。v0.1.0 已在 Windows 本地执行 Python 测试与 guard 断言；未启用 GitHub Actions，也不声称 Linux／远端运行通过。

配置示例是 [ci.workflow.example.yml](ci.workflow.example.yml)，固定了经核对的官方 Actions commit，最小 contents:read 权限，不使用私人数据、模型或账户秘密。Python 测试规划在 Windows／Ubuntu 运行，guard 测试仅在 Windows 运行；这只是待执行配置，不是结果证明。

如果维护者希望启用：

1. 先确认使用的 GitHub 身份有创建／修改工作流的权限；不要把 token 提交到文件，也不要为了安装模板让助手自动扩大授权。
2. 在自己的仓库中创建 `.github/workflows`，把本示例复制为 `.github/workflows/ci.yml`。
3. 将新增路径加入 `PUBLIC_FILES.txt`，再运行本地测试与内容检查。
4. 自行提交并推送，读回实际 workflow run 的平台、结论和对应 commit 后，再宣称远端测试通过。

需要的命令都应在确认属于自己的仓库后执行。启用 CI 是可选项，不影响手动使用模板或运行本地测试。GitHub 的托管运行器和第三方服务遵循各自计划／额度，本项目不创建付费或自托管运行器。
