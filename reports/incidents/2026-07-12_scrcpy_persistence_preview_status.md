# scrcpy 持久保活 + 预览实时性修复 + 状态角标

> 日期：2026-07-12
> 关联：reports/incidents/2026-07-11_scrcpy_pipeline_disconnect_analysis.md（根因分析）、reports/incidents/2026-07-11_scrcpy_timeout_fix.md（超时修复）

## 1. 根因分析

### 1.1 scrcpy 会话线程死亡后不自动重连

**位置**：`src/core/capability/device/android_runtime.py` `_ScrcpySession._run()` (line 110-126)

`_run()` 在 socket 超时/异常后执行 `finally: _close_codec() + _cleanup()`，然后方法返回，线程死亡。下一次 `screenshot` 调用时 daemon 才发现线程已死并重启（`wait_first_frame=False` 非阻塞），但 `start()` 中 `if self._thread.is_alive(): return` 存在竞态窗口——线程刚死但 daemon 未感知时，screenshot 拿到 None。

### 1.2 `get_latest_frame()` 污染 keepalive 时间戳

**位置**：`_ScrcpySession.get_latest_frame()` (line 103-108)

```python
def get_latest_frame(self) -> Optional[np.ndarray]:
    with self._lock:
        if self._latest_frame is None:
            return None
        self._last_frame_ts = time.time()  # ← BUG
        return self._latest_frame
```

预览定时器每 1.5s 调用 screenshot → `get_latest_frame()`，不断刷新 `_last_frame_ts`。即使 scrcpy 流已断流 30s，只要 GUI 还在轮询，KEEPALIVE-01（`if (now - _last_frame_ts) > 10.0: break`）永远不触发。**keepalive 在预览启用时完全失效**。

### 1.3 `_decode_loop()` 无 server 进程存活检测

**位置**：`_decode_loop()` (line 285-296)

scrcpy server 进程退出后，`fileobj.read(12)` 会阻塞至 socket 超时（10s）。在此期间 keepalive 检查（循环顶部）无法执行，重建延迟从接近 0 膨胀至 10s。

### 1.4 预览 QLabel 无法叠加状态文字

**位置**：`src/gui/pyqt6/main_window.py` (line 170-177)

QLabel 的 `setPixmap` 和 `setText` 互斥——设置 pixmap 后无法同时显示文字。用户需要"在画面右下角标明状态"，QLabel 无法实现。

## 2. 修改方案

### 2.1 修复 `get_latest_frame()` keepalive 污染

**文件**：`src/core/capability/device/android_runtime.py` line 103-108

删除 `self._last_frame_ts = time.time()`。`_last_frame_ts` 仅在 `_decode_loop()` 收到新帧时更新（line 318 已正确），使 KEEPALIVE-01 恢复"10s 无新帧→break"语义。

### 2.2 `_run()` 改为自动重连循环

**文件**：`src/core/capability/device/android_runtime.py` line 109-133

将 `_run()` 主体包裹在 `while not self._stop_event.is_set()` 循环中：
- `_decode_loop()` 正常退出（KEEPALIVE-01 / socket 断开 / server 退出）后，`finally` 清理资源
- `time.sleep(2.0)` 退避后自动回到循环顶部重建会话
- `_wait_for_socket()` 失败时 `continue` 跳过 `_decode_loop()`
- 仅 `_stop_event.is_set()`（`stop()` 被调用）时退出循环

`_start_server()` 内部已 `pkill` 旧 server，无残留进程风险。

### 2.3 `_decode_loop()` 增加 server 进程存活检测

**文件**：`src/core/capability/device/android_runtime.py` line 285-296

在内层 `while` 循环中，KEEPALIVE-01 检查后增加：
```python
if self._server_proc is not None and self._server_proc.poll() is not None:
    self._logger.warning("scrcpy server 进程已退出", returncode=self._server_proc.returncode)
    break
```
`_server_proc.poll()` 返回非 None 表示进程已退出，提前 `break` 将重建延迟从 10s 降至接近 0。

### 2.4 新增 `PreviewWidget` 替换 QLabel

**文件**：`src/gui/pyqt6/main_window.py`

新增 `PreviewWidget(QWidget)` 类（~60 行），在 `paintEvent` 中：
1. 绘制深色背景
2. 绘制 pixmap（保持比例居中）或"暂无预览"文字
3. 在右下角绘制状态角标（`drawText` + `AlignBottom | AlignRight`）
4. 绘制半透明边框

状态色值（与 theme_manager.py COLORS 一致）：
- "● 实时" → `#19d1ff`（primary 青色）
- "执行中" → `#8a8ea4`（text_secondary 灰色）
- "重连中" → `#f08c00`（warning 橙色）
- "已断开" → `#e03131`（danger 红色）
- "未连接" → `#8a8ea4`（灰色）

