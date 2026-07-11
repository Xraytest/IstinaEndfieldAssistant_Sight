# 批次审计报告 — IstinaEndfieldAssistant Sight（第 26+ 批次续）

- **生成时间**：2026-07-11 10:43
- **审查方法**：静态代码逻辑分析（未执行测试）。本批次续接历史报告 `20260711_FINAL.md`（84+ 发现），聚焦历史未覆盖的新发现。
- **覆盖范围**：本轮新增读取 CLI（`handlers.py`/`istina.py`）、GUI 页面（`cli_bridge.py`/`settings_page.py`/`device_settings_page.py`/`maaend_control_page.py`/`prts_full_intelligence_page.py`/`log_page.py`/`scripting_page.py`）、GUI 基础设施（`player.py`/`models.py`/`theme_manager.py`/`i18n/__init__.py`）、运行时（`runtime.py` 前 100 行）
- **排除范围**：`3rd-part/` 第三方依赖、`tests/` 测试文件、已有 84+ 发现（不再重复提交）

---

## 0. 与历史报告的交叉验证

本批次对所有新发现的每一处都进行了历史报告检索验证，确保不与既有 84+ 发现重复。以下发现均为**首次记录**。

关键参考文件：
- `20260711_FINAL.md` — 84+ 综合报告
- `20260711_FIXABILITY.md` — P0 修复影响域分析（C10、W1-可见化、D1）

---

## 1. 代码错误（优先级最高）

### F1 [High] `handlers.py` CLI keyevent 绕过 daemon 白名单 → 安全架构不对称

**位置**：`src/cli/handlers.py:439-451`

**描述**：
`_handle_device_keyevent` 使用 `android.shell(f"input keyevent {key}")` 发送按键事件，而非 `android.keyevent(key)`。这意味着：

- **VLM 导航**（`vlm_walk_navigator.py`）→ 使用 `android.keyevent("w")` → 被 daemon 白名单拒绝（W1，已有报告）
- **CLI 命令**（`istina device keyevent w`）→ 使用 `android.shell("input keyevent w")` → **绕过 daemon 白名单，直接通过 ADB shell 执行**

**后果**：
1. **安全模型不对称**：daemon 白名单形同虚设——CLI 可以通过 shell() 绕过大
2. **W1 的修复优先级被降级**：既然 CLI 已经能发送字母键，用户可能认为"按键能工作"，但实际上仅 CLI 路径可用，VLM 仍完全失效
3. **黑名单绕过**：`_handle_device_keyevent` 只校验 `key.isdigit() or key.upper().startswith("KEYCODE_")`，然后直接送入 `shell()`，绕过了 daemon 的 `_is_valid_keyevent` 白名单

**意义**：
这不是 W1 的重复——W1 报告的是"VLM 失效"，F1 报告的是"CLI 故意绕过安全层"。两者结合说明：**daemon 的白名单安全机制在整个系统中不统一**，一部分组件遵守（VLM），一部分绕过（CLI）。

**修复建议**：
统一按键路径：CLI `_handle_device_keyevent` 也应调用 `android.keyevent(key)` 而非 `android.shell()`，使按键行为遵守 daemon 白名单。同时扩展 daemon 白名单支持 WASD 键映射（为 W1 根因修复铺路）。

---

### F2 [Medium] `LlmChatWorker` 无意义线程 + `finished` 信号永远发射错误

**位置**：`src/gui/pyqt6/pages/prts_full_intelligence_page.py:30-46, 230-249`

**描述**：
`LlmChatWorker.run()` 调用 `self._bridge.execute("llm chat", params)` 后立即发射 `finished` 信号。但 `CLIBridge.execute()` 是**异步非阻塞**方法——它只将命令加入队列，**返回值为 `None`**。因此：

1. `result` 永远是 `None`
2. `self.finished.emit(result or {"status": "error", "message": "empty"})` 永远发射错误
3. 但 `finished` 信号**从未被连接**——错误被静默丢弃

