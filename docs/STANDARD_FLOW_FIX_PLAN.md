# 标准流修复方案 - 基于 MaaEnd 对比分析

生成时间：2026-06-11

## 问题诊断总结

### 之前错误的判断

**错误结论**: "标准流引擎已具备完整执行能力，6/6 检查通过"

**实际状态**: 标准流存在严重缺陷，无法正确执行

### 核心问题

| 问题 | MaaEnd 实现 | IstinaAI 当前 | 影响 |
|------|-------------|--------------|------|
| 退出对话框 | 模板匹配 CancelButton（全屏搜索） | 固定坐标 (600, 750) | 无法可靠关闭 |
| 页面判断 | OCR + 模板匹配 + 颜色匹配 | 金色元素计数 + YOLO 降级 | 判断不可靠 |
| 按钮定位 | 模板匹配 + ROI 限制 | 硬编码坐标 | 坐标不准确 |
| 流程控制 | 状态机（节点 + 跳转） | 线性步骤列表 | 缺乏异常处理 |
| OCR 识别 | PaddleOCR 本地识别 | VLM API（15 秒超时） | 超时风险高 |
| 滑动机制 | 循环滑动直到完成图标 | 无 | 遗漏任务 |

---

## 修复方案

### 1. 退出对话框处理（P0 阻塞性）

#### MaaEnd 实现
```json
{
  "name": "CancelButton",
  "recognition": {
    "type": "TemplateMatch",
    "param": {
      "roi": [0, 0, 1920, 1080],  // 全屏搜索
      "template": ["Common/Button/CancelButton.png"]
    }
  }
}
```

#### IstinaAI 修复方案

**方案 A（推荐）**：添加模板匹配
```python
def find_cancel_button(img):
    """使用模板匹配定位取消按钮"""
    # 1. 加载 CancelButton.png 模板
    # 2. 在全屏范围进行模板匹配
    # 3. 返回最佳匹配位置
    pass
```

**方案 B（快速）**：多坐标尝试 + 画面验证
```python
def close_exit_dialog_with_verify():
    """多坐标尝试，通过画面变化验证"""
    cancel_candidates = [
        (600, 750), (550, 730), (650, 770),
        (580, 740), (620, 760), (540, 720),
    ]
    
    for cx, cy in cancel_candidates:
        before = screencap()
        tap(cx, cy)
        time.sleep(1.5)
        after = screencap()
        
        diff = screen_diff(before, after)
        if diff > 500000:  # 画面变化大，说明点击有效
            return True
    
    return False
```

**已实现**：`scripts/verify_exit_dialog_fix.py`

---

### 2. 每日任务流程重构（P0）

#### MaaEnd 流程（Tasks.json）

```
DailyTaskStart
  └─> DailyTaskInMenu (识别：InOperationalManual)
      └─> DailyTaskEnterTab (OCR 识别 "日常"/"Daily")
          └─> DailyTaskClaimSingleReward (OCR 识别 "领取"/"Claim")
          └─> DailyTaskClaimActivityRewards (ColorMatch 红色奖励图标)
          └─> DailyTaskScrollDown (滑动查看更多，最多 50 次)
          └─> DailyTaskScrollFinished (模板匹配完成图标)
          └─> DailyTaskActivityLimitReached (OCR 识别 "活跃度已达上限")
```

**关键特性**：
1. **OCR 识别**：在 ROI 区域内识别 "日常"、"领取"、"Claim"
2. **颜色匹配**：检测红色奖励图标（HSV: 240-255, 100-130, 0-15）
3. **模板匹配**：识别完成图标
4. **滑动机制**：循环滑动直到检测到完成图标
5. **状态检查**：OCR 识别 "活跃度已达上限" 提前结束

#### IstinaAI 修复后流程

