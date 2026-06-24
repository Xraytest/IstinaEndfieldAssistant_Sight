# 识别结果带坐标区域机制 - 完整总结

## 修改目标

OCR 与模板匹配返回的元素应当带有坐标区域，LLM 自行决定行为而不是模板化坐标（提供 3CUI 的坐标，但具体行为由 LLM 决定）。

## 修改概览

### 1. 识别引擎返回格式增强

#### 1.1 RecognitionEngine (SIFT 版本)
位置：`src/core/recognition/recognition_engine.py`

**TemplateMatch 返回格式**：
```python
(True, {
    "bbox": [x1, y1, x2, y2],      # 边界框（全局坐标）
    "center": [cx, cy],             # 中心点
    "matches": int,                 # 匹配点数
    "confidence": float,            # 置信度 (0-1)
    "template": str                 # 模板路径
})
```

**ColorMatch 返回格式**：
```python
(True, {
    "contours": int,                # 轮廓数量
    "bboxes": [[x1,y1,x2,y2],...],  # 所有轮廓的边界框
    "centers": [[cx,cy],...],       # 所有轮廓的中心点
    "total_area": int               # 总面积
})
```

#### 1.2 RecognitionEngine (传统版本)
位置：`src/core/recognition.py`

**TemplateMatch 返回格式**：
```python
(True, {
    "bbox": [x1, y1, x2, y2],      # 边界框
    "center": [cx, cy],             # 中心点
    "score": float,                 # 匹配分数
    "template_size": [w, h]         # 模板尺寸
})
```

**ColorMatch 返回格式**：
```python
(True, {
    "contours": int,
    "bboxes": [[x1,y1,x2,y2],...],
    "centers": [[cx,cy],...],
    "total_area": int
})
```

### 2. 页面分析器更新

位置：`src/core/page_analyzer.py`

所有检测方法返回包含 bbox/center 的 detail：

```python
# 退出对话框
{
    "method": "CancelButton+SIFT+Color",
    "bbox": [x1, y1, x2, y2],
    "center": [cx, cy],
    "color_bboxes": [[x1,y1,x2,y2],...],
    "color_centers": [[cx,cy],...]
}

# 任务面板
{
    "method": "TaskIcon",
    "bbox": [x1, y1, x2, y2],
    "center": [cx, cy],
    "confidence": 0.85
}

# 世界页面
{
    "method": "WorldMenu",
    "bbox": [x1, y1, x2, y2],
    "center": [cx, cy],
    "confidence": 0.9
}
```

### 3. 标准流引擎 LLM 决策

位置：`scripts/standard_flow_engine.py`

新增方法：

#### 3.1 `_decide_action_with_recognition()`
根据识别结果让 LLM 自行决定点击位置。

流程：
1. 截图
2. 执行识别（OCR + 模板匹配 + 颜色匹配）
3. 构建上下文（识别结果 + 3CUI 参考坐标）
4. 调用 LLM 决策
5. 返回 LLM 决定的动作和坐标

#### 3.2 `_run_recognition()`
执行识别，返回格式：
```python
{
    "ocr": [
        {"text": "任务", "bbox": [...], "center": [...], "confidence": 0.9}
    ],
    "template": [
        {"name": "task_icon", "bbox": [...], "center": [...], "confidence": 0.85}
    ],
    "color": [
        {"name": "yellow_button", "bboxes": [...], "centers": [...]}
    ]
}
```

#### 3.3 `_build_recognition_prompt()`
构建 LLM 提示词，包含：
- 当前任务描述
- 识别结果（OCR/模板/颜色）
- 3CUI 参考坐标
- 决策规则

#### 3.4 `_get_reference_action()`
降级方案：当识别或 LLM 决策失败时，使用 3CUI 参考坐标。

### 4. 配置支持

在标准流配置中使用 `use_recognition: true` 启用基于识别的决策：

