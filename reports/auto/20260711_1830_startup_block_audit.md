# 批次 63：启动流程阻塞 / 预览定时器竞态 + 历史报告审计

> **生成时间**: 2026-07-11 18:30
> **审查范围**: `src/gui/pyqt6/pages/maaend_control_page.py` (1740+ 行), `src/gui/pyqt6/main_window.py` (391 行)
> **审计范围**: 批次 58（`20260711_160507.md`）、批次 60（`20260711_164102.md`）
> **方法**: 静态代码分析 + 调用链追踪 + Qt 嵌套事件循环语义推演
> **发现总计**: 2 新发现 + 2 审计验证
> **严重度分布**: 0 High / 1 Medium / 1 Low / 0 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。

---

## §1 新发现

### [NEW-MEDIUM] `maaend_control_page.py:1334-1355` — 启动序列阻塞主线程代码流长达 25 秒

```python
# line 1334-1338
def _do_auto_connect(self) -> None:
    params = self._resolve_connect_params()
    result = self._sync_execute("system connect", params, timeout_ms=15000)
    self._on_auto_connect_finished(bool(result and result.get("status") == "success"))
    QTimer.singleShot(0, self._do_metadata_load)

# line 1353-1355
def _do_metadata_load(self) -> None:
    result = self._sync_execute("metadata list", timeout_ms=10000)
    self._on_metadata_loaded(result or {})
```

**问题**：`_sync_execute` 通过嵌套 `QEventLoop` 实现同步等待。虽然 Qt 嵌套事件循环**仍然处理** I/O 事件（`readyReadStandardOutput`、`QTimer` 超时等），但**主线程代码流被阻塞**——`_on_auto_connect_finished`、`_on_metadata_loaded` 以及后续启动步骤（如 `self.refresh()` 中的 `_build_option_editor`）延迟执行。

**启动序列时序**：

```
GUI 显示
  │
  ├── 50ms 后: _delayed_init()
  │     ├── 停止预览定时器
  │     ├── self.refresh() → 渲染任务/预设列表
  │     └── QTimer.singleShot(0, _do_auto_connect)
  │
  ├── _do_auto_connect → _sync_execute("system connect", timeout=15000)
  │     └── 嵌套 QEventLoop 阻塞代码流 0~15 秒
  │           ├── I/O 事件仍被处理（ADB 通信、CLI 输出）
  │           └── 用户 UI 交互仍可发生（页面切换、按钮点击）
  │
  ├── _on_auto_connect_finished → 启动预览定时器（仅成功时）
  │
  └── _do_metadata_load → _sync_execute("metadata list", timeout=10000)
        └── 嵌套 QEventLoop 阻塞代码流 0~10 秒
```

**总阻塞时长**：0~25 秒（15s 自动连接 + 10s 元数据加载，均在最坏情况下超时）。

**影响面**：
- **用户体验**：启动后 25 秒内，任务/预设列表虽已渲染（`_delayed_init` 中的 `refresh()`），但元数据（任务选项定义等）未加载完成，选项编辑器（`_build_option_editor`）未构建。用户切换任务时可能看到空的选项面板。
- **竞态条件**：阻塞期间用户 UI 交互可发生，但启动序列逻辑不完整，与手动连接流程冲突（见 NEW-LOW）。
- **I/O 正常但逻辑延迟**：ADB 通信正常进行（嵌套事件循环处理 I/O），但 GUI 状态更新（日志追加、按钮状态）被延迟。

**建议**：将 `_do_auto_connect` 和 `_do_metadata_load 改为异步执行（QThread + 信号回调），避免阻塞主线程代码流。最小改动方案：

```python
def _do_auto_connect(self) -> None:
    params = self._resolve_connect_params()
    # 在工作线程中执行，通过信号回调结果
    worker = _AsyncCommandWorker(self._bridge, "system connect", params, timeout_ms=15000)
    worker.finished.connect(self._on_auto_connect_finished)
    worker.start()
    QTimer.singleShot(0, self._do_metadata_load)  # 立即调度元数据加载

