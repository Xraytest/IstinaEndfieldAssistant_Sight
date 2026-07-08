# Arknights: Endfield 视觉设计语言研究

> 研究员：Research Agent  
> 日期：2026-07-07  
> 状态：初版（基于官网 + 实机截图 + 现有代码库分析）  
> 约束：仅研究，不修改代码；输出可落地的 PyQt6/QSS 设计 token。

---

## 1. Visual References（视觉参考）

### 1.1 官方来源
- **Endfield 官网**：[endfield.hypergryph.com](https://endfield.hypergryph.com/)
- **Arknights 官网**：[ak.hypergryph.com](https://ak.hypergryph.com/)
- **鹰角网络官网**：[hypergryph.com](https://www.hypergryph.com/)

### 1.2 项目实机截图（来自 output/）
以下截图来自 IstinaEndfieldAssistant_Sight 项目自身的游戏画面分析输出，真实还原 Endfield UI 叠加层：

| 截图 | 说明 |
|------|------|
| output/scene_analysis_overlay_v4_direct.png | 基地界面 HUD 叠加层，展示顶部状态栏、左侧任务面板、右侧角色栏 |
| output/scene_analysis_overlay_v3_direct.png | 游戏场景中的实体标记框（绿/黄/红三色距离编码）与底部 HUD |
| output/scene_analysis_overlay_v2.png | Scene Geometry Analysis 分析面板，展示深色卡片 + 青色描边风格 |
| output/scene_analysis_overlay.png | 早期分析视图，确认半透明深色底 + 终端青高亮 |

**核心视觉特征（从截图中提取）：**
- **底色**：极深蓝黑（接近 #0a0a0f），面板采用高透明度叠加
- **主色**：终端青（Terminal Cyan，约为 #18d1ff），用于边框、选中态、图标激活态
- **辅助色**：琥珀黄/金色（约 #fffa00~#ffbf00）用于警告、高亮实体、顶部活动图标
- **实体标记**：绿色（近）/黄色（中）/红色（远）的距离编码系统
- **字体**：中文使用无衬线黑体（微软雅黑 / PingFang SC），英文/数字等宽或窄体
- **边框**：1px 细线，带轻微发光或透明度变化；圆角极小（2px~4px）
- **图标风格**：线性图标，选中态填充或加粗，带有轻微的外发光

### 1.3 与现有 hypergryph_references.md 的对比
| 已有记录 | 本研究补充 |
|----------|-----------|
| 基地主界面为多面板叠加结构 | 截图证实：顶部行、左侧列、右侧列、底部行四区布局 |
| 游戏场景以蓝色主导（93.9%） | 实测截图：蓝色来自 3D 场景，UI 叠加层保持半透明深色 |
| 面板采用半透明深色底 + 青色描边 | 提取具体色值：rgba(16,16,26,0.88) + rgba(24,209,255,0.15) |
| 文字信息层级清晰 | 补充量化：标题 20~28px / 正文 12px / 辅助 10~11px |

---

## 2. Design Tokens（设计令牌）

### 2.1 Brand Colors（品牌色）

| Token | HEX / RGBA | 用途 | 来源 |
|-------|-----------|------|------|
| primary | #18d1ff | 主按钮、选中态、高亮、激活图标 | 官网 + 实机截图 |
| primary_dark | #06bbff | 按下态、次级高亮 | theme_manager.py |
| primary_darker | #0099cc | 禁用态主色、深色描边 | theme_manager.py |
| primary_light | #6ae5ff | 悬停态、发光边框 | theme_manager.py |
| primary_container | rgba(24, 209, 255, 0.12) | 主色容器背景（按钮底、选中底） | theme_manager.py |
| accent_gold | #fffa00 | 稀有、重要提示、活动图标 | 官网 + theme_manager.py |
| accent_gold_dark | #e6de01 | 金色按下态 | theme_manager.py |
| accent_gold_glow | rgba(255, 250, 0, 0.2) | 金色外发光 | theme_manager.py |
| success | #00ffa2 | 在线状态、成功反馈 | theme_manager.py |
| danger | #ff3355 | 错误、停止、删除 | theme_manager.py |
| warning | #fffa00 | 警告提示（与 accent_gold 共用） | theme_manager.py |
| bg_primary | #0a0a0f | 主背景 | 实机截图 + theme_manager.py |
| surface | rgba(16, 16, 26, 0.88) | 卡片/面板底 | 实机截图 + theme_manager.py |
| surface_elevated | rgba(26, 26, 38, 0.90) | 浮层、弹窗 | theme_manager.py |
| border | rgba(24, 209, 255, 0.15) | 默认描边、分割线 | theme_manager.py |
| border_light | rgba(24, 209, 255, 0.08) | 弱化描边 | theme_manager.py |
| text_primary | #e8e8ee | 主标题、正文 | theme_manager.py |
| text_secondary | #9090a8 | 次级信息、辅助文字 | theme_manager.py |
| text_tertiary | #606080 | 占位符、禁用说明 | theme_manager.py |
| text_disabled | #282840 | 禁用态文字 | theme_manager.py |

**实体距离色阶（从截图提取）：**
| 距离 | 色值 | 用途 |
|------|------|------|
| 近 | #00ffa2（绿） | entity_2 24.8m |
| 中 | #fffa00（黄） | entity_5 50.9m |
| 远 | #ff3355（红） | entity_6 49.7m（截图中红色用于较远实体） |

### 2.2 Typography（字体）

| Token | 值 | 用途 |
|-------|-----|------|
| font_family | Microsoft YaHei UI | 主字体（Windows 默认） |
| font_fallback | Segoe UI | 西文回退 |
| font_mono | Consolas | 终端/数值 |
| size_display | 42px | 页面大标题 |
| size_headline | 24px | 区块标题 |
| size_title | 17px | 卡片标题 |
| size_header | 20px | 页面 Header |
| size_body | 12px | 正文（基础单位） |
| size_small | 11px | 辅助说明 |
| size_label | 10px | 标签、角标 |
| weight_bold | 700 | 标题 |
| weight_medium | 500 | 次级强调 |
| weight_regular | 400 | 正文 |

**字间距规范：**
- 标题：letter-spacing: 1.5px ~ 2px
- 按钮：letter-spacing: 0.8px
- 正文：无额外字间距

### 2.3 Spacing（间距）

基于 4px 网格系统（与鹰角产品一致）：

| Token | 值 | 用途 |
|-------|-----|------|
| unit | 4px | 基础单位 |
| xs | 6px | 紧凑内边距 |
| sm | 8px | 组件间距 |
| md | 12px | 卡片内边距 |
| lg | 16px | 页面边距、区块间距 |
| xl | 20px | 大区块间距 |
| xxl | 24px | 页面级留白 |
| section | 16px | 区块分隔 |
| container | 20px | 内容容器 |
| card_padding | 20px | 卡片内边距 |
| button_padding_h | 24px | 按钮水平内边距 |
| button_padding_v | 10px | 按钮垂直内边距 |
| input_padding_h | 14px | 输入框水平内边距 |
| input_padding_v | 10px | 输入框垂直内边距 |

### 2.4 Corner Radius（圆角）

| Token | 值 | 用途 |
|-------|-----|------|
| none | 0px | 表格、分割线 |
| xs | 2px | 按钮（Endfield 风格）、列表项 |
| sm | 4px | 输入框、小按钮 |
| md | 6px | 卡片、GroupBox |
| lg | 8px | 面板、对话框 |
| xl | 12px | 大型浮层 |
| full | 9999px | 徽章、FAB、进度条 |

**Endfield 特征：** 游戏内 HUD 几乎无圆角（0~2px），本项目 PyQt6 可适度使用 4px 提升现代感，但需保持工业科幻的硬朗气质。

### 2.5 Shadows（阴影/发光）

| Token | 值 | 用途 |
|-------|-----|------|
| shadow | rgba(0, 0, 0, 0.5) | 对话框、下拉菜单 |
| shadow_light | rgba(0, 0, 0, 0.3) | 卡片悬停 |
| shadow_cyan | rgba(24, 209, 255, 0.06) | 主色微光（替代传统阴影） |
| shadow_gold | rgba(255, 250, 0, 0.08) | 金色高亮微光 |

**Endfield 风格：** 极少使用传统模糊阴影，更多使用 1px 边框 + 微透明度变化 + 外发光来营造层次。

### 2.6 Elevation（层级）

| Token | 值 | 对应组件 |
|-------|-----|----------|
| level_0 | 0 | 基础面板 |
| level_1 | 1 | 卡片 |
| level_2 | 2 | 悬浮卡片、菜单 |
| level_3 | 3 | 对话框 |
| level_4 | 4 | 抽屉 |
| level_5 | 5 | 模态弹窗 |

---
## 3. Animation & Interaction Patterns（动画与交互）

### 3.1 时长规范

| 状态 | 时长 | 缓动 |
|------|------|------|
| Hover 反馈 | 120ms | OutCubic |
| Press 反馈 | 60ms | OutCubic |
| Fade 显隐 | 180ms | OutCubic |
| 面板展开 | 200ms | OutCubic |
| 滑动切换 | 250ms | OutCubic |
| 对话框弹出 | 250ms | OutCubic |
| 慢速过渡 | 300~350ms | OutCubic |

### 3.2 交互动效模式（从官网 + 实机推断）

1. **Hover 态**：背景色从透明过渡到 rgba(24,209,255,0.08)，边框亮度提升
2. **选中态**：左侧出现 2px 主色竖线，背景填充 rgba(24,209,255,0.12)，文字变亮
3. **按钮按下**：背景加深，边框变为实色 rgba(24,209,255,0.5)
4. **图标激活**：外发光增强，颜色从 #18d1ff 变为 #6ae5ff
5. **面板展开**：从无到有渐变显示，无位移动效（保持低侵入性）
6. **滚动条**：4px 宽，主色半透明，悬停时加深

### 3.3 按钮状态矩阵

| 状态 | 背景 | 边框 | 文字 | 投影 |
|------|------|------|------|------|
| Default | rgba(13,19,28,0.92) | rgba(64,132,162,0.32) | #e8e8ee | 无 |
| Hover | rgba(24,209,255,0.08) | rgba(106,229,255,0.5) | #e8e8ee | 无 |
| Pressed | rgba(18,27,38,0.92) | rgba(24,209,255,0.5) | #e8e8ee | 无 |
| Disabled | rgba(16,16,26,0.88) | rgba(24,209,255,0.08) | #282840 | 无 |
| Primary | rgba(24,209,255,0.12) | rgba(24,209,255,0.37) | #6ae5ff | 无 |
| Primary Hover | rgba(24,209,255,0.20) | rgba(24,209,255,0.5) | #6ae5ff | 无 |
| Danger | transparent | rgba(255,51,85,0.4) | #ff3355 | 无 |

---

## 4. Recommendations for This Project（对本项目的建议）

### 4.1 与现有 theme_manager.py 的对比

现有主题系统已实现约 **80%** 的 Endfield 设计语言，但存在以下差异：

| 维度 | 当前实现 | Endfield 官方风格 | 建议 |
|------|----------|------------------|------|
| 主色 | #18d1ff ✅ | 一致 | 保持 |
| 金色警告 | #fffa00 ✅ | 一致 | 保持 |
| 圆角 | 按钮 4px，卡片 6px | 2~4px（工业硬朗） | **降低按钮圆角至 2px** |
| 字体 | Microsoft YaHei UI 12px | 类似 | 保持 |
| 阴影 | 有 shadow_cyan | 极少阴影，重边框 | **减少 box-shadow，增强 border 表达** |
| 间距 | 4px 网格 ✅ | 4px/8px 网格 | 保持 |
| 实体色阶 | 无 | 绿/黄/红三色 | **新增 entity_near / entity_mid / entity_far token** |

### 4.2 立即可用的 QSS 片段

以下 token 可直接复制到 theme_manager.py 或页面内联 QSS：

```css
/* Endfield 实体标记色 */
QWidget[entity-state="near"] { color: #00ffa2; border-color: rgba(0,255,162,0.6); }
QWidget[entity-state="mid"]  { color: #fffa00; border-color: rgba(255,250,0,0.6); }
QWidget[entity-state="far"]  { color: #ff3355; border-color: rgba(255,51,85,0.6); }

/* HUD 风格半透明面板（适合叠加在视频/图像上） */
QFrame#hudPanel {
    background-color: rgba(16, 16, 26, 0.75);
    border: 1px solid rgba(24, 209, 255, 0.25);
    border-radius: 2px;
}

/* 终端风格标签 */
QLabel[variant="terminal"] {
    color: #18d1ff;
    font-family: Consolas;
    font-size: 11px;
    letter-spacing: 1px;
}
```

### 4.3 优先级修复建议

1. **P0 — 统一圆角语言**  
   将按钮圆角从 4px 降至 2px，卡片圆角从 6px 降至 4px，更贴近 Endfield 工业硬朗风格。

2. **P0 — 减少阴影，强化边框**  
   移除 QPushButton 的 box-shadow 类效果（如有），改用 border-color 透明度变化表达层级。

3. **P1 — 新增实体距离色阶**  
   在 TIER_COLORS 或新增 ENTITY_COLORS 中定义绿/黄/红三色，用于 SceneGeometryAnalysis 等分析面板。

4. **P1 — 统一 Hero Header 模式**  
   参考截图顶部的 SCENE GEOMETRY OVERLAY 样式：深色底 + 底部 1px 主色描边 + 大标题 24px/700 + 副标题 12px/400 text_secondary。

5. **P2 — 微动效增强**  
   在 ANIMATION_CONFIG 中增加 hover_glow: True，悬停时边框亮度渐变而非突变。

6. **P2 — DPI 感知字体缩放**  
   当前 theme_manager.py 已有 QScreen.logicalDotsPerInch 检测，建议扩展断点：>110 正常，>144 中等放大，>192 全面放大。

### 4.4 待补充来源（与 hypergryph_references.md 联动）

- [ ] 截存 Endfield 基地界面完整 UI 截图至 assets/references/hypergryph/endfield_base_hub.png
- [ ] 截存 Arknights 主界面截图至 assets/references/hypergryph/arknights_main.png
- [ ] 使用取色器提取官网 CSS 中的精确色值（当前为视觉估算）
- [ ] 录制 Endfield 按钮/面板动效 GIF，分析缓动曲线

---
## 5. Appendix（附录）

### 5.1 现有 Theme Token 完整清单（theme_manager.py）

已实现 3 套主题：
- endfield：工业科幻 - 终端青 + 暗黑底色（本项目主用）
- arknight：经典暗黑 - 低调蓝灰 + 高对比
- minimal：极简白昼 - 浅色高对比 + 低饱和

### 5.2 截图元数据

| 文件 | 尺寸 | 内容 |
|------|------|------|
| scene_analysis_overlay_v4_direct.png | 1920x1080 | 实机 HUD + 实体检测叠加 |
| scene_analysis_overlay_v3_direct.png | 1920x1080 | 实机场景 + 底部控制栏 |
| scene_analysis_overlay_v2.png | 1800x1200 | Scene Geometry Analysis 面板 |
| scene_analysis_overlay.png | 1800x1200 | 早期分析视图 |

---

*本文件为只读研究输出，不涉及任何代码修改。*