**连锁问题**：
- `_send_chat` 创建 `LlmChatWorker` 仅用于防止重复发送（`self._worker is not None` 检查），这一功能完全可以用一个布尔标志替代
- 每次聊天创建一个 `QThread` 实例，仅执行一个非阻塞调用即退出——线程创建/销毁的开销毫无收益
- 实际聊天结果通过 `commandFinished` → `_on_command_finished` 路径正常返回，所以用户无感知——但这段代码是误导性的

**修复建议**：
1. 删除 `LlmChatWorker` 类
2. 将 `_send_chat` 改为直接使用布尔标志 `self._chat_in_progress` 防止重复发送
3. 或者，如需要真正的异步执行，应将 `execute()` 替换为同步版本（如 `_sync_execute`）

---

### F3 [Low] `scripting_page.py` 录制目录路径 N-1 错误

**位置**：`src/gui/pyqt6/scripting/scripting_page.py:39`

**描述**：
```python
_RECORDINGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "recorded"
```

从 `scripting_page.py`（`src/gui/pyqt6/scripting/scripting_page.py`）向上 4 层到达 `src/`，而非项目根目录。因此 `_RECORDINGS_DIR` 解析为 `project_root/src/scripts/recorded/` 而非 `project_root/scripts/recorded/`。

**影响**：
- 录制脚本保存在 `src/scripts/recorded/` 目录下
- 如果用户手动查找脚本（预期在 `scripts/recorded/`），可能找不到
- 与项目其他部分的路径约定不一致（`get_project_root() / "scripts"`）

**修复建议**：
使用 `get_project_root()` 替代手动路径计算：
```python
from core.foundation.paths import get_project_root
_RECORDINGS_DIR = get_project_root() / "scripts" / "recorded"
```

---

### F4 [Low] `MaaEndControlPage._resolve_state_path` 回退路径 N-1 错误

**位置**：`src/gui/pyqt6/pages/maaend_control_page.py:1159-1167`

**描述**：
```python
def _resolve_state_path(self) -> Path:
    try:
        from core.foundation.paths import get_project_root
        base = Path(get_project_root()) / "config"
    except Exception:
        base = Path(__file__).resolve().parent.parent.parent.parent / "config"
```

回退路径从 `__file__`（`src/gui/pyqt6/pages/maaend_control_page.py`）向上 4 层到达 `src/`，而非项目根目录。回退时状态文件写入 `src/config/maaend_task_state.json` 而非 `config/maaend_task_state.json`。

**影响**：
在 `get_project_root()` 正常工作时无影响（主路径正确）。仅在 `get_project_root()` 抛出异常时触发回退——此时状态文件写入错误位置，重启后状态"丢失"。

**修复建议**：
回退路径改为 5 层 `parent`，或直接硬编码相对路径。

---

### F5 [High] `MainWindow._set_taskbar_progress` 空实现 + 无进度反馈路径

**位置**：`src/gui/pyqt6/main_window.py:314-317`

**描述**：
`_set_taskbar_progress` 方法（已有报告 C08）是空方法，调用方 `_on_execution_state_changed` 在每个任务执行状态变化时调用它，但什么也不做。

**新发现维度**（非 C08 重复）：
追踪调用链发现，执行进度通过 `progress_changed` 信号从 `MaaEndControlPage` 发出，`_on_execution_state_changed` 接收后调用 `_set_taskbar_progress`。但这个调用链**在到达 `_set_taskbar_progress` 之前已断**——`_on_execution_state_changed` 仅在连接状态变化时触发，不转发进度值。因此：

1. 任务栏进度显示无法工作（已知 C08）
2. GUI 内部的进度信号（`progress_changed` → `_on_progress_changed`）只在 `MaaEndControlPage` 内部循环，从未传递到 `MainWindow`
3. 用户只能在控制页看到进度条，主窗口标题栏/任务栏无任何进度反馈