def _do_metadata_load(self) -> None:
    worker = _AsyncCommandWorker(self._bridge, "metadata list", timeout_ms=10000)
    worker.finished.connect(self._on_metadata_loaded)
    worker.start()
```

其中 `_AsyncCommandWorker` 为 `QThread` 子类，在 `run()` 中调用 `_sync_execute`（在非主线程中，`_sync_execute` 通过 `BlockingQueuedConnection` 安全投递到主线程）。

---

### [NEW-LOW] `maaend_control_page.py:1340-1351` — 自动连接超时后手动连接成功，预览定时器未重启

```python
# line 1340-1351
def _on_auto_connect_finished(self, success: bool) -> None:
    if success:
        self._connected = True
        self._auto_connect_attempted = False
        self._append_log("系统", locale.tr("auto_connect_success", ...))
    else:
        self._auto_connect_attempted = True
        self._append_log("系统", locale.tr("auto_connect_failed", ...))

    preview_timer = getattr(self.window(), "_preview_timer", None)
    if preview_timer is not None and self._connected:
        preview_timer.start()
```

```python
# main_window.py:279-287
def _on_bridge_command_finished(self, command: str, result: dict) -> None:
    if command.startswith("system connect"):
        if result.get("status") == "success":
            self._maaend_page.set_connected(True)
            QTimer.singleShot(0, self._refresh_preview)  # 仅单次刷新
        else:
            self._maaend_page.set_connected(False)
            self._maaend_page.set_auto_connect_attempted()
```

**问题**：Qt 嵌套事件循环（`_sync_execute` 中的 `loop.exec()`）**仍处理**用户 UI 交互事件。用户在自动连接阻塞期间可切换到 device_settings_page 并手动连接成功。但：

1. `_on_auto_connect_finished(False)` 已执行（超时路径）→ `_auto_connect_attempted = True`，预览定时器**未启动**
2. 手动连接成功 → `_on_bridge_command_finished` → `set_connected(True)` + **仅单次** `_refresh_preview`，持续预览定时器**未启动**
3. `set_connected(True)` 仅设置 `_connected = True`，不启动预览定时器

**结果**：设备已连接，但预览画面只刷新一帧后停止更新。用户必须手动切换到标准推理页（触发 `_on_nav_changed`）才能恢复持续预览。

**预览定时器启动路径**（全部不覆盖此场景）：
| 路径 | 触发条件 | 本场景是否覆盖 |
|------|----------|----------------|
| `_on_auto_connect_finished(True)` | 自动连接成功 | ❌ 超时路径 |
| `_on_nav_changed(index=maaend)` | 用户切换到标准推理页 | ❌ 用户未切换 |
| `_on_execution_state_changed(False)` | 任务执行完成且当前在标准推理页 | ❌ 无任务执行 |
| `_on_bridge_command_finished` | 手动连接成功 | ❌ 仅单次刷新 |

**影响面**：低——需用户在启动自动连接阻塞期间主动手动连接，触发条件较苛刻。但一旦触发，预览持续停止是明确的功能退化。

**建议**：在 `_on_bridge_command_finished` 的 `system connect` 成功分支中启动预览定时器：

```python
if command.startswith("system connect"):
    if result.get("status") == "success":
        self._maaend_page.set_connected(True)
        QTimer.singleShot(0, self._refresh_preview)
        preview_timer = getattr(self, "_preview_timer", None)
        if preview_timer is not None and self._page_stack.currentWidget() is self._maaend_page:
            preview_timer.start()
    ...
