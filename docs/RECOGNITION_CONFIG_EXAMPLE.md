# 基于识别结果的 LLM 决策配置示例

## 概述

此配置示例展示如何在标准流配置中使用新的基于识别结果的 LLM 决策机制。

## 配置结构

```json
{
  "action": "tap",
  "target": "quest_icon",
  "use_recognition": true,
  "recognition": {
    "ocr_expected": ["任务", "Quest", "每日", "每周"],
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
        "roi": [700, 30, 300, 150],
        "lower": [28, 100, 100],
        "upper": [29, 255, 255],
        "min_area": 100,
        "min_contours": 1
      }
    ]
  },
  "wait": 3,
  "desc": "打开任务面板（使用识别结果决定点击位置）"
}
```

## 字段说明

### 基本字段

- `action`: 动作类型（tap/back/wait/none）
- `target`: 目标标识符（用于获取 3CUI 参考坐标）
- `use_recognition`: 是否启用基于识别结果的 LLM 决策（true/false）
- `wait`: 动作后等待时间（秒）
- `desc`: 步骤描述

### recognition 配置

#### ocr_expected

期望识别的文本列表（支持正则表达式）。

```json
"ocr_expected": ["任务", "Quest", "每日", "每周", "(?i)daily"]
```

#### templates

模板匹配配置列表。

```json
"templates": [
  {
    "name": "任务图标",           // 模板名称（用于 LLM 识别）
    "path": "SceneManager/TaskIcon.png",  // 模板图片路径
    "roi": [700, 30, 300, 150],   // 搜索区域 [x, y, w, h]
    "threshold": 15                // 最小匹配点数
  }
]
```

#### colors

颜色匹配配置列表。

```json
"colors": [
  {
    "name": "黄色按钮",           // 颜色名称（用于 LLM 识别）
    "roi": [700, 30, 300, 150],   // 搜索区域 [x, y, w, h]
    "lower": [28, 100, 100],      // HSV 下限 [h, s, v]
    "upper": [29, 255, 255],      // HSV 上限 [h, s, v]
    "min_area": 100,              // 最小轮廓面积
    "min_contours": 1             // 最少轮廓数
  }
]
```

## 完整示例：每日任务流程

```json
{
  "daily_quest_with_recognition": {
    "enabled": true,
    "description": "每日任务（使用基于识别结果的 LLM 决策）",
    "steps": [
      {
        "id": "ensure_world",
        "action": "navigate",
        "target": "explore",
        "desc": "确保在探索界面"
      },
      {
        "id": "open_quest_panel",
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
        "wait": 4,
        "desc": "打开任务面板（使用识别结果决定点击位置）"
      },
      {
        "id": "verify_quest_panel",
        "action": "check",
        "expect": "quest_panel",
        "desc": "验证任务面板已打开"
      },
      {
        "id": "claim_daily_rewards",
        "action": "tap",
        "target": "daily_claim",
        "use_recognition": true,
        "recognition": {
          "ocr_expected": ["领取", "Claim", "一键领取"],
          "templates": [
            {
              "name": "claim_button",
              "path": "Common/Button/ClaimButton.png",
              "roi": [800, 200, 400, 400],
              "threshold": 10
            }
          ],
          "colors": [
            {
              "name": "yellow_claim_button",
              "roi": [800, 200, 400, 400],
              "lower": [28, 100, 100],
              "upper": [29, 255, 255],
              "min_area": 100,
              "min_contours": 1
            }
          ]
        },
        "wait": 3,
        "desc": "领取每日任务奖励（使用识别结果决定点击位置）"
      },
      {
        "id": "return_world",
        "action": "back",
        "wait": 2,
        "desc": "返回探索界面"
      }
    ]
  }
}
```

## LLM 决策流程

1. **执行识别**
   - OCR 识别期望文本
   - 模板匹配 UI 元素
   - 颜色匹配特定区域

2. **构建上下文**
   - 识别结果（包含所有匹配元素的 bbox）
   - 3CUI 参考坐标（作为回退）
   - 任务描述

3. **LLM 决策**
   - 分析识别结果
   - 根据优先级规则选择最佳点击位置
   - 返回 JSON 格式的动作和坐标

4. **执行动作**
   - 使用 LLM 决定的坐标执行点击
   - 如果 LLM 决策失败，降级到 3CUI 参考坐标

## 优先级规则

LLM 根据以下优先级选择点击位置：

1. **OCR 识别结果**：如果识别到目标文本，使用文本的 bbox center
2. **模板匹配结果**：如果模板匹配成功，使用置信度最高的 bbox center
3. **颜色匹配结果**：如果颜色匹配成功，使用第一个轮廓的 center
4. **3CUI 参考坐标**：如果所有识别都失败，使用参考坐标

## 优势

1. **鲁棒性提升**：不依赖固定坐标，能适应 UI 变化
2. **精确度提高**：基于实际识别结果，定位更准确
3. **可解释性强**：LLM 提供决策原因，便于调试
4. **灵活性增强**：LLM 可根据上下文智能选择

## 注意事项

1. 3CUI 参考坐标仍然保留，作为识别失败时的回退
2. 需要预先准备模板图片（放在 assets/resource_adb/image 目录）
3. OCR 功能需要集成 MaaFw Pipeline
4. 颜色匹配需要调整 HSV 范围以适应不同 UI 元素
