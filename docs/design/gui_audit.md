# GUI 设计审计

> 基于 `src/gui/pyqt6/` 代码库的静态审计，持续更新。

## 审计时间
2026-07-07

## 1. 当前架构概览

| 文件 | 角色 | 状态 |
|------|------|------|
| `main.py` | 入口 | 正常 |
| `main_window.py` | 主窗口 + 导航 + 预览 | 正常 |
| `theme/theme_manager.py` | 主题系统 | 已有，但内联 QSS 与页面内联样式并存 |
| `pages/maaend_control_page.py` | 核心控制台（任务/预设/队列/日志） | 有大量内联样式常量 |
| `pages/device_settings_page.py` | 设备连接 | 正常 |
| `pages/settings_page.py` | 设置 | 正常 |
| `pages/log_page.py` | 日志查看 | 正常 |
| `pages/prts_full_intelligence_page.py` | 暂为空壳 | 正常 |
| `responsive.py` | 响应式 | 正常 |

## 2. 发现的问题

### 2.1 内联样式与主题系统脱节
- `theme_manager.py` 已有完整的 QSS 主题和 `ThemeManager`
- 但 `maaend_control_page.py` 中定义了 `CARD_STYLE`、`BTN_ACTIVE`、`LIST_STYLE` 等大量字符串常量
- 这些常量直接硬编码颜色值（如 `rgba(16,16,26,0.85)`），与主题系统的 token 完全重复且未同步
- **影响**：未来修改主题色时，需要同时改 `theme_manager.py` 和多个页面文件，极易遗漏

### 2.2 按钮标签与行为不一致（P0 示范修复点）
- `maaend_control_page.py:442`：按钮文本为“运行任务”，但 `_run_task()` 实际将任务加入队列而非立即运行
- 用户预期与实际行为不符，属于严重的可用性问题
- **鹰角设计原则**：控件标签必须准确描述行为

### 2.3 页面间视觉节奏不一致
- `SettingsPage`、`LogPage`、`DeviceSettingsPage` 使用 `settingsHero` / `ScrollArea` + 16px 边距
- `MaaEndControlPage` 使用 `QVBoxLayout` + `GroupBox` + `Splitter`，边距为 16px 但卡片内边距为 2px，过于紧凑
- 缺乏统一的页面 Hero（标题区域）模式

### 2.4 信息密度与可读性
- `maaend_control_page.py` 的队列表格使用 `QTableWidget`，但列宽与内容自适应不佳
- 任务/预设列表项选中态与悬停态对比度接近，快速扫视时边界模糊
- 日志区使用 HTML span 着色，但缺少统一的消息类型配色规范

### 2.5 响应式断点单一
- `responsive.py` 只有 `normal` / `compact` 两个模式，且仅在宽度 <960 或高度 <720 时切换
- 鹰角产品在不同 DPI / 缩放比下都有良好的信息密度调整，本项目缺少 DPI 感知的字体/间距缩放

### 2.6 图标系统缺失
- 当前所有按钮均为纯文本，无图标
- 鹰角 UI 中图标承担大量语义传达（任务、设置、删除、添加等）

## 3. 建议优化方向

1. **统一样式来源**：页面内联样式全部迁移到 `theme_manager.py`，通过 `ThemeManager` 读取
2. **统一页面骨架**：所有页面采用 `HeroHeader + ScrollArea + 卡片组` 结构
3. **建立图标系统**：使用 SVG 图标 + `QIcon`，建立 `gui/pyqt6/icons.py` 映射
4. **DPI 感知**：在 `responsive.py` 中引入 `QScreen.logicalDotsPerInch`，动态调整字体与间距
5. **微动效**：利用 `ANIMATION_CONFIG`，为按钮悬停、面板展开添加 120-200ms 过渡
