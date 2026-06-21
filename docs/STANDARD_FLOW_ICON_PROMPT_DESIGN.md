# 标准流图标含义与 Prompt 设计文档

## 概述

基于 MaaEnd 流程参考和实际测试数据，完善图标含义及 VLM Prompt，保证高可靠的标准流执行。

## 图标含义定义

### 1. 导航图标 (世界页面顶部栏)

| 图标 | 坐标 (1280x720) | 坐标 (1080x1920 ADB) | 含义 | 验证状态 |
|------|----------------|---------------------|------|----------|
| **TaskIcon** | (860, 80) | (860, 80) | 任务面板入口 | ✅ 已验证 (59.9% 成功率) |
| **EventIcon** | (928, 53) | (928, 53) | 活动中心入口 | ✅ 已验证 (MID 352K) |
| **MenuIcon** | (1392, 79) | (1392, 79) | 系统菜单入口 | ✅ 已验证 (BIG 1.72M) |
| **CityMap** | (150, 150) | (150, 150) | 城市地图入口 | ✅ 已验证 (MID 88K) |
| **IndustryPanel** | (300, 80) | (300, 80) | 工业计划面板 | ✅ 已验证 (BIG) |
| **RegionBuilding** | (400, 35) | (400, 35) | 地区建设面板 | ✅ 已验证 (BIG) |
| **IndustryBrief** | (90, 120) | (90, 120) | 工业简报面板 | ✅ 已验证 (MID 85K) |

### 2. 面板内操作图标

| 图标 | 坐标 (1280x720) | 坐标 (1080x1920 ADB) | 含义 | 验证状态 |
|------|----------------|---------------------|------|----------|
| **ClaimAll** | (810, 900) | (810, 900) | 一键领取按钮 | ⚠️ 面板内通用 |
| **DailyClaim** | (975, 288) | (975, 288) | 每日任务领取 | ⚠️ 任务面板内 |
| **WeeklyTab** | (810, 300) | (810, 300) | 周常标签页 | ⚠️ 任务面板内 |
| **EventSub** | (900, 200) | (900, 200) | 活动子区域 | ⚠️ 活动面板内 |
| **MidAction** | (540, 400) | (540, 400) | 通用中部操作 | ⚠️ 面板内通用 |
| **ProductionBtn** | (540, 600) | (540, 600) | 生产队列按钮 | ⚠️ 基建内 |
| **ConfirmBtn** | (540, 690) | (540, 690) | 确认按钮 | ⚠️ 基建内 |
| **ConfirmDialog** | (810, 1035) | (810, 1035) | 弹窗确认 | ⚠️ 弹窗内 |

### 3. 菜单内入口 (待验证)

| 图标 | 坐标 (1280x720) | 坐标 (1080x1920 ADB) | 含义 | 验证状态 |
|------|----------------|---------------------|------|----------|
| **BaseEntryMenu** | (960, 400) | (960, 400) | 基建入口 | → 基于金色元素估计 |
| **CharEntryMenu** | (1200, 330) | (1200, 330) | 角色入口 | → 基于金色元素估计 |

### 4. 通用操作

| 图标 | 坐标 (1280x720) | 坐标 (1080x1920 ADB) | 含义 | 验证状态 |
|------|----------------|---------------------|------|----------|
| **BackBtn** | (90, 120) | (90, 120) | 返回按钮 | ✅ 备用 |
| **ExitCancel** | (600, 750) | (600, 750) | 退出对话框取消 | ⚠️ 估计 |

## VLM Prompt 设计

### 1. 导航确认 Prompt

```
你是明日方舟终末地游戏自动化助手。请确认当前画面中是否存在目标 UI 元素。

当前任务：{task_description}
目标元素：{target_element}
参考坐标：{reference_coords}

请分析画面并回答（仅回答 YES 或 NO）：
- YES: 画面中存在目标元素
- NO: 画面中不存在目标元素

注意：
1. 目标元素可能在画面顶部栏（y < 100）
2. 元素可能有黄色/金色高亮或图标
3. 如果画面是加载/标题/对话框，回答 NO
```

### 2. 页面验证 Prompt

```
你是明日方舟终末地游戏自动化助手。请验证当前画面是否为预期页面。

预期页面：{expected_page}
当前画面特征：
- 左侧边栏亮度：{left_bar_brightness}
- 右上角绿色像素：{green_pixels}
- 整体亮度：{full_brightness}
- 金色元素数量：{gold_contours}

请判断当前页面类型（仅回答一个词）：
- world: 探索世界/世界地图
- quest_panel: 任务面板
- event_panel: 活动面板
- menu: 系统菜单
- base: 基建页面
- character: 角色页面
- loading: 加载中
- title: 标题画面
- dialog: 对话框
- other: 其他

回答格式：{page_type}
```

### 3. 点击位置决策 Prompt（基于识别结果）

```
你是明日方舟终末地游戏自动化助手。根据识别结果决定点击位置。

当前任务：{task_description}
预期动作：{expected_action}

识别结果：
- OCR 文字：{ocr_results}
- 模板匹配：{template_results}
- 颜色匹配：{color_results}

3CUI 参考坐标（仅作为参考）：{reference_coords}

请分析识别结果，决定最佳点击位置。返回 JSON（仅返回 JSON）：
{{
    "action": "tap/back/wait/none",
    "coords": [x, y],
    "reason": "选择该坐标的原因"
}}

决策规则：
1. 如果 OCR 识别到目标文本，使用文本的 bbox center
2. 如果模板匹配成功，使用匹配结果的 bbox center（最高置信度）
3. 如果颜色匹配成功，使用第一个轮廓的 center
4. 如果所有识别都失败，使用 3CUI 参考坐标
5. 如果有多个匹配结果，选择最符合任务描述的
```

