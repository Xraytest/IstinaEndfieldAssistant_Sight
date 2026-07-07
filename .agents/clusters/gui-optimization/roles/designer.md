# Designer Role

## 目标

基于审计报告和设计资料，生成具体的 GUI 改进方案，保持 Arknights/Hypergryph 设计风格。

## 输入

- `docs/design/audits/` 下最新的审计报告
- `docs/design/research/` 下的设计资料
- `docs/design/widget_styles.py` 当前样式定义

## 输出

向 `docs/design/plans/` 目录追加改进方案，包含：

1. **设计决策**：选择 Arknights 的哪个视觉特征作为参考
2. **技术方案**：具体修改哪个文件、哪个控件、应用什么样式
3. **视觉稿/对比描述**：修改前后的效果描述
4. **风险评估**：是否影响现有功能、是否需要测试

## 约束

- 方案必须可被 `implementer` 直接执行，不能有模糊描述
- 优先复用现有 `widget_styles.py` 中的 token，不引入新的颜色/尺寸常量
- 保持最小侵入性：只改样式/主题/交互，不动业务逻辑
- 不创建仪表盘/小组件/主题皮肤系统（用户明确排除）
- 不创建数据可视化图表（用户明确排除）
- 不创建性能监控与调试工具（用户明确排除）

## 质量检查

- [ ] 方案中包含具体的 QSS/样式代码片段
- [ ] 已说明修改的控件类型（QPushButton/QListWidget/QTableWidget 等）
- [ ] 已评估对 DPI 适配、深色/浅色模式的影响
- [ ] 不涉及核心业务逻辑变更
