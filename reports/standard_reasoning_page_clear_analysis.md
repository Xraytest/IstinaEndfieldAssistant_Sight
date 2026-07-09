# 标准推理页内容被清空根因分析

**报告日期**：2026-07-09  
**问题描述**：标准推理页（MaaEndControlPage）的任务列表、预设列表、选项编辑器内容会在用户切换到别的页面一段时间并执行一定操作后被清空。

## 1. 根因分析

### 1.1 直接原因

`MaaEndControlPage._refresh_task_list()` 与 `_refresh_preset_list()` 在刷新前对列表控件执行了 `self._task_list.clear()` / `self._preset_list.clear()`。

`QListWidget.clear()` 会触发 `itemSelectionChanged` 信号，槽函数 `_on_task_selected()` / `_on_preset_selected()` 将选中态置为 `None`。随后列表重新填充，但恢复选中态的代码：

```python
if self._selected_task in self._tasks_cache:
    matches = ...
```

因 `_selected_task` 已被置为 `None`，条件不成立，选中态无法恢复。若此时 `_tasks_cache` / `_presets_cache` 为空，列表最终表现为空。

### 1.2 根本原因

内容被清空不是由“页面切换”触发的，而是由 **异步元数据加载完成后的二次刷新** 触发的。

调用链如下：

```
MaaEndControlPage.__init__
  └── QTimer.singleShot(0, self._delayed_init)
        └── _delayed_init()
              ├── self.refresh()                    # [1] 首次刷新，阻塞式 metadata list
              ├── start AutoConnectWorker
              └── start MetadataLoadWorker
                    └── run(): _sync_execute("metadata list")  # 后台线程
                          └── finished → _on_metadata_loaded()
                                └── self.refresh()    # [2] 二次刷新，异步回调
```

**关键时序**：

1. 启动时 `_delayed_init()` 在主线线程调用 `self.refresh()`（`refresh()` → `_refresh_task_list()` → 若缓存为空则阻塞式调用 `_sync_execute("metadata list")`）。
2. 同时，`MetadataLoadWorker` 在后台线程执行 `_sync_execute("metadata list")`。
3. 当用户已切换到其他页面后，后台 `MetadataLoadWorker` 完成，主线程执行槽函数 `_on_metadata_loaded()`。
4. `_on_metadata_loaded()` **无条件**调用 `self.refresh()`。
5. `refresh()` → `_refresh_task_list()` / `_refresh_preset_list()` → `clear()` → 选中态丢失 → 若缓存为空或加载失败，列表被清空且无法恢复选中。

### 1.3 加剧因素

1. **`cache/metadata_cache.json` 为空**
   当前文件内容为：
   ```json
   {"tasks": {}, "presets": {}, "task_option_defs": {}}
   ```
   空字典在 Python 中为 falsy，导致 `_refresh_task_list()` 每次刷新都触发阻塞式 `_sync_execute("metadata list", timeout_ms=10000)`。

2. **`_on_metadata_loaded()` 无条件刷新**
   无论后台加载成功与否，都会调用 `self.refresh()`。若加载失败或返回空结果，列表被清空且无法恢复。

3. **`_sync_execute` 默认超时过短（1200ms）**
   非执行类命令（如 `metadata list`）在 GUI 嵌套事件循环中被 1200ms 默认超时约束，极易超时，导致后台 worker 返回空结果。

4. **`_build_option_editor()` 清除选项控件**
   `refresh()` 最后通过 `QTimer.singleShot(0, self._build_option_editor)` 重建选项编辑器，清空所有动态生成的 option widget，导致选项区域在刷新期间短暂（或最终）显示 "Please select a task first" 提示。

### 1.4 调用链证据

| 调用起点 | 调用路径 | 触发条件 |
|---------|---------|---------|
| `__init__` | `_delayed_init()` → `self.refresh()` | 启动时，由 `QTimer.singleShot(0, ...)` 触发 |
| `MetadataLoadWorker` | `_on_metadata_loaded()` → `self.refresh()` | 后台线程完成 metadata list 后异步触发 |
| `set_bridge()` | `self.refresh()` | 当前代码中无外部调用（死代码） |

`MaaEndControlPage` 本身无 `showEvent` / `hideEvent` 重写，**页面切换本身不会触发清空**。清空一定来自上述异步回调。

## 2. 修改方案

### 2.1 修复选中态丢失（P0）

在 `_refresh_task_list` 与 `_refresh_preset_list` 中，`clear()` 前后保存并恢复选中项。

**修改位置**：
- `src/gui/pyqt6/pages/maaend_control_page.py:599` `_refresh_task_list`
- `src/gui/pyqt6/pages/maaend_control_page.py:617` `_refresh_preset_list`

**修改内容**：