```json
{
  "action": "tap",
  "target": "quest_icon",
  "use_recognition": true,
  "recognition": {
    "ocr_expected": ["任务", "Quest", "每日任务"],
    "templates": [
      {
        "name": "task_icon",
        "path": "SceneManager/TaskIcon.png",
        "roi": [700, 30, 300, 150],
        "threshold": 15
      }
    ],
    "colors": [
      {
        "name": "yellow_indicator",
        "roi": [800, 40, 200, 100],
        "lower": [28, 100, 100],
        "upper": [29, 255, 255],
        "min_area": 50,
        "min_contours": 1
      }
    ]
  },
  "wait": 3,
  "desc": "打开任务面板（使用识别结果决定点击位置）"
}
```

### 5. LLM 决策规则

LLM 根据以下优先级选择点击位置：

1. **OCR 识别结果**：如果识别到目标文本，使用文本的 bbox center
2. **模板匹配结果**：如果模板匹配成功，使用置信度最高的 bbox center
3. **颜色匹配结果**：如果颜色匹配成功，使用第一个轮廓的 center
4. **3CUI 参考坐标**：如果所有识别都失败，使用参考坐标
5. **多个匹配结果**：选择最符合任务描述的

### 6. 工作流程

```
┌─────────────────────────────┐
│  标准流步骤配置              │
│  (含 3CUI 参考坐标)           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  执行识别                    │
│  - OCR (MaaFw Pipeline)     │
│  - 模板匹配 (SIFT/传统)      │
│  - 颜色匹配 (HSV 轮廓)        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  构建上下文                   │
│  - 识别结果 (含 bbox)        │
│  - 3CUI 参考坐标              │
│  - 任务描述                   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  LLM 决策                     │
│  根据识别结果决定最佳位置     │
│  返回：{action, coords, reason}│
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  执行动作                     │
│  (使用 LLM 决定的坐标)         │
│  失败则降级到参考坐标         │
└─────────────────────────────┘
```

## 修改的文件

### IstinaEndfieldAssistant
- `src/core/recognition/recognition_engine.py` - 更新返回格式
- `src/core/recognition.py` - 更新返回格式
- `src/core/page_analyzer.py` - 更新返回格式
- `scripts/standard_flow_engine.py` - 新增 LLM 决策方法
- `docs/RECOGNITION_TO_BBOX_DESIGN.md` - 设计文档
- `docs/RECOGNITION_CONFIG_EXAMPLE.md` - 配置示例

### IstinaEndfieldAssistant_Sight
- `src/core/recognition/recognition_engine.py` - 同步更新
- `src/core/recognition.py` - 同步更新
- `src/core/page_analyzer.py` - 同步更新
- `docs/RECOGNITION_TO_BBOX_DESIGN.md` - 同步文档
- `docs/RECOGNITION_CONFIG_EXAMPLE.md` - 同步文档

## 优势

1. **鲁棒性提升**：不依赖固定坐标，能适应 UI 变化
2. **精确度提高**：基于实际识别结果，定位更准确
3. **可解释性强**：LLM 提供决策原因，便于调试
4. **灵活性增强**：LLM 可根据上下文智能选择
5. **降级保障**：3CUI 参考坐标作为回退方案

## 使用示例

```python
# 在标准流配置中启用基于识别的决策
{
    "id": "open_quest_panel",
    "action": "tap",
    "target": "quest_icon",
    "use_recognition": true,  # 启用识别决策
    "recognition": {
        "ocr_expected": ["任务", "Quest"],
        "templates": [...],
        "colors": [...]
    },
    "wait": 3,
    "desc": "打开任务面板"
}
```

执行时：
1. 引擎检测到 `use_recognition: true`
2. 调用 `_decide_action_with_recognition()`
3. 执行识别，获取 bbox 信息
4. LLM 根据识别结果决定点击位置
5. 如果 LLM 决策失败，降级到 `nav_coords.quest_icon`

## 注意事项

1. 3CUI 参考坐标仍然保留，作为识别失败时的回退
2. 需要预先准备模板图片（放在 assets 目录）
3. OCR 功能需要集成 MaaFw Pipeline
4. 颜色匹配需要调整 HSV 范围以适应不同 UI 元素
5. LLM 需要有明确的优先级规则
