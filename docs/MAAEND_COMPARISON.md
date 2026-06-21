# MaaEnd vs IstinaAI 标准流对比分析

生成时间：2026-06-11

## 核心差异总结

| 维度 | MaaEnd | IstinaAI 当前实现 | 问题 |
|------|--------|------------------|------|
| **识别方式** | TemplateMatch + OCR + ColorMatch | 金色元素计数 + YOLO 降级 | 页面判断不可靠 |
| **按钮定位** | 模板匹配 + ROI 限制 | 硬编码坐标 | 坐标不准确 |
| **退出对话框** | `CancelButton` 模板匹配（全屏搜索） | 固定坐标 (600, 750) | 无法可靠关闭 |
| **流程结构** | 状态机（节点 + 跳转） | 线性步骤列表 | 缺乏异常处理 |
| **OCR 使用** | 关键文本识别（领取/前往/日常） | VLM OCR（仅降级用） | VLM 超时风险 |
| **错误恢复** | `[JumpBack]` 跳转机制 | 简单的 `back()` 调用 | 恢复逻辑不完善 |

---

## 1. 退出对话框处理对比

### MaaEnd 实现（common-buttons.md）

```json
{
  "name": "CancelButton",
  "desc": "通用取消按钮，有文字、白色底、X 形图标",
  "recognition": {
    "type": "TemplateMatch",
    "param": {
      "roi": [0, 0, 1920, 1080],  // 全屏搜索
      "template": ["Common/Button/CancelButton.png"],
      "threshold": 0.85
    }
  },
  "action": "Click"
}
```

**优势**：
- 使用模板匹配，不依赖固定坐标
- 全屏搜索，任何位置的取消按钮都能识别
- 支持普通态和 Hover 态模板

### IstinaAI 当前实现

```python
# standard_flow_engine.py
if page == "exit_dialog":
    self._tap(600, 750)  # 硬编码坐标
    self.adb.wait(2)
```

**问题**：
- 坐标基于估计，未经验证
- 无法适应不同分辨率或 UI 变化
- 没有验证关闭是否成功

### 修复方案

**方案 A（推荐）**：添加模板匹配支持
```python
# 1. 添加 CancelButton.png 模板到 assets/
# 2. 使用 MaaFw 或 OpenCV 模板匹配定位按钮
# 3. 点击匹配到的位置
```

**方案 B（快速）**：多坐标尝试 + 画面验证
```python
cancel_candidates = [(600, 750), (540, 720), (660, 780), (580, 730), (620, 770)]
for cx, cy in cancel_candidates:
    before = screencap()
    tap(cx, cy)
    time.sleep(1.5)
    after = screencap()
    if screen_diff(before, after) > 500000:
        # 画面变化大，说明点击有效
        break
```

---

## 2. 每日任务流程对比

### MaaEnd 流程（Tasks.json）

```
DailyTaskStart
  └─> DailyTaskInMenu (识别：InOperationalManual)
      └─> DailyTaskEnterTab (OCR 识别 "日常"/"Daily")
          └─> DailyTaskClaimSingleReward (OCR 识别 "领取"/"Claim")
          └─> DailyTaskClaimActivityRewards (ColorMatch 红色奖励图标)
          └─> DailyTaskScrollDown (滑动查看更多)
          └─> DailyTaskScrollFinished (模板匹配完成图标)
          └─> DailyTaskActivityLimitReached (OCR 识别 "活跃度已达上限")
```

**关键特性**：
1. **OCR 识别**：在 ROI 区域内识别 "日常"、"领取"、"Claim" 等文本
2. **颜色匹配**：检测红色奖励图标（HSV: 240-255, 100-130, 0-15）
3. **模板匹配**：识别完成图标、TSA 图标等
4. **滑动机制**：`DailyTaskScrollDown` 最多 50 次，直到 `DailyTaskScrollFinished`
5. **状态检查**：OCR 识别 "活跃度已达上限" 提前结束

### IstinaAI 当前实现

```json
{
  "steps": [
    {"action": "tap", "coords": [860, 80]},      // 任务图标
    {"action": "check"},                         // 检查状态（未实现）
    {"action": "tap", "coords": [975, 288]},     // 领取按钮（未验证）
    {"action": "back"}
  ]
}
```

**问题**：
1. 没有 OCR 识别，直接点击硬坐标
2. 没有滑动机制，可能遗漏任务
3. 没有状态检查，无法判断是否完成
4. 没有错误恢复，遇到对话框就卡住

### 修复方案

```json
{
  "steps": [
    {
      "id": "ensure_world",
      "action": "navigate",
      "target": "world",
      "method": "back_until",
      "verify": {
        "type": "golden_count",
        "range": [18, 21]
      }
    },
    {
      "id": "close_exit_dialog",
      "action": "find_and_click",
      "method": "template_match",
      "template": "Common/CancelButton.png",
      "roi": [0, 0, 1920, 1080],
      "optional": true
    },
    {
      "id": "open_quest_panel",
      "action": "tap",
      "coords": [860, 80],
      "wait": 3,
      "verify": {
        "type": "ocr",
        "roi": [150, 100, 1000, 100],
        "expected": ["日常", "Daily", "任务"]
      }
    },
    {
      "id": "claim_tasks_loop",
      "action": "loop",
      "max_iterations": 10,
      "steps": [
        {
          "id": "find_claim_button",
          "action": "find_and_click",
          "method": "ocr",
          "roi": [825, 200, 300, 400],
          "expected": ["领取", "Claim", "受取"],
          "optional": true
        },
        {
          "id": "check_finished",
          "action": "check",
          "method": "template_match",
          "template": "DailyRewards/FinishedTaskIcon.png",
          "roi": [929, 432, 164, 148],
          "on_found": "break_loop"
        },
        {
          "id": "scroll_down",
          "action": "swipe",
          "start": [627, 528],
          "end": [627, 238],
          "duration": 300
        }
      ]
    },
    {
      "id": "check_activity_limit",
      "action": "check",
      "method": "ocr",
      "roi": [330, 520, 500, 100],
      "expected": ["今日活跃度已达上限", "Daily Activity Points Maxed"],
      "on_found": "complete"
    },
    {
      "id": "return_world",
      "action": "navigate",
      "target": "world",
      "method": "back_until"
    }
  ]
}
```