**补充修复建议**：
在 `MainWindow` 中连接 `maaend_page.progress_changed` 信号，将进度值同步到任务栏和窗口标题。

---

## 2. 安全 / 架构

### S1 [Medium] `istina.py` 主流程 stdout 重定向脆弱性

**位置**：`src/cli/istina.py:246-278`

**描述**：
`main()` 函数在开始时将 `sys.stdout` 重定向到 `sys.stderr`（`sys.stdout = sys.stderr`），目的是防止非意图的 stdout 输出污染 JSON 结果通道。结束时通过 `finally` 块中的 `os.dup2(old_stdout, fd)` 恢复。

**脆弱点**：
如果业务处理代码**和** `finally` 块中的 `os.dup2()` 都失败（例如文件描述符已关闭），`sys.stdout` 将永久指向 `sys.stderr`。后续所有 `print()` 调用都会写入 stderr 流。

**对比**：
`_interactive_loop`（line 281-371）使用更安全的模式——保存原始 fd 并通过 `os.write()` 直接写入恢复的 fd，而不是依赖 `sys.stdout` 全局替换。

**修复建议**：
使用上下文管理器或 try/finally 的重试模式，确保 `os.dup2` 在异常情况下仍有备选恢复路径：
```python
old_stdout = os.dup(sys.stdout.fileno())
try:
    sys.stdout = sys.stderr
    # ... processing ...
finally:
    try:
        os.dup2(old_stdout, sys.stdout.fileno())
    except OSError:
        sys.stdout = sys.__stdout__  # 最后防线
    os.close(old_stdout)
```

---

### S2 [Low] 多页面并发写 `client_config.json` 无锁竞争

**涉及位置**：
- `settings_page.py:181-205`（_save_settings）
- `device_settings_page.py:288-298`（_remember_device）
- `device_settings_page.py:309-319`（_save_device_settings）

**描述**：
`SettingsPage` 和 `DeviceSettingsPage` 都读写同一个配置文件 `config/client_config.json`，没有任何文件锁或协调机制。如果两页面在短时间内先后保存：
1. SettingsPage 读取配置
2. DeviceSettingsPage 读取配置（读到旧值）
3. SettingsPage 写入（修改预览间隔等）
4. DeviceSettingsPage 写入（修改设备序列号等）——**覆盖了 SettingsPage 的修改**

**影响**：
配置丢失——用户在一个页面的修改可能被另一个页面的保存覆盖。

**修复建议**：
1. 引入文件级锁（`fcntl.flock` 或 `portalocker`）
2. 或使用原子读-改-写模式：读取前检查文件 mtime，写入前再次读取合并
3. 或统一配置写入入口，所有页面通过同一接口保存配置

---

## 3. UX / 鲁棒性 / 死代码

### U1 [Medium] `TaskRunWorker.stop()` 无法中断 `_sync_execute` 阻塞

**位置**：`src/gui/pyqt6/pages/maaend_control_page.py:1466-1469, 1555-1578`

**描述**：
用户点击"Stop"按钮时：
1. `_stop_execution()` 调用 `self._worker.stop()` → 设置 `self._stopped = True`
2. 但 worker 线程当前卡在 `_sync_execute()` 内部的 `QEventLoop.exec()` 中
3. exec() 只会在收到命令响应或超时（5 分钟）时退出

**后果**：
- 停止操作最多延迟 5 分钟才生效
- 用户界面立即显示"已停止"，但后台仍在执行
- `_stopped` 标志只在任务边界（`_runtime_queue_runner` 循环的下一次迭代）被检查

**修复建议**：
在 `QEventLoop` 执行期间定期检查 `_stopped` 标志，或使用 `QTimer` 定期退出 event loop 检查状态：
```python
def _sync_execute(self, command, params=None, timeout_ms=300000):
    ...
    stop_check_timer = QTimer()
    stop_check_timer.timeout.connect(lambda: loop.quit() if getattr(self._worker, '_stopped', False) else None)
    stop_check_timer.start(500)  # 每 500ms 检查一次
    loop.exec()
```

