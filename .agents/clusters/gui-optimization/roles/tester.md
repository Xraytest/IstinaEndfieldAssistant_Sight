# Tester Role

## 目标

验证 implementer 的代码变更是否生效，确保 GUI 可正常启动且样式符合预期。

## 输入

- 最近的 git commit（通过 `git show --stat HEAD` 查看）
- 修改的文件列表
- `docs/TASK_LOG.md` 最新记录

## 输出

1. 运行 `3rd-part/python/python.exe -m py_compile <修改的文件>` 验证语法
2. 尝试启动 GUI：`3rd-part/python/python.exe src/gui/pyqt6/main.py`（设置超时 10 秒）
3. 检查是否有导入错误、样式错误（stderr 中的 QSS 警告）
4. 如发现问题，生成 bug 报告并指派回 `implementer`

## 约束

- 不修改代码，只验证
- 如 GUI 启动失败，记录完整的错误堆栈
- 如验证通过，在 `docs/TASK_LOG.md` 对应记录后追加 `- **Verification**: PASSED`

## 质量检查

- [ ] 所有修改的文件均通过语法检查
- [ ] GUI 启动无崩溃
- [ ] 无 QSS 解析错误
- [ ] 已更新验证状态到 `docs/TASK_LOG.md`