---

## 3. 活动奖励流程对比

### MaaEnd 流程（Event.json）

```
DailyEventStart
  └─> DailyEventEnterMenu (识别：InEventCenter)
      └─> DailyEventUnreadItemInit (自定义识别未读活动)
          └─> DailyEventUnreadItemSwitch (OCR 匹配 ".{3,}")
              └─> DailyEventUnreadItemSwitchSuccess (模板匹配切换成功)
                  └─> 各类活动子流程
```

**关键特性**：
1. **红点识别**：模板匹配 `EventRedDot.png`（绿色掩膜）
2. **前往按钮**：OCR 识别 "前往"/"Go"/"移動"
3. **活动切换**：OCR 匹配左侧活动列表文本
4. **分类处理**：限时签到、周常、引导活动、挑战活动等

### IstinaAI 当前实现

```json
{
  "steps": [
    {"action": "tap", "coords": [928, 53]},  // 活动图标
    {"action": "tap", "coords": [900, 200]}, // 子区域（未验证）
    {"action": "claim"}
  ]
}
```

**问题**：
1. 没有红点识别，无法判断是否有未领取奖励
2. 没有活动切换逻辑，只能处理当前活动
3. 没有分类处理，无法区分不同类型的活动

---

## 4. 邮件奖励流程对比

### MaaEnd 流程（Emails.json）

```
DailyEmailStart
  └─> DailyEmailWorldEnterMenuEmail (模板匹配世界菜单图标)
      └─> DailyEmailHasUnreadMessage (模板匹配未读邮件图标)
          └─> DailyEmailAlreadyInEmail (OCR 识别 "邮件"/"Mail")
              └─> DailyEmailReceiveEmail (OCR 识别 "全部收取"/"Claim All")
                  └─> DailyEmailConfirmEmail (OCR 识别 "邮箱奖励")
```

**关键特性**：
1. **图标检测**：模板匹配 `email.png` 和 `email2.png`
2. **OCR 识别**：多语言支持（中文/英文/日文/韩文）
3. **TSA 处理**：单独处理暂存区物资领取
4. **无奖励检测**：OCR 识别 "暂无附件"

---

## 5. 推荐修复优先级

### P0（阻塞性问题）

1. **退出对话框处理**
   - 实现模板匹配或多坐标尝试
   - 添加关闭验证逻辑

2. **页面类型判断**
   - 添加 OCR 识别辅助判断
   - 降低对金色元素计数的依赖

### P1（功能完整性）

3. **每日任务滑动机制**
   - 实现循环滑动直到底部
   - 检测 "已完成" 图标

4. **OCR 识别支持**
   - 集成 PaddleOCR 或 EasyOCR
   - 支持 "领取"/"Claim"/"前往" 等关键文本

### P2（优化增强）

5. **模板匹配支持**
   - 添加 MaaFw 模板匹配
   - 收集常用按钮模板（取消/确认/领取）

6. **错误恢复机制**
   - 实现 `[JumpBack]` 跳转
   - 添加超时和重试逻辑

---

## 6. 技术栈对比

| 功能 | MaaEnd | IstinaAI 当前 | IstinaAI 推荐 |
|------|--------|--------------|--------------|
| 图像识别 | MaaFw (C++) | OpenCV + YOLO | 保持 OpenCV，添加模板匹配 |
| OCR | PaddleOCR | VLM API | 本地 PaddleOCR 降级 |
| 触控 | MaaFw / ADB | ADB / MaaFw | 优先 ADB，回退 MaaFw |
| 流程引擎 | 状态机 (JSON) | 线性步骤 (JSON) | 扩展现有引擎支持状态机 |
| 坐标系统 | 1280x720 | 1920x1080 | 统一为 1920x1080（ADB 原生） |

---

## 7. 具体修复步骤

### 步骤 1：修复退出对话框（立即执行）

```bash
# 1. 运行高精度验证脚本
python scripts/high_precision_verify.py

# 2. 根据结果更新坐标或添加模板
# 3. 修改 standard_flow_engine.py 的 _verify_tap_result 方法
```

### 步骤 2：添加 OCR 支持（本周内）

```bash
# 1. 安装 PaddleOCR
pip install paddlepaddle paddleocr

# 2. 创建 OCR 工具类
# src/core/ocr/paddle_ocr.py

# 3. 在标准流引擎中集成
```

### 步骤 3：重构 daily_quest 流程（下周）

```bash
# 1. 更新 flows_config.json
# 2. 修改 StandardFlowExecutor 支持新动作类型
# 3. 测试验证
```

---

## 8. 结论

**MaaEnd 的优势**：
1. 成熟的模板匹配系统
2. 完善的 OCR 识别
3. 状态机流程控制
4. 多语言支持

**IstinaAI 的改进方向**：
1. 短期：修复 exit_dialog，添加多坐标尝试
2. 中期：集成本地 OCR，减少 VLM 依赖
3. 长期：引入模板匹配，重构流程引擎

**不建议直接复制 MaaEnd**：
- MaaEnd 基于 MaaFw C++ 框架，技术栈差异大
- 应基于 IstinaAI 现有技术栈逐步改进
- 参考 MaaEnd 的**设计思路**，而非直接复制代码