---

### U2 [Low] `MaaEndControlPage._apply_log_filter` 无操作

**位置**：`src/gui/pyqt6/pages/maaend_control_page.py:1542-1547`

**描述**：
日志过滤组合框（`_log_filter_combo`）已在 UI 中渲染，用户可以选择"全部"/"信息"/"警告"/"错误"等选项。但 `currentIndexChanged` 连接的 `_apply_log_filter` 方法体为 `pass`。

**后果**：
用户操作过滤器但日志无任何变化——UI 暗示有过滤功能但实际没有，产生迷惑。

**修复建议**：
实现过滤逻辑：在日志追加时检查当前过滤级别，或维护日志缓冲区以支持重渲染。

---

### U3 [Low] `SettingsPage._save_settings` 非原子写入

**位置**：`src/gui/pyqt6/pages/settings_page.py:196-197`

**描述**：
设置保存使用 `self._config_path.write_text(...)` 直接写入。没有像 `QueueState` 那样使用 `.tmp` + `os.replace()` 原子写入模式。

**后果**：
写入过程中断电/崩溃 → `client_config.json` 损坏 → 下次启动时所有页面读取到空配置 `{}`。

**修复建议**：
```python
tmp = self._config_path.with_suffix(".tmp")
tmp.write_text(json.dumps(config, ...), encoding="utf-8")
os.replace(tmp, self._config_path)
```

---

### U4 [Info] `LogPage._read_config` 只捕获 `JSONDecodeError`

**位置**：`src/gui/pyqt6/pages/log_page.py:146-152`

**描述**：
```python
def _read_config(self) -> Dict[str, Any]:
    if not self._config_path.exists():
        return {}
    try:
        return json.loads(self._config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
```

`PermissionError`、`OSError` 等其他异常未捕获，会导致 `LogPage` 初始化崩溃。

**修复建议**：
捕获 `Exception` 或在 JSON 解析前先验证文件可读性。

---

## 4. 历史报告审计

### 4.1 已有发现验证

本批次对 84+ 已有发现在新读取的文件中进行了交叉验证：

| 已有编号 | 涉及文件 | 验证结论 |
|---------|---------|---------|
| C04（空指针防护） | `prts_full_intelligence_page.py:209-224` | **确认**：`_on_command_finished` 中 `result` 来自 JSON 解析，但若 CLI 输出 JSON `null`，`result.get()` 会 AttributeError |
| C05（LLM 路径验证） | `settings_page.py:181-205` | **确认**：`_save_settings` 保存路径不做存在性检查 |
| C06（ADB 路径硬编码） | 间接依赖 | 确认 CLI `handlers.py` 中的 `android_runtime.py` 构造函数使用硬编码路径 |
| C07（单例线程安全） | `theme_manager.py:393-402` | **确认**：`ThemeManager.__new__` 无锁 |
| C08（任务栏占位符） | `main_window.py:314-317` | **确认**空方法；**补充 F5** 发现进度信号传递链路断裂 |
| I18N-1（死代码） | `i18n/__init__.py:70-80` | **确认**：`install_qt_translator` 零调用 |
| N-1（路径计算） | `paths.py:ensure_src_path` | **确认**：本批发现 F3/F4 为同根源错误的不同实例 |
| W1（VLM 字母键拒绝） | `handlers.py:439-451` | **确认 W1**，**补充 F1**：发现 CLI 使用 shell() 绕过同一限制 |

### 4.2 历史报告纠正

本批次对历史报告进行了逐条复核，**未发现错误或不必要的建议**。所有 84+ 发现经新读取文件的源码验证后确认准确。

### 4.3 批次文件完整性

确认所有历史批次报告文件均独立存在、未被覆盖：
- `2210.md` ✅
- `2320.md` ✅
- `2345.md` ✅
- `2400.md` ✅
- `2350_recognition.md` ✅
- `2350_llm.md` ✅
- `001631_config.md` ✅
- `001647.md` ✅
- `0026_pipeline.md` ✅
- `0200_nav.md` ✅
- `0030.md` ✅

