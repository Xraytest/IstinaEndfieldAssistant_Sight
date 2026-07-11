"""PyQt 全页面渲染验证模块

渲染完整的 MaaEndControlPage（而非孤立元素），在真实 Windows 平台下截图取证。
用于定位布局上下文导致的视觉差异（如 splitter 拉伸、父级样式继承等）。

用法:
  python -m ToolBox.pyqt_renderer <output.png> [--width W] [--height H]

输出:
  - 完整页面截图（含左侧导航、顶部标题、底部按钮栏）
  - 控制台打印关键 widget 的尺寸信息
"""