### 4. 页面状态分析 Prompt

```
你是明日方舟终末地游戏自动化助手。请分析当前页面状态。

当前页面：{current_page}
任务目标：{task_goal}

画面特征：
- 左侧边栏亮度：{left_bar_brightness}
- 右上角绿色像素：{green_pixels}
- 整体亮度：{full_brightness}
- 金色元素数量：{gold_contours}
- 黄色按钮数量：{yellow_contours}

请分析当前状态并返回 JSON（仅返回 JSON）：
{{
    "can_proceed": true/false,
    "status": "ready/pending/loading/error",
    "next_action": "tap/swipe/wait/back",
    "reason": "状态分析原因"
}}

状态判断规则：
- ready: 可以执行下一步操作
- pending: 需要等待（加载中/动画中）
- loading: 加载画面
- error: 错误状态（对话框/异常）
```

## MaaEnd 流程参考

### 1. DijiangRewards 导航模式

```
Navigation(打开面板) → StatusCheck(确认页面) → ScrollFind(滑动查找) → Claim(领取) → Back(返回)
```

**关键步骤**:
1. **Navigation**: 点击任务图标 (860, 80)，等待 4 秒
2. **StatusCheck**: 验证金色元素≥22（任务面板特征）
3. **ScrollFind**: 从 (540, 800) 滑动到 (540, 400)，持续 500ms
4. **Claim**: 点击领取按钮 (810, 900)
5. **Back**: 按返回键（keyevent 4）

### 2. BAKER 筛选模式

```
SwitchTab(切换标签) → SwipeFilter(滑动筛选) → FilterUnread(查找可领取) → Claim(领取)
```

**关键步骤**:
1. **SwitchTab**: 点击周常标签 (810, 300)
2. **SwipeFilter**: 从 (540, 900) 滑动到 (540, 500)，持续 600ms
3. **FilterUnread**: 查找可领取标识（黄色/金色）
4. **Claim**: 点击领取按钮

### 3. GrowthChamberTargetNotFound 处理

```
DetectNotFound(检测未找到) → RetrySwipe(重试滑动) → Fallback(降级方案)
```

**关键逻辑**:
- 如果滑动后未找到目标，重试 2 次
- 每次滑动幅度减小 20%
- 超过 3 次失败则降级到 VLM 分析

## 页面类型特征

### 1. 世界页面 (world)

```
- left_bar_brightness: 30-50
- green_pixels_top_right: >100
- full_brightness: 80-120
- gold_contours: 5-15
- yellow_contours: 2-5
```

### 2. 任务面板 (quest_panel)

```
- left_bar_brightness: 40-60
- green_pixels_top_right: 0-50
- full_brightness: 70-100
- gold_contours: 22-50
- yellow_contours: 10-30
```

### 3. 退出对话框 (exit_dialog)

```
- left_bar_brightness: <15
- green_pixels_top_right: 0
- full_brightness: >100
- gold_contours: 2-5
- yellow_contours: 1-2
```

### 4. 加载/标题画面 (title_loading)

```
- left_bar_brightness: >150
- green_pixels_top_right: 0
- full_brightness: >180
- gold_contours: 0-2
- yellow_contours: 0
```

## 错误恢复策略

### 1. 点击无响应

```
1. 重试点击（最多 3 次）
2. 每次间隔 2 秒
3. 如果仍无响应，重启游戏
```

### 2. 页面识别失败

```
1. 使用 VLM 分析画面
2. 根据特征判断页面类型
3. 如果仍无法判断，按返回键重试
```

### 3. 退出对话框

```
1. 检测对话框（left_bar < 15）
2. 尝试点击取消按钮
3. 如果失败，重启游戏
```

## 高可靠性保证

### 1. 多重验证

- **坐标验证**: ADB tap 后等待 3-5 秒，截图验证画面变化
- **页面验证**: 使用特征（left_bar, gold_contours）确认页面类型
- **VLM 验证**: 关键步骤使用 VLM 确认

### 2. 降级方案

- **识别失败**: 使用 3CUI 参考坐标
- **点击失败**: 重启游戏
- **页面错误**: 按返回键回到已知状态

### 3. 超时控制

- **单次操作**: 超时 10 秒
- **页面加载**: 超时 30 秒
- **完整流程**: 超时 5 分钟

## 测试验证

### 1. 坐标验证脚本

```python
# scripts/verify_menu_entries.py
# 扫描并验证所有菜单坐标
```

### 2. 页面特征采集

```python
# scripts/capture_page_profiles.py
# 采集各页面类型的特征数据
```

### 3. 端到端测试

```python
# scripts/daily_quest_fixed.py
# 完整执行每日任务流程
```

## 更新日志

- 2026-06-18: 基于实际测试数据完善图标含义和 Prompt
- 2026-06-18: 添加 MaaEnd 流程参考
- 2026-06-18: 添加页面类型特征定义
- 2026-06-18: 添加错误恢复策略
