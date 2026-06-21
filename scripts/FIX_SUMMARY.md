# 标准流修复总结

## 已修复问题

### 1. 任务图标坐标更新
- **旧坐标**: (820, 40) → 触发退出对话框
- **新坐标**: (860, 80) → 扫描确认 59.9% 变化率
- **棋盘格现象**: y=40/60/80 有效，y=50/70 无效（透明条纹）

### 2. 退出对话框视觉检测
- **触发条件**: 12-16 个金色元素 + 无 person + OCR 为空/无文字
- **world 对比**: 20 个金色元素
- **作用**: VLM OCR 超时返回"无文字"时仍能识别

### 3. 前置验证阶段处理
- 添加 `exit_dialog` 页面类型处理
- 检测到退出对话框时自动按返回关闭

### 4. 页面分类增强
- 任务面板：>20 个金色元素 + 无 person
- 退出对话框：12-16 个金色元素 + 无 person + OCR 空
- 探索世界：有 person + >10 个金色元素

## 待解决问题

### 1. 按返回键后页面变化异常
- **现象**: world → 按返回 → title（而不是保持 world）
- **可能原因**: 
  - 游戏状态不稳定
  - 返回键在特定条件下触发退出
  - 模拟器状态异常

### 2. 点击 (860, 80) 后金色=0
- **现象**: 点击后画面变成空白（金色从 20 变 0）
- **可能原因**:
  - 坐标空间不匹配（ADB vs MaaFw）
  - 点击后触发加载/过渡动画
  - 画面分析时机不对

## 建议方案

### 方案 A: 移除 clear_dialog 步骤
直接删除第一步，让流程从点击任务图标开始：
```json
"steps": [
  {"id": "open_quest", "action": "tap", "coords": [860, 80], ...},
  ...
]
```

### 方案 B: 使用点击中央代替返回键
```json
"steps": [
  {"id": "clear_dialog", "action": "tap", "coords": [960, 540], "wait": 2},
  {"id": "open_quest", "action": "tap", "coords": [860, 80], ...},
  ...
]
```

### 方案 C: 增强路由恢复逻辑
在路由恢复时：
1. 检测到 exit_dialog 时直接按返回
2. 按返回后重新分析页面
3. 如果是 title 则点击中央返回 world

## 测试命令

```bash
# 测试 daily_quest 流程
python scripts\standard_flow_engine.py --flow daily_quest --local-only

# 测试所有流程
python scripts\standard_flow_engine.py --flow all --local-only

# 仅分析当前画面
python scripts\standard_flow_engine.py --flow daily_quest --local-only --analyze-only
```

## 下一步行动

1. **验证 exit_dialog 检测**: 手动触发退出对话框，检查是否能正确识别
2. **测试方案 B**: 用点击中央代替返回键清除对话框
3. **调整等待时间**: 点击后等待 5 秒再分析（给加载动画时间）
4. **检查 ADB 坐标**: 确认 (860, 80) 在 ADB input tap 中的实际位置
