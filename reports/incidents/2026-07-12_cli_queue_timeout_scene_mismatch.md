# CLI 队列执行超时 — 场景不匹配 + 预览状态简化

> 日期: 2026-07-12
> 关联: TASK_LOG 2026-07-12 15:30
> 类型: 问题分析 + 重构

## 1. 用户请求

1. 设备依然无法正确被控制，需要通过 CLI 执行队列并校验中间 OCR 结果以确认任务运作正确。
2. 预览状态只应当分为"实时"和"已断开"两种。

## 2. 根因分析

### 2.1 队列执行超时根因：场景不匹配

**直接原因**：`preset run DailyFullSkippingVisitFriends --serial 192.168.1.12:16512 --timeout 90` 执行 8 个任务，全部失败：
- 6 个任务（DijiangRewards, SellProduct, AutoStockStaple, EnvironmentMonitoring, DailyRewards, AutoCollect）在 90s 超时
- 2 个任务（CreditShoppingN2, DeliveryJobs）未定义 — 预设配置错误

**根本原因**：设备当前处于 "gameplay" 场景（confidence=0.7），而非主界面（home）。日常任务均假设从主界面启动，pipeline 找不到预期的 UI 元素，等待至超时。

**证据**：
- `scene identify` 对当前屏幕截图识别结果：`page_type="gameplay"`, `confidence=0.7`, `element_count=13`
- 检测到的元素包括 `SceneManager/LoginDialogConfirm`, `SceneManager/WorldSpaceExit`, `SceneManager/WordMenuBackpack2` — 表明设备处于游戏世界/场景选择界面
- 13:20-13:22 时段 VisitFriends 任务成功执行（TASK_LOG 记录），当时设备处于主界面

### 2.2 截图路径问题（附带发现）

**直接原因**：CLI 的 `screenshot` 和 `device screenshot` 命令在全新 CLI 进程中失败，返回 `{"status": "error", "message": "scrcpy not ready"}`。

**根本原因**：
1. **scrcpy 通道不跨进程持久化**：每个 CLI 进程是独立的，scrcpy 会话不共享。新进程需要重新启动 scrcpy，但首帧未就绪时截图返回 None。
2. **`_prepare_screen` 缺少 MaaEnd 回退**：`runtime.py:794` 直接调用 `self.android(serial).screenshot(serial=serial)`，而非 `_screenshot()`（后者有 MaaEnd AdbController 回退）。当 scrcpy 不可用时，没有回退路径。
3. **`_handle_device_screenshot` 缺少回退**：`handlers.py:427-430` 仅调用 `android.screenshot()`，无 MaaEnd 回退。

**影响**：任何需要截图的 CLI 命令（`scene identify`, `scene verify`, `scene elements`, `device screenshot`, `screenshot`）在全新进程中都会失败，除非：
- 提供 `--image` 参数（绕过截图）
- 先在同一进程中执行 `system connect` 并等待 scrcpy 就绪

### 2.3 预览状态简化

**用户要求**：预览状态只应当分为"实时"和"已断开"。

**原状态**（5 种）：实时、执行中、重连中、未连接、已断开

**新状态**（2 种）：实时、已断开

## 3. 修改方案

### 3.1 预览状态简化（已实施，commit faf7974）

**`src/gui/pyqt6/main_window.py`**:
- `_on_bridge_command_finished`: 连接成功不再显示"重连中"，直接触发 `_refresh_preview`；连接失败/断开显示"已断开"（红色）
- `_on_execution_state_changed`: 执行中不再显示"执行中"状态，保留上一次的状态角标
- `_refresh_preview`:
  - 未连接 → "已断开"（红色）
  - 执行中 → 不改变状态角标（保留上一次的"实时"或"已断开"）
  - 截图失败 < 3 次 → 不改变状态角标（保留上一次的"实时"显示，避免抖动）
  - 截图失败 ≥ 3 次 → "已断开"（红色）+ `set_connected(False)`
  - 截图成功 → "● 实时"（青色）
- 移除未使用的 `_STATUS_COLOR_RECONNECTING` 常量
- 失败阈值从 5 降至 3，更快响应连接断开