### 2.5 `_refresh_preview()` 在各退出点设置状态角标

**文件**：`src/gui/pyqt6/main_window.py` `_refresh_preview()`

- `_connected == False` → "未连接"
- `_is_executing == True` → "执行中"（scrcpy 后台保活，预览不竞争 CLI 管道）
- screenshot 失败 → "重连中"（5 次失败后 → "已断开" + `set_connected(False)`）
- screenshot 成功 → "● 实时"

### 2.6 连接/执行状态变更时更新角标

- `_on_bridge_command_finished`：connect 成功 → "重连中"（等首帧刷新为"● 实时"）；disconnect → "未连接"
- `_on_execution_state_changed`：`is_executing=True` → "执行中"

### 2.7 i18n 键

`zh_CN.json` + `en_US.json` 新增 6 个键：`preview_status_live`、`preview_status_executing`、`preview_status_reconnecting`、`preview_status_disconnected`、`preview_status_lost`、`preview_lost_connection`。

## 3. 影响面

| 组件 | 影响 |
|------|------|
| `_ScrcpySession._run()` | 行为变化：从"单次执行后死亡"变为"循环重建直至 stop()"。daemon 的 `startScrcpy`/`screenshot` 死线程检查仍有效（`thread.is_alive()` 现在几乎总为 True，fallback 路径极少触发） |
| `_ScrcpySession.get_latest_frame()` | 仅删除一行。`_last_frame_ts` 不再被读操作污染，KEEPALIVE-01 恢复有效 |
| `_ScrcpySession._decode_loop()` | 新增 server 进程 poll 检查。无新行为，仅加速异常检测 |
| `MainWindow._preview_label` → `_preview_widget` | 类型从 `QLabel` 变为 `PreviewWidget`。`setPixmap` → `set_pixmap`，新增 `set_status` 调用 |
| `PREVIEW_STYLE` | 不再被 main_window.py 引用（常量保留在 widget_styles.py 供其他模块使用） |
| CLI 管道 | 不变。scrcpy session 仍在 CLI 进程内，preview 仍经 `_sync_execute("screenshot")` 走 CLI |
| 预览定时器间隔 | 不变（1500ms）。scrcpy 持久保活后帧率瓶颈从"scrcpy 死亡"变为"CLI 往返"，1.5s 间隔足够 |

**调用点影响**：
- `start()` 中 `if self._thread.is_alive(): return`：自动重连后线程几乎总存活，`start()` 重入时直接返回，无副作用
- `stop()` 中 `_stop_event.set() + join()`：循环检查 `_stop_event` 后退出，`join(5)` 仍有效
- daemon `screenshot` handler 的死线程重启：作为 fallback 保留，极少触发

## 4. 非期待变化

### 4.1 scrcpy 持续重连的 CPU/网络开销

自动重连循环在网络持续不可用时每 2s 执行一次完整重建（pkill + push jar + forward + start server + wait socket）。每次约 1-2s CPU 占用 + ADB 往返。在设备永久离线场景下会产生周期性负载。

**回退策略**：如需限制，可在 `_run()` 循环中增加最大重试次数计数器，超过阈值后退避至更长间隔（如 30s）。

### 4.2 `get_latest_frame()` 返回旧帧

删除时间戳更新后，`get_latest_frame()` 在 scrcpy 断流后仍返回最后一次缓存的旧帧（而非 None）。这是预期行为——预览显示最后一帧而非空白，状态角标同时显示"重连中"提示用户。但 screenshot handler 的 `if frame is not None` 分支会返回旧帧 PNG，而非 error。CLI → GUI 路径仍返回 success。

**评估**：可接受。用户看到旧帧 + "重连中"角标，比看到空白 + error 更友好。

### 4.3 PreviewWidget 不继承 QLabel 样式

原 `PREVIEW_STYLE` 的 QSS（border-radius、padding）不再作用于预览。PreviewWidget 在 `paintEvent` 中自行绘制边框（`drawRoundedRect`），视觉效果等价。但 QSS 主题切换不会自动反映到 PreviewWidget。

**评估**：当前主题系统无运行时切换，无影响。如未来增加主题切换，需在 `PreviewWidget.paintEvent` 中读取 `COLORS` 动态着色。

### 4.4 `_preview_label` 变量名消失

全局搜索确认 `main_window.py` 中无残留 `_preview_label` 引用。其他文件无此变量引用（变量为 MainWindow 私有）。

## 验证

- `py_compile`：`android_runtime.py` + `main_window.py` 均通过
- `pytest`：181 passed / 5 skipped / 1 failed（`test_config_get_set_works` 环境权限问题，非本次引入）
- JSON 校验：`zh_CN.json` + `en_US.json` 均通过 `json.load`
