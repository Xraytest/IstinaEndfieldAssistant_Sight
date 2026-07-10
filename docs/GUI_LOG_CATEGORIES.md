# GUI 日志分类说明

本文档梳理 IstinaEndfieldAssistant Sight 图形界面（PyQt6）中**实时展示**的日志类别。
GUI 内共有 **4 个**独立的日志展示面，各自分类维度不同。

> 注：文件级持久日志（`main.log` / `qt.log`）通过「Logs」页查看，其分类规则见第 4 节。

---

## 总览

| # | 展示面 | 代码位置 | 分类维度 | 来源标签/发言方 |
|---|--------|----------|----------|-----------------|
| 1 | 标准推理页「执行日志」 | `src/gui/pyqt6/pages/maaend_control_page.py:529` (`_log_text`) | 按来源标签 source | 系统 / 队列 / 预设 / CLI / ERROR |
| 2 | PRTS 全智能页「对话输出」 | `src/gui/pyqt6/pages/prts_full_intelligence_page.py:125` (`_chat_output`) | 按发言方 | 系统 / User / LLM |
| 3 | 设备连接页「连接日志」 | `src/gui/pyqt6/pages/device_settings_page.py:130` (`_log_text`) | 按日志性质（多为无标签纯文本 + CLI 透传） | （无内置标签）/ CLI |
| 4 | Logs 页「日志文件查看器」 | `src/gui/pyqt6/pages/log_page.py` | 按文件 + 级别 | 见第 4 节 |

---

## 0. 日志路由机制（避免跨区刷屏）

`CLIBridge` 在交互模式下运行 `istina.py`，而 CLI 把 stdout fd 重定向到 stderr
（`cli/istina.py:294`），因此 MaaFW/ADB/框架日志全部汇入子进程 stderr。
桥接层对每行 stderr 做分类（`cli_bridge.py` `_classify_stderr_line`）后，
通过唯一的 `logMessage(category, message)` 信号下发：

- **ADB** → 仅设备连接页「连接日志」展示
- **MES** → 仅标准推理页「执行日志」展示
- **Qt 噪声**（`qt.qpa` / `qfont` 等）→ **丢弃**（GUI 进程的 Qt 日志已由 `qt_log_filter.py` 写入 `qt.log`）

各日志页在槽函数中再做二次过滤（执行页忽略 `ADB`，设备页仅接受 `ADB`），
**确保同一份底层日志只出现在一个面板**，消除跨区重复刷屏。

---

## 1. 标准推理页 — 执行日志（实时流）

所有条目经 `_append_log(source, text)` 写入，格式为 `[source] 文本`
（`maaend_control_page.py:1530`）。出现的来源标签：

| 来源标签 | 含义 | 典型内容 | 代码位置 |
|----------|------|----------|----------|
| **系统** | 连接与执行生命周期 | `Connecting to MaaEnd runtime...`、`MaaEnd runtime connected`、`Start execution`、`Execution finished`、`Retry N/Max`、`Auto-connect succeeded/failed`、预览断连提示 | `:1317`–`:1479`、`:340` |
| **队列** | 任务队列动作 | `Added {name}`、`Executing {name} (N/Total)`、`{name} -> Success/Failed (N/Total)` | `:819`、`:829`、`:1394` |
| **预设** | 预设应用 | `Applied preset '{name}' (N tasks)` | `:704`、`:1435` |
| **MES** | MaaEnd 子进程 stderr 透传（框架日志） | MaaFW/MES 的 C++ 框架日志、CLI 子进程内 Python WARNING 级以上日志（经 `CLIBridge.logMessage` 信号，类别已分类为 `MES`） | `cli_bridge.py` `_classify_stderr_line` |
| **ERROR** | 工作线程未捕获异常 | `TaskRunWorker.run()` 抛出的异常堆栈/信息 | `maaend_control_page.py:1569` |

**配色规则**：`系统` 用蓝色（`BLUE_STYLE`），其余用 `VAL_STYLE`（`maaend_control_page.py:1531`）。

**过滤**：下拉框选项为 `All / Info / Warning / Error`（`maaend_control_page.py:540`），
但 `_apply_log_filter` 当前为空占位（`maaend_control_page.py:1539`），**尚未真正按级别过滤**。

---

## 2. PRTS 全智能页 — 对话输出（实时流）

经 `_append_chat(source, text)` 写入，格式为 `[source] 文本`
（`prts_full_intelligence_page.py:267`）。此页为 VLM 对话流，按发言方区分：

| 发言方 | 含义 | 典型内容 |
|--------|------|----------|
| **系统** | 流程状态 | `Starting LLM...`、`Stopping LLM...`、错误提示 |
| **User** | 用户输入 | 用户输入的 prompt，或纯图片时显示 `[Image]` |
| **LLM** | 模型返回 | VLM 推理结果文本 |

