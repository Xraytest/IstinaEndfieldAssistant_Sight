# 识别结果带坐标区域设计文档

## 概述

修改机制：OCR 与模板匹配返回的元素应当带有坐标区域，LLM 自行决定行为而不是模板化坐标（提供 3CUI 的坐标，但具体行为由 LLM 决定）。

## 修改内容

### 1. RecognitionEngine 返回格式增强

#### TemplateMatch 返回格式
```python
# 成功
(True, {
    "bbox": [x1, y1, x2, y2],      # 边界框（全局坐标）
    "center": [cx, cy],             # 中心点
    "matches": int,                 # 匹配点数
    "confidence": float,            # 置信度 (0-1)
    "template": str                 # 模板路径
})

# 失败
(False, {"matches": int})
```

#### ColorMatch 返回格式
```python
# 成功
(True, {
    "contours": int,                # 轮廓数量
    "bboxes": [[x1,y1,x2,y2],...],  # 所有轮廓的边界框
    "centers": [[cx,cy],...],       # 所有轮廓的中心点
    "total_area": int               # 总面积
})

# 失败
(False, {"contours": int})
```

#### And/Or 组合识别返回格式
```python
# And: 聚合所有子节点的 bbox
(True, {
    "bboxes": [[x1,y1,x2,y2],...],  # 所有匹配元素的边界框
    "centers": [[cx,cy],...]         # 所有匹配元素的中心点
})

# Or: 返回第一个匹配的子节点完整信息
(True, {...})  # 与子节点返回格式相同
```

### 2. OCR 结果格式（MaaFw Pipeline）

```python
RecognitionDetail(
    hit: bool,                          # 是否匹配期望文本
    box: (x, y, w, h),                  # 匹配位置边界框
    all_results: list[RecognitionResult],  # 所有识别结果
    best_result: RecognitionResult       # 最佳匹配结果
)

RecognitionResult 包含:
- text: str              # 识别的文本
- bbox: [x1, y1, x2, y2] # 文本边界框（全局坐标）
- center: [cx, cy]       # 文本中心点
- confidence: float      # 置信度
```

### 3. 标准流引擎修改

#### 修改前的逻辑
```python
# 硬编码坐标
coords = nav_coords.get("quest_icon", [860, 80])
self._tap(coords[0], coords[1])
```

#### 修改后的逻辑
```python
# 1. 执行识别（OCR + 模板匹配）
recognition_results = self._run_recognition(step_cfg)

# 2. 构建上下文（包含识别结果和 3CUI 参考坐标）
context = {
    "recognition_results": recognition_results,
    "reference_coords": nav_coords.get(step_cfg.get("target"), [540, 360]),
    "step_description": step_cfg.get("desc", ""),
    "expected_action": step_cfg.get("action", "tap")
}

# 3. 让 LLM 根据识别结果决定点击位置
decision = self._llm_decide_action(context)

# 4. 执行 LLM 决定的动作
if decision.get("action") == "tap":
    coords = decision.get("coords")  # LLM 根据识别结果返回的坐标
    self._tap(coords[0], coords[1])
```

### 4. LLM 提示词模板

```
你是明日方舟终末地游戏自动化助手。根据识别结果决定点击位置。

当前任务：{step_description}
预期动作：{expected_action}

识别结果：
{recognition_results}

3CUI 参考坐标（仅作为参考，请优先使用识别结果的坐标）：
{reference_coords}

请分析识别结果，决定最佳点击位置。返回 JSON：
{{
    "action": "tap/back/wait/none",
    "coords": [x, y],  // 点击坐标，优先使用识别结果的 bbox center
    "reason": "选择该坐标的原因"
}}

规则：
1. 如果 OCR 识别到目标文本，使用文本的 bbox center
2. 如果模板匹配成功，使用匹配结果的 bbox center
3. 如果颜色匹配成功，使用第一个轮廓的 center
4. 如果所有识别都失败，使用 3CUI 参考坐标
5. 如果有多个匹配结果，选择最符合任务描述的
```

## 工作流程

```
┌─────────────────────┐
│  标准流步骤配置      │
│  (含 3CUI 参考坐标)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  执行识别            │
│  - OCR              │
│  - 模板匹配          │
│  - 颜色匹配          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  构建上下文           │
│  - 识别结果 (含 bbox) │
│  - 3CUI 参考坐标       │
│  - 任务描述           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LLM 决策             │
│  根据识别结果决定     │
│  最佳点击位置         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  执行动作             │
│  (使用 LLM 决定的坐标)  │
└─────────────────────┘
```

## 优势

1. **鲁棒性提升**：不依赖固定坐标，能适应 UI 变化
2. **精确度提高**：基于实际识别结果，定位更准确
3. **可解释性强**：LLM 提供决策原因，便于调试
4. **灵活性增强**：LLM 可根据上下文智能选择

## 注意事项

1. 3CUI 参考坐标仍然保留，作为识别失败时的回退
2. 识别结果需要包含完整的 bbox 信息
3. LLM 需要有明确的优先级规则
4. 需要验证机制确认点击是否成功

## 测试验证

1. 单元测试：验证 RecognitionEngine 返回格式
2. 集成测试：验证 LLM 决策逻辑
3. 端到端测试：验证完整流程执行