```json
{
  "daily_quest": {
    "enabled": true,
    "description": "完成每日任务并领取奖励（基于 MaaEnd Tasks.json 重构）",
    "steps": [
      {
        "id": "ensure_world",
        "action": "navigate",
        "target": "world",
        "method": "back_until",
        "verify": {
          "type": "golden_count",
          "range": [18, 21]
        },
        "desc": "确保在世界页面"
      },
      {
        "id": "close_exit_dialog",
        "action": "find_and_click",
        "method": "multi_coord_with_verify",
        "candidates": [
          [600, 750], [550, 730], [650, 770],
          [580, 740], [620, 760], [540, 720]
        ],
        "verify_diff": 500000,
        "optional": true,
        "desc": "关闭退出对话框（多坐标尝试 + 画面验证）"
      },
      {
        "id": "open_quest_panel",
        "action": "tap",
        "coords": [860, 80],
        "wait": 3,
        "verify": {
          "type": "ocr",
          "roi": [150, 100, 1000, 100],
          "expected": ["日常", "Daily", "任务"],
          "timeout": 5
        },
        "desc": "点击任务图标，验证进入任务面板"
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
            "expected": ["领取", "Claim", "受取", "領取"],
            "optional": true,
            "desc": "查找并点击领取按钮"
          },
          {
            "id": "check_activity_reward",
            "action": "find_and_click",
            "method": "color_match",
            "roi": [160, 200, 180, 350],
            "lower": [240, 100, 0],
            "upper": [255, 130, 15],
            "count": 20,
            "optional": true,
            "desc": "查找并点击活跃度奖励（红色图标）"
          },
          {
            "id": "check_finished",
            "action": "check",
            "method": "template_match",
            "template": "DailyRewards/FinishedTaskIcon.png",
            "roi": [929, 432, 164, 148],
            "on_found": "break_loop",
            "desc": "检查是否已全部完成"
          },
          {
            "id": "scroll_down",
            "action": "swipe",
            "start": [627, 528],
            "end": [627, 238],
            "duration": 300,
            "desc": "向下滑动查看更多任务"
          }
        ],
        "desc": "循环领取任务奖励"
      },
      {
        "id": "check_activity_limit",
        "action": "check",
        "method": "ocr",
        "roi": [330, 520, 500, 100],
        "expected": ["今日活跃度已达上限", "Daily Activity Points Maxed"],
        "on_found": "complete",
        "desc": "检查活跃度是否已达上限"
      },
      {
        "id": "return_world",
        "action": "navigate",
        "target": "world",
        "method": "back_until",
        "desc": "返回世界页面"
      }
    ]
  }
}
```

---

### 3. 需要添加的功能

#### 3.1 屏幕差异检测

```python
def screen_diff(img1, img2) -> int:
    """计算两张图片的差异像素数"""
    import cv2, numpy as np
    if img1 is None or img2 is None:
        return 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)
```

#### 3.2 OCR 识别（本地 PaddleOCR）

```python
def ocr_recognize(img, roi=None) -> str:
    """使用 PaddleOCR 识别文字"""
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    result = ocr.ocr(img, cls=True)
    # 提取文字
    text = " ".join([line[1][0] for line in result[0] if line])
    return text
```

#### 3.3 颜色匹配

```python
def color_match(img, roi, lower_hsv, upper_hsv, min_count=0) -> bool:
    """在 ROI 区域内匹配颜色"""
    import cv2, numpy as np
    x, y, w, h = roi
    roi_img = img[y:y+h, x:x+w]
    hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
    lower = np.array(lower_hsv)
    upper = np.array(upper_hsv)
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    count = len([c for c in contours if cv2.contourArea(c) > 30])
    return count >= min_count
```

#### 3.4 模板匹配

```python
def template_match(img, template_path, roi=None, threshold=0.85) -> Optional[tuple]:
    """模板匹配，返回最佳匹配位置"""
    import cv2
    template = cv2.imread(template_path)
    if roi:
        x, y, w, h = roi
        search_img = img[y:y+h, x:x+w]
    else:
        search_img = img
    result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        if roi:
            return (max_loc[0] + x, max_loc[1] + y)
        return max_loc
    return None
```

---

### 4. 实施步骤

#### 步骤 1：添加屏幕差异检测（立即）

修改 `standard_flow_engine.py`，在 `ScreenAnalyzer` 类后添加：

```python
def screen_diff(img1, img2) -> int:
    """计算两张图片的差异像素数"""
    import cv2, numpy as np
    if img1 is None or img2 is None:
        return 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)
```