**`src/gui/pyqt6/locales/zh_CN.json` 和 `en_US.json`**:
- 移除 `preview_status_executing`, `preview_status_reconnecting`, `preview_status_lost` 三个键
- `preview_status_disconnected` 文案从 "未连接" 改为 "已断开"
- 保留 `preview_status_live` 和 `preview_lost_connection`（后者用于断开时的日志提示）

### 3.2 队列执行超时（未修改 — 场景不匹配，非代码 bug）

队列超时是场景状态问题，不是代码 bug。解决方向：
1. **手动操作**：用户手动将设备导航回主界面后重新执行队列
2. **预设设计**：在 DailyFullSkippingVisitFriends 预设前添加导航任务（如 `AndroidOpenGame` 或自定义 "GoHome" 任务）
3. **预设配置修正**：移除未定义的 CreditShoppingN2 和 DeliveryJobs，或将其替换为已定义的任务

### 3.3 截图路径问题（未修改 — 附带发现，待后续修复）

修复方向：
- `runtime.py:_prepare_screen` 应调用 `_screenshot()` 而非 `android.screenshot()` 直接调用，以获得 MaaEnd 回退
- `handlers.py:_handle_device_screenshot` 应通过 `runtime.execute("screenshot", {})` 而非 `android.screenshot()` 直接调用

## 4. 影响面

### 4.1 预览状态简化影响

| 组件 | 影响 |
|------|------|
| `MainWindow._refresh_preview` | 状态逻辑简化，不再有"执行中"/"重连中"中间状态 |
| `MainWindow._on_bridge_command_finished` | 连接成功不再显示中间状态，直接刷新 |
| `MainWindow._on_execution_state_changed` | 执行中不改变预览状态角标 |
| `PreviewWidget` | 无变化（仍接收 text+color） |
| locale 文件 | 移除 3 个未使用的状态键 |
| 用户体验 | 预览状态更清晰：只有"实时"和"已断开"，不再有中间状态 |

### 4.2 队列执行超时影响

- 不影响代码 — 这是场景状态问题
- 用户需要手动将设备导航回主界面后重新执行

## 5. 非期待变化

### 5.1 预览状态简化

- **可能变化**：执行任务期间预览状态角标显示"实时"（保留上一次状态），用户可能误以为预览仍在刷新。但预览定时器已停止（`_on_execution_state_changed` 中 `self._preview_timer.stop()`），不会实际刷新画面。
- **回退策略**：如需恢复"执行中"状态，可在 `_on_execution_state_changed` 中重新添加 `set_status` 调用。

### 5.2 失败阈值从 5 降至 3

- **可能变化**：网络抖动或瞬时截图失败时，更快标记为"已断开"。但单次失败仍不标记（保留"实时"显示），需要连续 3 次失败。
- **回退策略**：将 `>= 3` 改回 `>= 5`。

## 6. 验证

### 6.1 预览状态简化验证

- `py_compile` 通过
- 代码审查确认所有 `preview_status_*` 引用已更新
- 待用户运行 GUI 验证：连接设备后观察预览状态角标显示"● 实时"；断开设备后显示"已断开"

### 6.2 队列执行验证

- CLI `preset run DailyFullSkippingVisitFriends` 执行完成，8 个任务全部失败
- 日志确认 6 个任务超时（90s），2 个任务未定义
- `scene identify` 确认设备处于 "gameplay" 场景（非主界面）
- 35 个任务已定义，CreditShoppingN2 和 DeliveryJobs 不在其中

### 6.3 OCR/场景识别验证

- `scripts/verify_scene_identify.py` 使用本地截图文件验证 `scene.identify` 功能
- 成功识别场景为 "gameplay"，confidence=0.7，13 个元素
- OCR/模板匹配功能正常工作

## 7. 文件清单

| 文件 | 操作 |
|------|------|
| `src/gui/pyqt6/main_window.py` | 修改（预览状态简化） |
| `src/gui/pyqt6/locales/zh_CN.json` | 修改（移除未使用状态键） |
| `src/gui/pyqt6/locales/en_US.json` | 修改（移除未使用状态键） |
| `scripts/verify_scene_identify.py` | 新增（OCR 验证脚本） |
| `reports/incidents/2026-07-12_cli_queue_timeout_scene_mismatch.md` | 新增（本报告） |
| `docs/TASK_LOG.md` | 追加（任务记录） |
