# 高可靠标准流配置完成报告

## 完成时间
2026-06-18

## 完成内容

### 1. 图标含义完善

#### 导航图标 (世界页面顶部栏)
| 图标 | 坐标 | 含义 | 验证状态 | 识别配置 |
|------|------|------|----------|----------|
| TaskIcon | (860, 80) | 任务面板入口 | ✅ | 模板+OCR+ 颜色 |
| EventIcon | (928, 53) | 活动中心入口 | ✅ | 模板+OCR |
| MenuIcon | (1392, 79) | 系统菜单入口 | ✅ | 模板 |
| CityMap | (150, 150) | 城市地图入口 | ✅ | 模板 |

#### 面板内操作图标
| 图标 | 坐标 | 含义 | 识别配置 |
|------|------|------|----------|
| ClaimAll | (810, 900) | 一键领取 | OCR+ 颜色 |
| DailyClaim | (975, 288) | 每日领取 | OCR |
| WeeklyTab | (810, 300) | 周常标签 | OCR |

### 2. VLM Prompt 修缮

#### 导航确认 Prompt
```
基于识别结果确认是否应该点击目标元素
输入：task, recognition_results, reference_coords
输出：YES/NO
```

#### 页面验证 Prompt
```
根据画面特征验证当前页面类型
输入：expected_page, features, recognition_results
输出：world/quest_panel/event_panel/...
```

#### 动作决策 Prompt
```
根据识别结果决定点击位置
输入：task, recognition_results, reference_coords
输出：{"action", "coords", "reason"}
```

#### 状态分析 Prompt
```
分析当前页面状态
输入：page, goal, features
输出：{"can_proceed", "status", "next_action", "reason"}
```

### 3. MaaEnd 流程参考整合

#### DijiangRewards 模式 (每日任务)
```
Navigation(打开面板) → StatusCheck(确认页面) → ScrollFind(滑动查找) → Claim(领取) → Back(返回)
```

#### BAKER 模式 (周常任务)
```
SwitchTab(切换标签) → SwipeFilter(滑动筛选) → FilterUnread(查找可领取) → Claim(领取)
```

### 4. 识别配置

#### 任务图标识别
```json
{
  "template": "SceneManager/TaskIcon.png",
  "roi": [700, 30, 300, 150],
  "threshold": 5,
  "ocr_expected": ["任务", "Quest", "每日", "每周"],
  "color": {
    "name": "yellow_indicator",
    "roi": [800, 40, 200, 100],
    "lower": [28, 100, 100],
    "upper": [29, 255, 255]
  }
}
```

#### 领取按钮识别
```json
{
  "ocr_expected": ["领取", "Claim", "一键领取", "收取"],
  "color": {
    "name": "yellow_claim_button",
    "roi": [800, 200, 400, 400],
    "lower": [28, 100, 100],
    "upper": [29, 255, 255]
  }
}
```

### 5. 页面类型特征

| 页面类型 | left_bar | green | brightness | gold |
|---------|----------|-------|------------|------|
| world | 30-50 | >100 | 80-120 | 5-15 |
| quest_panel | 40-60 | 0-50 | 70-100 | 22-50 |
| exit_dialog | <15 | 0 | >100 | 2-5 |
| title_loading | >150 | 0 | >180 | 0-2 |

### 6. 错误恢复策略

#### 退出对话框处理
1. 检测对话框 (left_bar < 15)
2. 尝试点击取消按钮 (最多 3 次)
3. 如果失败，重启游戏

#### 无响应处理
1. 检测画面无变化 (连续 3 次相同)
2. 重启游戏 (com.hypergryph.endfield)
3. 等待 15 秒加载

### 7. 配置文件

#### flows_config_v5.json
- 版本：5.0
- 包含：识别配置、VLM Prompt、页面特征、流程定义
- 位置：`config/standard_flows/flows_config_v5.json`

#### STANDARD_FLOW_ICON_PROMPT_DESIGN.md
- 图标含义完整定义
- VLM Prompt 设计文档
- MaaEnd 流程参考
- 页面特征定义
- 错误恢复策略

### 8. 执行引擎

#### high_reliability_flow_engine.py
- 识别增强：OCR+ 模板匹配 + 颜色匹配
- LLM 决策：根据识别结果决定点击位置
- MaaEnd 模式：Navigation→StatusCheck→ScrollFind→Claim→Back
- 错误恢复：无响应时自动重启游戏
- 多重验证：坐标验证 + 页面验证+VLM 验证
- 无超时机制：等待用户确认或自动恢复

## 高可靠性保证

### 1. 多重验证
- 坐标验证：ADB tap 后截图验证画面变化
- 页面验证：使用特征确认页面类型
- VLM 验证：关键步骤使用 VLM 确认

### 2. 降级方案
- 识别失败：使用参考坐标
- 点击失败：重启游戏
- 页面错误：按返回键回到已知状态

### 3. 无超时机制
- 等待用户确认或自动恢复
- 不强制中断流程
- 依赖错误恢复策略处理异常情况

## 测试验证

### 已验证
- ✅ 游戏重启功能 (com.hypergryph.endfield)
- ✅ 退出对话框检测
- ✅ 页面类型特征提取
- ✅ 识别记录保存

### 待验证
- ⚠️ 模板匹配实际效果
- ⚠️ OCR 识别准确率
- ⚠️ VLM Prompt 效果
- ⚠️ 完整流程执行

## 下一步

1. 运行 `high_reliability_flow_engine.py` 测试完整流程
2. 根据测试结果调整识别配置
3. 优化 VLM Prompt 提高准确率
4. 完善错误恢复逻辑

## 文件清单

1. `config/standard_flows/flows_config_v5.json` - 标准流配置 v5
2. `docs/STANDARD_FLOW_ICON_PROMPT_DESIGN.md` - 图标含义与 Prompt 设计
3. `docs/STANDARD_FLOW_COMPLETE_REPORT.md` - 完成报告
4. `scripts/high_reliability_flow_engine.py` - 高可靠执行引擎
