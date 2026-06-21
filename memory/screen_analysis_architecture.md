---
name: 画面分析两层+VLM架构
description: OpenCV双特征快速判页(10ms) + VLM复杂场景决策(15s)的混合架构
type: project
---

画面分析系统采用 **OpenCV 主导 + VLM 辅助决策** 架构：

### Layer 1: HighPrecisionPageAnalyzer
- 双特征（left_bar_brightness + green_pixels_top_right）快速判页
- 约 10ms/帧，覆盖 ~90% 场景
- 返回 page_type + confidence + features

### Layer 2: RecognitionEngine
- OpenCV 模板匹配 + 颜色匹配 + And/Or 组合
- OCR 委托给 MaaFw Pipeline（原生 OCR，无需额外安装）

### VLM 决策层: VlmActionDecider
- **仅当 Layer 1 不确定时调用**：confidence < 0.5 或 page_type="unknown" 或与预期不符
- 调用 `_classify_with_vlm()` → `should_invoke_vlm()` 判断是否触发 → `VlmActionDecider.decide_action()` 获取决策
- VLM 返回结构化 JSON：{page_type, suggested_action, target, coordinates, reason}
- 超时 15s，失败降级返回

### 决策流程
```
截图 → Layer1 (OpenCV, 10ms)
  ├── 确定 → 直接执行标准动作
  └── 不确定 → VLM 介入决策 (15s) → 执行建议动作
```

**Why:** OpenCV 无法理解复杂 UI 布局和语义（如多个按钮中哪个是"领取"），VLM 补足这块。但 VLM 延迟高，只在边缘场景使用。
**How to apply:** 前置验证循环使用 `_classify_with_vlm()`，关闭对话框循环保持 `_classify_page()`（追求速度）。新增分析能力优先加到 Layer 1，只有语义理解需求才走 VLM。
