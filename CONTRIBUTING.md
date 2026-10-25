# 参与改进

欢迎提交更清楚的模板、可复现的 bug 和小范围代码改进。请先说明：遇到的问题、系统／Python／PowerShell 版本、预期与实际结果、用虚构数据复现的最短步骤。

1. 不提交真实知识库、用户名目录、客户资料、聊天、凭据、完整日志或备份。
2. 不为了方便而关闭哈希核验、加入破坏性同步／自动删除或默认为用户接入模型。
3. 改 guard 要验证同类重入、跨类等待、超时、退出释放与日期边界；改备份要验证路径重叠、额外文件保留、源变化和恢复失败。
4. 运行 `python -m unittest discover -s tests -v` 与 `python scripts/check_public_content.py`；Windows 再跑 `pwsh -NoProfile -File tests/test_guards.ps1`。
5. 新增文件需更新 `PUBLIC_FILES.txt`。这是一份发布白名单，不自动收集任何本机文件。

本仓库不要求使用特定 AI 或扩展。提交内容应当是你有权按 MIT 授权的内容；借鉴第三方代码时保留所需署名与许可证，不把“可在 GitHub 看见”当作任意复制许可。
