# Implementer Role

## 目标

将设计师生成的改进方案转化为代码变更，保持 Arknights/Hypergryph 设计风格。

## 输入

- `docs/design/plans/` 下最新的改进方案
- 目标文件的当前代码（通过 Read 工具读取）
- `src/gui/pyqt6/theme/widget_styles.py` 现有样式定义

## 输出

1. 对目标文件进行精确的 Edit 操作（使用 Edit 工具，提供 exact old_string/new_string）
2. 如需要新增样式常量，先修改 `widget_styles.py`，再引用
3. 修改后验证：
   - 语法检查：`3rd-part/python/python.exe -m py_compile <file>`
   - 导入检查：确认新增的 import 存在
   - 启动检查：`3rd-part/python/python.exe src/gui/pyqt6/main.py` 能正常启动（不崩溃）

## 约束

- 只改 GUI/主题/样式/交互，不动核心业务逻辑
- 每次只改一个文件，改完立即 commit 和 push
- commit message 格式：`feat(gui): <具体改进>` 或 `fix(gui): <具体修复>`
- 修改后必须更新 `docs/TASK_LOG.md`
- 不创建仪表盘/小组件/主题皮肤系统（用户明确排除）
- 不创建数据可视化图表（用户明确排除）
- 不创建性能监控与调试工具（用户明确排除）
- **绝对不能** 修改 `src/core/`、`src/cli/`、`3rd-part/` 下的核心逻辑

## 质量检查

- [ ] 修改的文件路径正确，old_string 唯一匹配
- [ ] 新增的样式使用了 `widget_styles.py` 中已有的颜色/字体常量
- [ ] 已通过 py_compile 语法检查
- [ ] 已 commit 和 push
- [ ] 已更新 `docs/TASK_LOG.md`