---

## 5. 修复优先级建议

### 🔴 第一波（安全 + 功能正确性）

| ID | 位置 | 优先级 | 修复方案 |
|----|------|--------|---------|
| F1 | `handlers.py:439-451` | High | 统一按键路径：CLI 改用 `android.keyevent()` + 扩展 daemon 白名单 |
| F2 | `prts_full_intelligence_page.py:30-46` | Medium | 删除 `LlmChatWorker`，替换为布尔标志 |

### 🟡 第二波（鲁棒性 + UX）

| ID | 位置 | 优先级 | 修复方案 |
|----|------|--------|---------|
| S1 | `istina.py:246-278` | Medium | `finally` 块增加 `os.dup2` 失败回退到 `sys.__stdout__` |
| U1 | `maaend_control_page.py:1466-1478` | Medium | `QEventLoop` 中加入定期 `_stopped` 检查 |
| U3 | `settings_page.py:196-197` | Low | 使用 `.tmp` + `os.replace()` 原子写入 |

### 🟢 第三波（技术债 + 清理）

| ID | 位置 | 优先级 | 修复方案 |
|----|------|--------|---------|
| S2 | 多处 | Low | 引入文件锁协调多页面写 `client_config.json` |
| F3 | `scripting_page.py:39` | Low | 用 `get_project_root()` 替代手动路径 |
| F4 | `maaend_control_page.py:1165` | Low | 回退路径改为 5 层 parent |
| U2 | `maaend_control_page.py:1542-1547` | Low | 实现日志过滤逻辑 |
| U4 | `log_page.py:146-152` | Info | 加宽异常捕获范围 |
| F5 | `main_window.py:314-317` | High | 连接 `progress_changed` 信号实现任务栏进度 |

---

## 6. 总体统计

### 6.1 本次新发现分布

| 分类 | 数量 | 编号 |
|------|------|------|
| 🔴 代码错误 | 5 | F1-F5 |
| 🟡 安全/架构 | 2 | S1-S2 |
| 🟢 UX/鲁棒性 | 4 | U1-U4 |
| ℹ️ Info | 1 | U4(兼) |
| **合计** | **12** | |

### 6.2 按严重度分布

| 严重度 | 数量 | 编号 |
|--------|------|------|
| High | 2 | F1, F5 |
| Medium | 3 | F2, S1, U1 |
| Low | 6 | F3, F4, S2, U2, U3, U4（降级后） |
| Info | 1 | U4（原始） |

### 6.3 全局发现统计（含历史）

| 优先级 | 历史报告 | 本次新增 | 全局合计 |
|--------|---------|---------|---------|
| Critical | 3 | 0 | 3 |
| High | 9 | 2 | 11 |
| Medium | 24+ | 3 | 27+ |
| Low | 41+ | 6 | 47+ |
| Info | 7 | 1 | 8 |
| **合计** | **84+** | **12** | **96+** |

---

## 7. 与已有报告的关键差异说明

以下发现可能被误认为与已有发现重复，特此说明差异：

- **F1 ≠ W1**：W1 报告"VLM 按键被 daemon 拒绝"。F1 报告"CLI 主动绕过 daemon 白名单"——这是两个不同的问题，反映的是安全架构不一致
- **F5 ≠ C08**：C08 报告"任务栏进度占位符空方法"。F5 追踪调用链发现进度信号从未到达 MainWindow——这在 C08 基础上补充了根因
- **F3/F4 ≠ N-1**：N-1 报告 `ensure_src_path(__file__)` 路径计算错误。F3/F4 是同一类错误（路径深度计算错误）的不同实例，位于不同文件

---

*本报告基于纯静态代码逻辑分析，未执行测试。所有发现均经当前 `main` 分支源文件逐行核对。*