---

## 3. 设备连接页 — 连接日志（实时流）

经 `_append_log(message)`（无来源标签）与 `_on_log_message(source, message)` 写入
（`device_settings_page.py:244`、`:250`）。与执行日志不同，**本页大多为无标签纯文本**，
仅来自 CLI 子进程 stderr 的内容会带 `[CLI]` 前缀。

| 类别 | 含义 | 典型内容 | 代码位置 |
|------|------|----------|----------|
| 连接请求 | 用户主动发起 | `Request connect: {serial}`、`Request disconnect: ...`、地址为空提示 | `:163`、`:166`、`:171` |
| 连接结果 | 命令返回 | `Connect result: {result}`、`Disconnect result: {result}` | `:187`、`:201` |
| 设备刷新 | 设备列表更新 | `Devices refreshed, N found.`、`Failed to refresh devices: ...` | `:228`、`:235` |
| 命令失败 | 桥接层错误 | `Command failed: {command} {message}` | `:218` |
| 自动重连 | 断线重连尝试 | `Auto-reconnect attempt: {serial}` | `:151` |
| **ADB** | stderr 透传（仅 ADB 诊断，带 `[ADB]` 前缀） | ADB 输出 / `adb` 相关诊断；含 `killing ADB`/`杀死ADB` 时联动状态栏提示 | `:250`–`:253` |

**配色**：本页 `_log_text` 使用默认 `LOG_STYLE`，**未做按来源/级别的着色**，所有行为纯文本追加。

---

## 4. Logs 页 — 日志文件查看器（文件级）

不做运行时流，读取 `logs/` 目录下所有 `.log` / `.txt` 文件
（`log_page.py:89` `_refresh_file_list`）。当前项目实际产生的文件：

### 4.1 文件清单

| 文件 | 内容来源 | 说明 |
|------|----------|------|
| **main.log** | `init_logger` 创建的根 logger 全量文件日志（`core/foundation/logger.py:126`） | 所有模块、所有级别 |
| **qt.log** | `qt_log_filter.py` 用 `qInstallMessageHandler` 重定向的 Qt 日志 | 仅良性字体/调试/信息类警告；`QtCritical/QtFatal` 仍写 stderr 并进入 main.log |

### 4.2 main.log 中的模块类别标记

`ProjectLogger._format` 会把 `LogCategory` 枚举前缀化为 `[类别]`（`logger.py:43`–`:53`）：

| 类别标记 | 含义 |
|----------|------|
| `[MAIN]` | 主流程 / MaaEnd runtime / 连接与资源加载 |
| `[ADB]` | ADB 设备通信 |
| `[COMMUNICATION]` | 进程间 / 网络通信 |
| `[EXECUTION]` | 任务执行 |
| `[AUTHENTICATION]` | 鉴权 |
| `[GUI]` | GUI 主线程 / 预览 / 桥接 |
| `[EXCEPTION]` | 异常 |
| `[PERFORMANCE]` | 性能 |

此外每行还含 Python logger 名（如 `gui.pyqt6.main_window`、`core.service.maa_end.runtime`）。

### 4.3 级别高亮（HTML 着色）

`log_page.py:30` `_LOG_LEVEL_COLORS`：

| 级别 | 颜色 |
|------|------|
| `INFO` | 主色蓝 |
| `WARN` | 橙 `#ffb84d` |
| `ERROR` | 红 `#ff4d4d` |
| `DEBUG` | 灰 `#8b919e` |
| `TRACE` | 灰 `#a6a9b0` |

同时高亮时间戳 `YYYY-MM-DD HH:MM:SS`。

---

## 5. 非日志流（瞬时提示，非持久）

- **状态栏**：`main_window.py:64` `statusBar().showMessage("Ready")`，瞬时状态文本。
- **系统托盘 / 弹窗**：CLI 连续崩溃 5 次弹 `QMessageBox`（`cli_bridge.py:233`）、
  GPU 不支持/低显存弹窗（`main_window.py:100`），属告警而非日志流。

---

## 6. 分类维度汇总

GUI 日志按用户关心的维度可归为三大类：

1. **按来源/发言方分**：
   - 执行页：系统 / 队列 / 预设 / CLI / ERROR
   - 对话页：系统 / User / LLM
   - 设备页：无标签纯文本 / CLI
2. **按模块分**：`[MAIN] [ADB] [COMMUNICATION] [EXECUTION] [AUTHENTICATION] [GUI] [EXCEPTION] [PERFORMANCE]`（main.log）
3. **按级别分**：`INFO / WARN / ERROR / DEBUG / TRACE`（Logs 页高亮；qt.log 按严重度分流）

> 待完善：执行页的级别过滤（`_apply_log_filter`）目前为空实现，如需真正按级别过滤需补全。
