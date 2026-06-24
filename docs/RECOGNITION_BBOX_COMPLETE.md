# 识别结果带坐标区域机制 - 完成报告

## 修改目标 ✅

OCR 与模板匹配返回的元素应当带有坐标区域，LLM 自行决定行为而不是模板化坐标（提供 3CUI 的坐标，但具体行为由 LLM 决定）。

## 完成状态

### ✅ 核心识别引擎

#### 1. RecognitionEngine (SIFT 版本)
- 文件：`src/core/recognition/recognition_engine.py`
- 修改：`_template_match()` 和 `_color_match()` 返回 `bbox` 和 `center`
- 状态：✅ 完成（两个分支）

#### 2. RecognitionEngine (传统版本)
- 文件：`src/core/recognition.py`
- 修改：`_template_match()` 和 `_color_match()` 返回 `bbox` 和 `center`
- 状态：✅ 完成（两个分支）

### ✅ 页面分析器

- 文件：`src/core/page_analyzer.py`
- 修改：所有检测方法返回包含 `bbox`/`center` 的 detail
- 状态：✅ 完成（两个分支）

### ✅ 状态机

- 文件：`src/core/recognition/state_machine.py`
- 修改：`_get_click_coords()` 支持新格式 `bbox`/`center`，兼容旧格式 `location`
- 状态：✅ 完成（两个分支）

### ✅ 标准流引擎

- 文件：`scripts/standard_flow_engine.py`
- 新增方法：
  - `_decide_action_with_recognition()` - 根据识别结果让 LLM 决策
  - `_run_recognition()` - 执行 OCR+ 模板匹配 + 颜色匹配
  - `_build_recognition_prompt()` - 构建 LLM 提示词
  - `_get_reference_action()` - 降级到 3CUI 参考坐标
- 状态：✅ 完成（IstinaEndfieldAssistant）

### ✅ 文档

- `RECOGNITION_TO_BBOX_DESIGN.md` - 设计文档
- `RECOGNITION_CONFIG_EXAMPLE.md` - 配置示例
- `RECOGNITION_BBOX_SUMMARY.md` - 完整总结
- 状态：✅ 完成（两个分支）

## 返回格式

### TemplateMatch
```python
(True, {
    "bbox": [x1, y1, x2, y2],      # 边界框（全局坐标）
    "center": [cx, cy],             # 中心点
    "matches": int,                 # 匹配点数（SIFT）
    "confidence": float,            # 置信度（SIFT）
    "score": float,                 # 匹配分数（传统）
    "template": str                 # 模板路径
})
```

### ColorMatch
```python
(True, {
    "contours": int,                # 轮廓数量
    "bboxes": [[x1,y1,x2,y2],...],  # 所有轮廓的边界框
    "centers": [[cx,cy],...],       # 所有轮廓的中心点
    "total_area": int               # 总面积
})
```

## LLM 决策流程

```
1. 执行识别（OCR + 模板匹配 + 颜色匹配）
   ↓
2. 构建上下文（识别结果 + 3CUI 参考坐标 + 任务描述）
   ↓
3. LLM 根据优先级规则决定点击位置
   - 优先：OCR 识别结果的 bbox center
   - 其次：模板匹配结果的 bbox center（最高置信度）
   - 再次：颜色匹配结果的第一个 center
   - 降级：3CUI 参考坐标
   ↓
4. 执行动作（使用 LLM 决定的坐标）
```

## 配置示例

```json
{
  "action": "tap",
  "target": "quest_icon",
  "use_recognition": true,
  "recognition": {
    "ocr_expected": ["任务", "Quest"],
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
        "name": "yellow_button",
        "roi": [800, 40, 200, 100],
        "lower": [28, 100, 100],
        "upper": [29, 255, 255],
        "min_area": 50,
        "min_contours": 1
      }
    ]
  }
}
```

## 修改的文件清单

### IstinaEndfieldAssistant
1. `src/core/recognition/recognition_engine.py` - 返回格式增强
2. `src/core/recognition.py` - 返回格式增强
3. `src/core/page_analyzer.py` - 返回格式增强
4. `src/core/recognition/state_machine.py` - 兼容新格式
5. `scripts/standard_flow_engine.py` - LLM 决策方法
6. `docs/RECOGNITION_TO_BBOX_DESIGN.md` - 设计文档
7. `docs/RECOGNITION_CONFIG_EXAMPLE.md` - 配置示例
8. `docs/RECOGNITION_BBOX_SUMMARY.md` - 完整总结

### IstinaEndfieldAssistant_Sight
1. `src/core/recognition/recognition_engine.py` - 同步更新
2. `src/core/recognition.py` - 同步更新
3. `src/core/page_analyzer.py` - 同步更新
4. `src/core/recognition/state_machine.py` - 同步更新
5. `docs/RECOGNITION_TO_BBOX_DESIGN.md` - 同步文档
6. `docs/RECOGNITION_CONFIG_EXAMPLE.md` - 同步文档
7. `docs/RECOGNITION_BBOX_SUMMARY.md` - 同步文档

## 向后兼容性

- ✅ 保留 `location` 字段支持（state_machine.py 中兼容）
- ✅ 3CUI 参考坐标仍然保留（作为降级方案）
- ✅ 旧配置仍可正常工作（`use_recognition` 默认为 `false`）

## 优势

1. **鲁棒性提升** - 不依赖固定坐标，适应 UI 变化
2. **精确度提高** - 基于实际识别结果，定位更准确
3. **可解释性强** - LLM 提供决策原因，便于调试
4. **灵活性增强** - LLM 可根据上下文智能选择
5. **降级保障** - 3CUI 参考坐标作为回退方案

## 完成时间

2026-06-18
