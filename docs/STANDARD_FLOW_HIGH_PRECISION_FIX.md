# 标准流高精度判定修复报告

生成时间：2026-06-12

## 问题诊断

### 1. 核心问题：页面状态判断不准确

**现象**：
```
诊断脚本输出:
  [初始] 金色元素=13  (按返回后金色=3)
  点击 (860, 80) 后：金色 13→14, diff=187,692
```

**分析**：
- 金色 13 应该在 `exit_dialog` 范围 (12-16)
- 但按返回后金色变成 3，说明不是正常的退出对话框
- 点击任务图标后金色只增加 1，说明没有打开面板

**根本原因**：
1. **游戏状态异常**：可能处于加载中间状态或特殊 UI 层
2. **金色元素检测阈值需要调整**：当前范围可能不准确
3. **缺少状态恢复机制**：无法从异常状态回到世界页面

---

### 2. 坐标系统问题

**已知信息**（来自 flows_config.json）：
```
_quest_icon_note: "✓ ADB tap 扫描最佳 (860,80) 59.9% — 棋盘格：y=40/60/80 有效，y=50/70 无效"
```

**问题**：
- 之前的"59.9%"是什么指标？需要确认
- 棋盘格现象说明 UI 有透明条纹，需要精确到像素
- 当前坐标可能受分辨率/缩放影响

---

### 3. 验证方法缺陷

**之前错误判断的原因**：
1. 只检查代码是否存在，未实际运行测试
2. 验证脚本逻辑不完善（未处理 exit_dialog 状态）
3. 阈值设置不合理（静态差异阈值过低）

---

## 修复方案

### 方案 A：增强状态检测（推荐）

#### 1.1 扩展页面分类逻辑

在 `standard_flow_engine.py` 的 `_classify_by_keywords` 方法中添加：

```python
# 异常状态检测
if len(golden_elements) < 10 and "person" not in yolo_classes:
    return "unknown_low_ui"  # UI 元素过少，可能处于异常状态
```

#### 1.2 添加状态恢复机制

在 `_verify_tap_result` 方法中添加：

```python
# 异常状态恢复
if page in ("unknown", "unknown_low_ui"):
    print(f"  [恢复] 检测到异常状态 ({page})，尝试恢复...")
    # 多次按返回回到已知状态
    for i in range(10):
        self.adb.back()
        self.adb.wait(0.5)
        p, _, _ = self._analyze_page()
        if p in ("world", "exit_dialog", "title"):
            print(f"  [恢复] 已回到 {p}")
            break
    else:
        print("  [恢复] 无法恢复到已知状态")
        return False
```

#### 1.3 调整金色元素阈值

基于实际测试数据调整：

```python
# 退出对话框：12-16 个金色元素 → 扩展为 10-18
if 10 <= len(golden_elements) <= 18 and "person" not in yolo_classes:
    return "exit_dialog"

# 世界页面：18-22 个金色元素 → 扩展为 16-24
if 16 <= len(golden_elements) <= 24 and "person" not in yolo_classes:
    return "world"
```

---

### 方案 B：基于模板匹配的精确检测（长期）

参考 MaaEnd 的实现：

#### 2.1 添加模板匹配功能

```python
def template_match(img, template_path, threshold=0.85):
    """模板匹配"""
    import cv2
    template = cv2.imread(template_path)
    if template is None:
        return None
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        return max_loc, max_val
    return None
```

#### 2.2 采集关键 UI 模板

需要采集的模板：
- `assets/templates/quest_icon.png` - 任务图标
- `assets/templates/event_icon.png` - 活动图标
- `assets/templates/menu_icon.png` - 菜单图标
- `assets/templates/cancel_button.png` - 取消按钮

#### 2.3 使用模板匹配验证页面

```python
def verify_quest_panel_open(img):
    """验证任务面板是否打开"""
    # 匹配任务面板特有的 UI 元素
    quest_tab = template_match(img, "assets/templates/quest_tab.png")
    return quest_tab is not None
```

---

### 方案 C：基于 ADB 窗口标题的检测（快速）

```python
def get_activity_name():
    """获取当前 Android 活动名称"""
    cmd = [ADB, '-s', SERIAL, 'shell', 'dumpsys', 'window', 'window']
    output = subprocess.run(cmd, capture_output=True, text=True).stdout
    for line in output.split('\n'):
        if 'mCurrentFocus' in line or 'mFocusedApp' in line:
            # 提取活动名称
            if '/com.hypergryph.arknightsendfield.' in line:
                return line.split('.')[-1].split()[0]
    return None
```

---

## 实施步骤

### 第 1 步：立即修复（1 小时）

1. 调整金色元素阈值范围
2. 添加异常状态检测和恢复
3. 更新验证脚本逻辑

### 第 2 步：短期改进（本周）

1. 运行坐标校准脚本，确认最佳坐标
2. 采集关键 UI 模板
3. 实现模板匹配功能

### 第 3 步：长期优化（本月）

1. 集成 PaddleOCR 提高文字识别准确性
2. 实现基于活动名称的状态检测
3. 建立完整的状态机和异常恢复机制

---

## 验证标准

### 高精度判定标准（必须全部满足）

1. **状态检测准确率**：> 95%（100 次测试中至少 95 次正确）
2. **坐标点击成功率**：> 90%（10 次点击中至少 9 次成功）
3. **异常恢复成功率**：> 80%（5 次异常中至少 4 次恢复）
4. **流程执行完成率**：> 85%（20 次完整流程中至少 17 次成功）

### 验证方法

```bash
# 1. 运行状态检测测试
python scripts/verify_standard_flow_fix.py

# 2. 运行坐标校准
python scripts/calibrate_coords.py

# 3. 运行完整流程测试
python scripts/standard_flow_engine.py --flow daily_quest --repeats 20

# 4. 生成统计报告
python scripts/generate_stats_report.py
```

---

## 结论

**之前错误判断的根本原因**：
- 仅检查代码存在性，未进行实际运行测试
- 未考虑游戏状态异常情况
- 阈值设置基于理论值，未通过实际测试验证

**修复重点**：
1. **增强状态检测**：扩展阈值范围，添加异常状态处理
2. **添加恢复机制**：从异常状态自动恢复到已知状态
3. **实际运行验证**：通过大量测试验证准确性

**下一步行动**：
1. 立即应用第 1 步修复
2. 运行验证脚本确认修复效果
3. 根据验证结果继续优化
