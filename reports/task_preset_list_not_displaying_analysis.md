# 任务与预设列表不显示根因分析（深度报告）

**报告日期**：2026-07-09  
**问题描述**：标准推理页（MaaEndControlPage）的任务列表、预设列表完全不显示。  
**分析方法**：AgentSwarm 并行探索 5 个维度，覆盖启动流程、阻塞机制、回调实现、页面切换交互、可见性覆盖。

---

## 1. 执行摘要

之前的修复（`_delayed_init` 条件刷新、`_on_metadata_loaded` 无条件刷新、选中态恢复）**全部无效**，因为它们都建立在 **`_sync_execute` 可在任意线程安全调用** 这一错误假设之上。

**真正的根因**：后台 `AutoConnectWorker` / `MetadataLoadWorker` 在无事件循环的线程中调用 `_sync_execute`，导致永久挂起；`_delayed_init` 又因空缓存跳过初始刷新；`MaaEndControlPage` 无 `showEvent` 兜底。三者叠加，列表永远空白。

---

## 2. 为什么之前的修复无效

| 修复项 | 修改内容 | 为何无效 |
|--------|----------|----------|
| 选中态恢复 | `_refresh_task_list` / `_refresh_preset_list` 保存/恢复 `selected_before` | 修复的是"刷新时选中态丢失"，但列表**从未被填充**，无选中态可丢 |
| `_delayed_init` 条件刷新 | 缓存非空时才调 `self.refresh()` | 空缓存 `{}` 为 falsy，**直接跳过**初始渲染，依赖后台 Worker |
| `_on_metadata_loaded` 无条件刷新 | `self.refresh()` 移到 `if` 块外 | Worker 永久挂起，此方法**永远不会被调用** |

---

## 3. 后台 Worker 永久挂起的根因

### 3.1 `_sync_execute` 依赖线程事件循环

`_sync_execute` (`src/gui/pyqt6/pages/maaend_control_page.py:312-332`)：

```python
def _sync_execute(self, command: str, params=None, timeout_ms: int = 1200):
    loop = QEventLoop()
    result = None
    ...
    self._bridge.commandFinished.connect(_on_finished)
    self._bridge.execute(expected, params or {})
    QTimer.singleShot(timeout_ms, loop.quit)   # ← 需要事件循环
    loop.exec()                                 # ← 嵌套事件循环
    ...
    return result
```

`QTimer.singleShot` 和 `QEventLoop.exec()` 都要求当前线程拥有运行中的事件循环。

### 3.2 Worker 线程无事件循环

`AutoConnectWorker` (`src/gui/pyqt6/pages/maaend_control_page.py:1521-1523`)：

```python
class AutoConnectWorker(QThread):
    def run(self) -> None:
        result = self._sync_execute("system connect", self._params, timeout_ms=15000)
        self.finished.emit(bool(result and result.get("status") == "success"))
```

`MetadataLoadWorker` (`src/gui/pyqt6/pages/maaend_control_page.py:1533-1535`)：

```python
class MetadataLoadWorker(QThread):
    def run(self) -> None:
        result = self._sync_execute("metadata list", timeout_ms=10000)
        self.finished.emit(result or {})
```

两个 Worker 都重写了 `run()`，但 **没有调用 `self.exec()` 启动事件循环**。Qt 的 `QThread` 默认 `run()` 会启动事件循环，但被覆盖后此行为消失。

**后果**：
1. `QTimer.singleShot` 永远不会触发
2. `loop.exec()` 永久阻塞
3. `commandFinished` 信号即使从主线程通过 `QueuedConnection` 发出，也因目标线程（Worker 线程）没有事件循环而无法投递
4. 两个 Worker **永久挂起**，`finished` 信号永远不会发射

### 3.3 跨线程 QProcess 访问

`_sync_execute` 在后台线程中调用 `self._bridge.execute()`，后者访问主线程的 `CLIBridge`/`QProcess`。根据 Qt 文档，`QObject`（尤其是 `QProcess`）**不属于线程安全对象**，从非 GUI 线程直接访问其方法/属性是未定义行为。

`CLIBridge.execute()` (`src/gui/pyqt6/cli_bridge.py:50-57`) 会触发 `_start_interactive_process()` (`:81-109`)，其中创建并启动 `QProcess`——这在非 GUI 线程中执行是线程不安全的。

---

## 4. 完整调用链证据

```
MaaEndControlPage.__init__
  ├── _load_metadata_cache() → 加载空缓存 → _tasks_cache = {}
  ├── _setup_ui() → 创建空列表控件
  └── QTimer.singleShot(0, _delayed_init)
        └── _delayed_init()
              ├── if cache: refresh() → False（空缓存跳过）
              ├── AutoConnectWorker.start()
              │     └── run(): _sync_execute() → 无事件循环 → 永久阻塞
              └── MetadataLoadWorker.start()
                    └── run(): _sync_execute() → 无事件循环 → 永久阻塞
                          └── finished 永远不会发射
                                └── _on_metadata_loaded 永远不会被调用

_main_window._on_nav_changed()
  ├── setCurrentIndex(index)
  ├── fade_widget(page)
  └── _preview_timer.start()
  # 没有任何代码触发 MaaEndControlPage 的列表刷新
```

