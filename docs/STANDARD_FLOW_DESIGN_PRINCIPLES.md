# 标准流设计原则

## 一、核心原则

### 1.1 触控输入规则

**严禁**:
- ❌ `adb shell input tap x y` - ADB 触控
- ❌ `adb shell input keyevent N` - ADB 按键
- ❌ `adb shell input swipe x1 y1 x2 y2` - ADB 滑动

**仅允许**:
- ✅ `MaaFw.safe_press(x, y)` - 点击
- ✅ `MaaFw.safe_swipe(x1, y1, x2, y2, duration)` - 滑动
- ✅ `MaaFw.post_press_key(key_code)` - 按键
- ✅ `MaaFw.long_press(x, y, duration)` - 长按

### 1.2 视觉识别规则

**严禁**:
- ❌ HSV 颜色匹配（金色元素检测）
- ❌ 像素级颜色分析
- ❌ `cv2.inRange(hsv, lower_gold, upper_gold)`

**仅允许**:
- ✅ 模板匹配（TemplateMatch）
- ✅ SIFT 特征匹配
- ✅ OCR 文字识别
- ✅ 视觉特征（left_bar_brightness, green_pixels_top_right）

## 二、页面检测方案

### 2.1 使用模板匹配替代颜色匹配

**错误方案**（严禁）:
```python
# ❌ 颜色匹配检测金色元素
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
lower_gold = np.array([25, 100, 100])
upper_gold = np.array([35, 255, 255])
mask = cv2.inRange(hsv, lower_gold, upper_gold)
```

**正确方案**:
```python
# ✅ 模板匹配检测 UI 元素
ok, result = engine.recognize(img, {
    "type": "TemplateMatch",
    "template": "Common/Button/ClaimButton.png",
    "roi": [x1, y1, x2, y2],
    "threshold": 6
})
```

### 2.2 页面类型检测

**退出对话框**:
- ❌ 错误：金色元素 10-18 个
- ✅ 正确：`CancelButton` 模板匹配 + 白色背景检测

**任务面板**:
- ❌ 错误：金色元素 > 20
- ✅ 正确：`TaskIcon` 模板匹配

**世界页面**:
- ❌ 错误：金色元素 16-24 个
- ✅ 正确：`MinimapIcon` 模板匹配 + `left_bar_brightness > 100`

**主菜单**:
- ❌ 错误：金色元素 8-12 个
- ✅ 正确：`MainMenuButton` 模板匹配 + `left_bar_brightness > 200`

## 三、异常处理机制

### 3.1 退出对话框处理

```python
# ✅ 正确方案：模板匹配 + MaaFw 触控
ok, result = engine.recognize(img, {
    "type": "TemplateMatch",
    "template": "Common/Button/CancelButtonType1.png",
    "threshold": 4
})
if ok:
    maafw.safe_press(result["location"][0], result["location"][1])
```

### 3.2 游戏重启

```python
# ✅ 正确方案：ADB 仅用于应用管理
subprocess.run([
    adb_path, "-s", device_serial, "shell", 
    "monkey", "-p", "com.hypergryph.endfield", 
    "-c", "android.intent.category.LAUNCHER", "1"
])
```

### 3.3 模拟器重启

```python
# ✅ 正确方案：ADB 仅用于系统命令
subprocess.run([
    adb_path, "-s", device_serial, "reboot"
])
```

## 四、检测方案对比

| 检测目标 | 错误方案（严禁） | 正确方案（推荐） |
|---------|----------------|----------------|
| 退出对话框 | 金色元素 10-18 个 | CancelButton 模板匹配 |
| 任务面板 | 金色元素 > 20 | TaskIcon 模板匹配 |
| 领取按钮 | 金色元素 + 位置 | ClaimButton 模板匹配 |
| 世界页面 | 金色元素 16-24 个 | MinimapIcon + left_bar |
| 是否在游戏内 | 金色元素 >= 2 | UI 元素模板匹配 |

## 五、实施计划

### 5.1 第一阶段：移除颜色匹配

1. 移除 `_detect_golden()` 函数
2. 移除 `_classify_by_keywords()` 中的金色元素计数
3. 移除 `_count_gold_elements()` 函数
4. 移除 `_classify_page_by_gold()` 函数

### 5.2 第二阶段：添加模板匹配

1. 添加 `CancelButton` 模板
2. 添加 `TaskIcon` 模板
3. 添加 `ClaimButton` 模板
4. 添加 `MinimapIcon` 模板

### 5.3 第三阶段：更新页面检测

1. 更新 `_check_exit_dialog()` 使用模板匹配
2. 更新 `_check_quest_panel()` 使用模板匹配
3. 更新 `_check_world()` 使用模板匹配
4. 更新 `_check_in_game()` 使用模板匹配

## 六、验证清单

- [ ] 所有触控使用 MaaFw
- [ ] 无 ADB input 命令
- [ ] 无 HSV 颜色匹配
- [ ] 无金色元素检测
- [ ] 页面检测使用模板匹配
- [ ] 异常处理使用 MaaFw
- [ ] 游戏/模拟器重启使用 ADB（允许）