```

或在 `set_connected(True)` 时由调用方决定是否启动定时器，避免 `_on_bridge_command_finished` 依赖 `_page_stack` 状态。

---

## §2 历史报告审计

### [AUDIT-1] 批次 58 `20260711_160507.md` — GUI58-02 分析正确，维持 Low

**GUI58-02**（`main_window.py:305` `singleShot` lambda 崩溃风险）：

审计结论：**合理，维持 Low**。

分析验证：
- `QTimer.singleShot(1000, lambda: self._set_taskbar_progress(0))` 创建的 QTimer 无父对象
- lambda 闭包通过引用捕获 `self`（MainWindow 实例）
- 若 MainWindow 在 1 秒内被销毁（非托盘模式关闭），timer 触发时 C++ 对象已删除
- Python wrapper 仍存在但底层 C++ 对象无效 → `RuntimeError: wrapped C/C++ object of type MainWindow has been deleted`

技术分析正确。虽然实际触发概率低（任务执行通常持续数秒至数分钟，用户需在完成后 1 秒内关闭窗口），但代码路径确实存在崩溃风险。

**建议微调**：原报告建议"为 QTimer 设置父对象"不适用于 `singleShot`（其设计即为无父）。更准确的修复建议是使用 `QObject` 方法作为回调而非 lambda，或将 timer 创建移至 `__init__` 中作为有父的子对象复用：

```python
# 方案 1：使用 bound method 而非 lambda（self 引用在 timer 中自然处理）
QTimer.singleShot(1000, self._clear_taskbar_progress)

# 方案 2：在 __init__ 中创建持久化 timer
self._taskbar_clear_timer = QTimer(self)
self._taskbar_clear_timer.setSingleShot(True)
self._taskbar_clear_timer.timeout.connect(self._clear_taskbar_progress)
```

原报告的"修改建议"不够精确（`singleShot` 无法设置父对象），但核心论断（崩溃风险存在）正确，故维持 Low 评级。

---

### [AUDIT-2] 批次 60 `20260711_164102.md` — 审计确认无矛盾

批次 60 审查范围：`service/runtime.py`、`tasks/task_runner.py`、`device/touch_manager.py`、`gui/pyqt6/main.py`、`pages/prts_full_intelligence_page.py`。

审计结论：**合理，无矛盾**。

关键验证点：
- **3 新发现**：runtime.py 状态序列化缺失异常处理、task_runner.py 任务结果未持久化、touch_manager.py 单例线程安全。全部为运行时/任务层新发现，与本批次审查范围（GUI 启动流程）无重叠。
- **1 审计验证**：对批次 1445 DEADCODE01 的复核确认 `analyze_scene_3d` 死代码结论准确。
- 无与本批次发现冲突的论断。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | NEW-MEDIUM（`_do_auto_connect` 阻塞主线程代码流 25 秒） | Medium | 历史未覆盖 |
| 新发现 | NEW-LOW（自动连接超时 + 手动连接竞态，预览定时器未重启） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 58 GUI58-02 正确） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 60 合理） | — | 确认无误 |
| **合计** | **2 新 + 2 审计** | **1M / 1L** | — |

---

## §4 跨批次一致性验证

- **批次 62 NEW-LOW**（`_resolve_connect_params` 静默吞异常）→ 与本批次独立，不冲突。本批次关注启动流程的阻塞/竞态，批次 62 关注异常处理缺失。
- **批次 58 GUI58-02**（`singleShot` lambda 崩溃风险）→ 与本批次独立，不冲突。本批次关注预览定时器的竞态条件，批次 58 关注 timer 生命周期管理。
- **批次 2345 U2**（`_refresh_preview` 阻塞 GUI 2-4 秒）→ 与本批次互补。2345 关注持续预览刷新阻塞，本批次关注启动序列的间歇性阻塞。
- **批次 1730 SRV-08**（device_settings_page 重连定时器）→ 与本批次独立文件/路径，不冲突。
- **批次 56 SRV-01** → 批次 1745 A1 已推翻为假阳性，本批不重复。
- **批次 56 SRV-02** → 批次 1745 A2 已降级，本批不重复。

---

## §5 验证方法

- 全部发现基于对 `maaend_control_page.py`、`main_window.py` 的**逐行静态阅读**与 Qt 嵌套事件循环语义推演。
- **未执行任何测试**，未修改任何业务代码。
- 审计部分基于对批次 58、批次 60 报告的逐条代码复核。
- 关键推演依据：Qt 文档中 `QEventLoop.exec()` 仍处理事件队列（含用户输入），但当前调用栈被阻塞——这是 Qt 嵌套事件循环的确定语义。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