```python
def _refresh_task_list(self):
    selected_before = self._selected_task
    if not self._tasks_cache:
        result = self._sync_execute("metadata list", timeout_ms=10000)
        ...
    self._task_list.clear()
    for name in sorted(self._tasks_cache.keys()):
        item = QListWidgetItem(_zh(name))
        item.setData(Qt.ItemDataRole.UserRole, name)
        self._task_list.addItem(item)
    if selected_before and selected_before in self._tasks_cache:
        matches = self._task_list.findItems(_zh(selected_before), Qt.MatchFlag.MatchExactly)
        if matches:
            self._task_list.setCurrentItem(matches[0])
    # 若恢复失败且之前有选中项，回退 _selected_task
    if selected_before and not self._task_list.currentItem():
        self._selected_task = selected_before
```

`_refresh_preset_list` 同理。

### 2.2 避免无条件刷新（P1）

修改 `_on_metadata_loaded()`，仅在加载成功且数据有效时调用 `refresh()`。

**修改位置**：
- `src/gui/pyqt6/pages/maaend_control_page.py:1267` `_on_metadata_loaded`

**修改内容**：

```python
def _on_metadata_loaded(self, result: dict) -> None:
    if result and result.get("status") == "success":
        new_tasks = result.get("tasks") or {}
        new_presets = result.get("presets") or {}
        new_defs = result.get("task_option_defs") or {}
        if new_tasks != self._tasks_cache or new_presets != self._presets_cache:
            self._tasks_cache = new_tasks
            self._presets_cache = new_presets
            self._task_option_defs = new_defs
            self._persist_metadata_cache()
            self.refresh()
```

这样：
- 加载失败时不刷新列表，保留现有内容。
- 数据未变化时不重复刷新，避免不必要的 `clear()`。

### 2.3 避免启动期阻塞式刷新（P2）

修改 `_delayed_init()`，缓存非空时才在主线程同步刷新，避免阻塞 GUI。

**修改位置**：
- `src/gui/pyqt6/pages/maaend_control_page.py:1232` `_delayed_init`

**修改内容**：

```python
def _delayed_init(self) -> None:
    preview_timer.stop()
    if self._tasks_cache or self._presets_cache:
        self.refresh()
    # 启动后台 worker 加载最新元数据
    self._auto_connect_worker = AutoConnectWorker(
        self._sync_execute, self._resolve_connect_params()
    )
    ...
```

## 3. 影响面

### 3.1 直接涉及

| 文件 | 函数/方法 | 影响 |
|-----|----------|------|
| `src/gui/pyqt6/pages/maaend_control_page.py` | `_refresh_task_list` | 修复选中态丢失 |
| `src/gui/pyqt6/pages/maaend_control_page.py` | `_refresh_preset_list` | 修复选中态丢失 |
| `src/gui/pyqt6/pages/maaend_control_page.py` | `_on_metadata_loaded` | 避免失败时无条件清空列表 |
| `src/gui/pyqt6/pages/maaend_control_page.py` | `_delayed_init` | 避免缓存非空时仍阻塞主线程 |

### 3.2 信号与调用点

- `_refresh_task_list` / `_refresh_preset_list` 仅被 `refresh()` 调用，`refresh()` 仅被 `_delayed_init`、`_on_metadata_loaded`、`set_bridge` 调用。
- 修改后，`refresh()` 的触发频率与调用点不变，仅内部行为更安全。

### 3.3 用户可见行为变化

- **修复前**：切换页面后再返回，任务/预设列表可能被清空，或选中项丢失。
- **修复后**：列表内容与选中态在后台刷新后保持不变；仅当元数据确实变化时才更新。

## 4. 非期待变化与回退策略

### 4.1 非期待变化

1. **启动时列表可能短暂为空**：若 `cache/metadata_cache.json` 为空，`_delayed_init` 不再阻塞主线程加载 metadata，列表需等待 `MetadataLoadWorker` 完成后才显示。但这是预期行为，避免 GUI 冻结。
2. **元数据更新不及时**：若后台 worker 失败，列表不会自动重试刷新。但失败时旧缓存仍然有效，优于清空。

### 4.2 回退策略

若需恢复旧行为，仅需：
1. 将 `_delayed_init` 中的 `if self._tasks_cache or self._presets_cache:` 条件移除。
2. 将 `_on_metadata_loaded` 中的成功判断移除，恢复无条件 `self.refresh()`。

## 5. 验证建议

1. **清空 `cache/metadata_cache.json`**，启动应用并快速切换到其他页面，等待 10 秒后返回，确认列表未被清空。
2. **选中一个任务**，在选项编辑器修改选项，切换到其他页面，等待后台 worker 完成，返回后确认选中项与选项值保持不变。
3. **模拟 metadata list 失败**（如临时断开 CLI），确认列表不会被清空。
4. 运行 `pytest` 确认现有测试通过。