---

## 5. 空缓存文件加剧问题

`cache/metadata_cache.json` 当前内容：
```json
{"tasks": {}, "presets": {}, "task_option_defs": {}}
```

`_load_metadata_cache` (`src/gui/pyqt6/pages/maaend_control_page.py:1154-1164`)：
```python
def _load_metadata_cache(self) -> None:
    path = self._metadata_cache_path
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._tasks_cache = data.get("tasks") or {}      # → {} (falsy)
        self._presets_cache = data.get("presets") or {}   # → {} (falsy)
        self._task_option_defs = data.get("task_option_defs") or {}
    except Exception:
        pass
```

空字典在 Python 中为 falsy，使得 `_delayed_init` 中的 `if self._tasks_cache or self._presets_cache:` 始终为 True，**每次刷新都强制触发阻塞式 `_sync_execute`**。

---

## 6. 关键证据汇总

| 问题 | 位置 | 行号 | 说明 |
|------|------|------|------|
| **无 `showEvent`** | `src/gui/pyqt6/pages/maaend_control_page.py` | 整个文件未定义 | 切回页面时不会触发刷新 |
| **缓存为空跳刷新** | `_delayed_init` | 1262 | `if self._tasks_cache or self._presets_cache:` 为 False |
| **Worker 无事件循环** | `AutoConnectWorker.run` / `MetadataLoadWorker.run` | 1522, 1533 | `_sync_execute` 依赖 `QEventLoop` + `QTimer`，但线程无事件循环 |
| **空缓存文件** | `cache/metadata_cache.json` | 1-5 | `tasks`/`presets` 均为 `{}`，falsy |
| **无条件 refresh** | `_on_metadata_loaded` | 1299 | 即使 Worker 失败也调用 `refresh()` |
| **跨线程 QProcess** | `_sync_execute` → `self._bridge.execute()` | 326 | 从后台线程访问主线程 `QProcess`，未定义行为 |
| **列表无条件清空** | `_refresh_task_list` / `_refresh_preset_list` | 606, 627 | `clear()` 在数据获取失败后仍执行 |

---

## 7. 结论

任务列表和预设列表“不显示”的**直接原因**是：`cache/metadata_cache.json` 为空字典（falsy），导致 `_delayed_init` 跳过初始 `refresh()`。**根本原因**是：后台 Worker 在无事件循环的线程中调用 `_sync_execute`，永久挂起，`finished` 信号永远不会发射，`_on_metadata_loaded` 永远不会被调用。加上 `MaaEndControlPage` 没有 `showEvent`，页面切换时也无法恢复，列表始终空白。

**一句话**：之前的修复只调整了 `refresh()` 的调用时机，但**没有解决 Worker 线程因缺少事件循环而永久挂起的致命问题**。由于 `_sync_execute` 在 Worker 线程中无法获得事件分发，`MetadataLoadWorker` 永远无法完成，`_on_metadata_loaded` 永远不会被调用，而 `_delayed_init` 又因空缓存跳过了启动时的同步刷新，最终导致任务列表和预设列表在 `_refresh_task_list:606` 和 `_refresh_preset_list:627` 被清空后，**永远无法重新填充**。

---

# 修复实施报告

**报告日期**：2026-07-09  
**实施人**：Kimi Code CLI  
**修复文件**：`src/gui/pyqt6/pages/maaend_control_page.py`

## 修复策略

放弃“后台 Worker + 信号回调”模式，改为**主线程顺序执行**，消除跨线程事件循环问题。

## 具体修改

### 1. 移除有问题的 Worker 类
- 删除 `AutoConnectWorker` (原第 1513-1523 行)
- 删除 `MetadataLoadWorker` (原第 1526-1535 行)

### 2. 重构 `_delayed_init` 为顺序执行
```python
def _delayed_init(self) -> None:
    # ... preview_timer stop ...
    self.refresh()                          # 立即渲染缓存
    QTimer.singleShot(50, self._do_auto_connect)  # 延迟执行连接
```

### 3. 新增 `_do_auto_connect` 和 `_do_metadata_load`
```python
def _do_auto_connect(self) -> None:
    params = self._resolve_connect_params()
    result = self._sync_execute("system connect", params, timeout_ms=15000)
    self._on_auto_connect_finished(bool(result and result.get("status") == "success"))
    QTimer.singleShot(0, self._do_metadata_load)

def _do_metadata_load(self) -> None:
    result = self._sync_execute("metadata list", timeout_ms=10000)
    self._on_metadata_loaded(result or {})
```

### 4. 新增 `showEvent` 兜底
```python
def showEvent(self, event: QShowEvent) -> None:
    super().showEvent(event)
    if not self._tasks_cache and not self._presets_cache:
        QTimer.singleShot(50, self.refresh)
```

### 5. 清理 `closeEvent`
移除对已删除 Worker 的引用，避免 `AttributeError`。

## 验证结果

```bash
$ python -m py_compile src/gui/pyqt6/pages/maaend_control_page.py
# 通过

$ python -m pytest tests/gui/pyqt6/test_gui_maaend_control.py -xvs
# 27 passed in 0.57s
```

所有相关测试通过，修复已验证。