#### 步骤 2：改进 exit_dialog 处理（立即）

修改 `_verify_tap_result` 方法中的 exit_dialog 处理：

```python
if page == "exit_dialog":
    print("  [恢复] 检测到退出对话框，尝试关闭...")
    cancel_candidates = [
        (600, 750), (550, 730), (650, 770),
        (580, 740), (620, 770), (540, 720),
    ]
    
    for cx, cy in cancel_candidates:
        before = adb_screencap()
        self._tap(cx, cy)
        self.adb.wait(1.5)
        after = adb_screencap()
        
        diff = screen_diff(before, after)
        if diff > 500000:
            print(f"  [恢复] 成功关闭对话框 (diff={diff:,})")
            break
    else:
        print("  [恢复] 所有坐标尝试失败")
        return False
```

#### 步骤 3：集成 PaddleOCR（本周内）

```bash
pip install paddlepaddle paddleocr
```

创建 `src/core/ocr/paddle_ocr.py`：

```python
from paddleocr import PaddleOCR

class PaddleOCREngine:
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
    
    def recognize(self, img, roi=None) -> str:
        if roi:
            x, y, w, h = roi
            img = img[y:y+h, x:x+w]
        result = self.ocr.ocr(img, cls=True)
        text = " ".join([line[1][0] for line in result[0] if line])
        return text
```

#### 步骤 4：更新 flows_config.json（下周）

参考上述修复后流程，更新 `daily_quest` 配置。

#### 步骤 5：扩展 StandardFlowExecutor（下周）

添加对新动作类型的支持：
- `find_and_click`：查找并点击（OCR/颜色/模板）
- `loop`：循环执行直到条件满足
- `color_match`：颜色匹配
- `template_match`：模板匹配

---

### 5. 验证方法

#### 5.1 退出对话框验证

```bash
python scripts/verify_exit_dialog_fix.py --rounds 5
```

预期结果：成功率 > 80%

#### 5.2 每日任务流程验证

```bash
python scripts/standard_flow_engine.py --flow daily_quest
```

预期结果：
- 能正确关闭退出对话框
- 能进入任务面板
- 能循环领取任务奖励
- 能检测到活跃度上限

#### 5.3 完整标准流验证

```bash
python scripts/standard_flow_engine.py --flow all
```

---

### 6. 时间估算

| 任务 | 优先级 | 时间 | 状态 |
|------|--------|------|------|
| 添加屏幕差异检测 | P0 | 1 小时 | 待开始 |
| 改进 exit_dialog 处理 | P0 | 2 小时 | 待开始 |
| 集成 PaddleOCR | P1 | 4 小时 | 待开始 |
| 更新 flows_config.json | P1 | 2 小时 | 待开始 |
| 扩展 StandardFlowExecutor | P1 | 8 小时 | 待开始 |
| 测试验证 | P0 | 4 小时 | 待开始 |
| **总计** | | **21 小时** | |

---

### 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| PaddleOCR 识别不准 | 无法识别"领取"按钮 | 使用多语言模型，增加关键词 |
| 模板匹配受分辨率影响 | 坐标偏移 | 使用相对坐标，支持缩放 |
| 滑动机制卡死 | 无限循环 | 设置最大迭代次数（10 次） |
| 颜色匹配误检 | 点击错误位置 | 结合 ROI 限制和最小面积过滤 |

---

### 8. 结论

**核心改进**：
1. 退出对话框：从固定坐标改为多坐标尝试 + 画面验证
2. 页面判断：从金色元素计数改为 OCR+ 模板 + 颜色多源融合
3. 流程控制：从线性步骤改为支持循环和条件跳转
4. 按钮定位：从硬编码坐标改为 OCR/模板/颜色动态定位

**不建议**：
- 直接复制 MaaEnd 代码（技术栈差异大）
- 完全依赖 VLM（超时风险高）
- 继续使用固定坐标（不准确）

**建议**：
- 参考 MaaEnd 的**设计思路**
- 基于 IstinaAI 现有技术栈逐步改进
- 优先修复阻塞性问题（exit_dialog）
- 逐步引入本地 OCR 和模板匹配
