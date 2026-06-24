"""
IEA CLI 模块 — 领域专用的 CLI 处理模块

每个子模块封装一个领域，istina.py 作为薄路由层调用它们。

子模块:
  gpu_cli.py       — GPU 检测、CUDA 可用性、推荐模型
  system_cli.py    — 系统诊断、环境检查、性能监控
  device_cli.py    — 设备管理、截图、ADB 操作
  scenario_cli.py  — 场景采集、导航流程、探索
"""
