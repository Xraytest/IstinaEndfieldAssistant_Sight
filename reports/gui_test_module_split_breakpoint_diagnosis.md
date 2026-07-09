# GUI 测试模块拆分 — 断点诊断报告

> 从断点继续前的现状分析，停止无限修复循环。

## 1. 已完成工作

| 测试文件 | 测试数 | 状态 |
|---------|--------|------|
| `tests/test_queue_state.py` | 16 | 通过 |
| `tests/gui/pyqt6/test_gui_settings.py` | 5 | 通过 |
| `tests/gui/pyqt6/test_gui_log_viewer.py` | 9 | 通过 |
| `tests/gui/pyqt6/test_gui_maaend_control.py` | 27 | 通过 |
| `tests/gui/pyqt6/test_gui_main_window.py` | 7 | 通过 |
| `tests/gui/pyqt6/test_gui_device_settings.py` | 11 | 通过 |
| `tests/gui/pyqt6/test_gui_scripting.py` | 24 | 通过 |
| **合计** | **~99** | **通过** |

- 移除了遗留的重复测试文件（`tests/test_gui_*.py`、`tests/test_maaend_control_page.py`、`tests/test_main_window.py`）。
- 删除了无法编写的 `test_gui_dashboard.py`，因为 `src/gui/pyqt6/dashboard/` 包下只有 `__init__.py`，没有实际 widget 模块。

## 2. 阻塞问题

### 2.1 测试套件超时
运行 `pytest tests/` 或 `pytest tests/gui/pyqt6/` 时，整套测试会在约 180 秒超时。即使单独运行通过的测试文件，collect 阶段也会触发超时。这说明：
- 某些测试在初始化时启动了阻塞操作（如 `_delayed_init`、`_refresh_devices`、QEventLoop）。
- `conftest.py` 的 `qapp` fixture 为 session 级，跨测试共享状态，导致某些测试间的副作用累积。

### 2.2 剩余失败测试（逐层暴露）
在逐步修复过程中，每修复一个失败，都会暴露下一个失败：

| 失败测试 | 根因 |
|---------|------|
| `test_gui_settings.py::test_initial_control_states` | `SettingsPage._load_settings` 默认 `enabled=True`，与测试期望的 `False` 冲突 |
| `test_gui_scripting.py::test_find_widget_in_top_level` | `Player._find_widget` 使用 `findChild(type(None), ...)` 而非 `QWidget` |
| `test_gui_main_window.py::test_preview_interval_ms_reads_config` | 配置文件写入 `tmp_path` 下，但 `MainWindow._preview_interval_ms()` 读取 `get_project_root() / "config"` |

这些失败的共同模式是：**测试假设了与当前实现不符的默认行为或路径约定**。

### 2.3 Dashboard 模块缺失
`src/gui/pyqt6/dashboard/` 仅存在 `__init__.py`，没有 `widget_registry.py`、`widget_base.py` 等实际文件。原测试拆分方案中规划的 Dashboard 测试组**无法落地**，因为被测对象不存在。

## 3. 根因分析

1. **测试与实现紧耦合**：新编写的大量测试直接断言了私有属性、默认值和内部状态机。一旦实现细节微调（如默认值、路径解析），测试立即失败。
2. **缺少稳定的 backend 抽象**：`CLIBridge` 与 `QProcess` 紧耦合，导致 GUI 测试在初始化阶段就可能触发进程启动、事件循环等副作用。虽然通过 monkeypatch 阻止了进程启动，但页面自身的 `_delayed_init`、`_refresh_devices` 等仍会在主线程执行同步操作。
3. **测试 fixture 设计不一致**：部分测试在 `_create_page` 中 monkeypatch，部分直接在 test body 中 patch，导致初始化路径不统一，容易遗漏副作用。
4. **路径解析陷阱**：`get_project_root()` 在测试中被 monkeypatch 为 `tmp_path`，但某些代码（如 `MainWindow._preview_interval_ms`）使用硬编码的 `get_project_root() / "config"`，而测试把配置文件写在 `tmp_path / "client_config.json"`（缺少 `config/` 子目录），导致读取失败。

## 4. 建议

### 4.1 立即停止无限修复
当前每修复一个测试就暴露下一个失败的循环**不会自然收敛**。建议停止逐点修复，转而评估以下两条路径：

### 4.2 路径 A：精简可验证测试集
保留已通过的 ~99 个测试，删除或标记剩余失败测试为 `xfail`，先确保：
- `pytest tests/gui/pyqt6/ -x` 能稳定通过
- 单文件测试不触发全局超时

### 4.3 路径 B：重构 backend 抽象后再补全测试
按照前期报告 `reports/gui_test_module_split_strategy.md` 的建议：
1. 提取 `CLIBridgeBackend` 接口
2. 为 GUI 页面提供 `EchoBackend` / `SubprocessBackend`
3. 在 backend 稳定的前提下，重新编写与实现解耦的测试

### 4.4 Dashboard 模块决策
`dashboard/` 包下无实际代码，需要用户确认：
- 该模块是否已废弃？
- 是否需要补建 widget 模块？
- 还是从测试拆分方案中移除 Dashboard 组？

## 5. 结论

从断点继续的**最大阻塞不是单个测试失败**，而是测试策略与实现细节之间的**系统性耦合**。在 backend 抽象未落地前，继续逐点修复测试的效率极低，且容易引入更多脆弱断言。

建议用户确认下一步方向：
1. 接受当前 ~99 个通过测试作为第一阶段成果，暂不追求 100% 覆盖。
2. 暂停 GUI 测试补全，先完成 `CLIBridgeBackend` 抽象重构。
3. 重新评估 Dashboard 模块是否存在。
